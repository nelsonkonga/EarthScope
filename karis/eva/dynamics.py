"""Molettes de dynamique (``EvaConfig(model="dynamics")``) — the user's theory of 2026-11-09.

Every molette captures a *dynamic*, like the gradient of a curve, and knows its **norm**
(the typical gradient) and its **extremes** (the out-of-norm gradients). Nothing here knows
what the watchers mean.

Units (what can change)
    - the watchers the environment shows;
    - *construction elements*, discovered from the dynamics alone: a set of steps
      ``(watcher, old, new)`` whose completion is followed by an extreme of the global
      dynamic (nothing moves any more: the episode stops) is a unit; its value is its
      magnitude ``(done, impossible)``. The same steps built by another side (same watchers,
      same starting values) are the same unit, seen from the other side.

Degrees (transitions of transitions)
    The reading of a unit at degree 1 is its value; at degree k it is its last k values: the
    transition it is making (degree 2: ``(before, now)``, a stay ``(x, x)`` included — a
    dynamic may stay the same), the change of that transition (degree 3), and so on. The
    molette of degree k learns how its reading moves on: ``P(next value | reading, source)``
    (its norm), and the running mean / spread of the surprise of what it sees: a transition
    whose surprise is far above the typical one is out of norm (an extreme). The source is
    whether the perspective's own action or the world brought the transition.
    Transitions are symmetric (the user's rule, 2026-11-10: a transition molette is a question
    of transition, never of time): every transition is also read backwards — from ``nxt`` one
    goes back to the reading, its direction kept (the backward reading is marked ``BACK``) — so
    a point can be recognised from either side; its surprise is the mean of its two readings.

Meta molettes (at every degree, over 2, 3, 4... dynamics, and over meta molettes)
    When two dynamics change at the same tick because of the same event significantly more
    often than chance, a meta molette is born over them at that degree. A meta molette is a
    dynamic too (it moves as a whole when one event moves all its members): with another
    unit moved by the same event it gives a meta molette over three dynamics, with another
    meta molette one over their union (a meta molette over meta molettes is represented by
    the base dynamics it joins: their joint reading is the readings of the meta molettes it
    is built on). Its reading is the tuple of its members' readings; its molette learns their
    joint dynamic (which joint moves are standard, which are extremes). At degree 1 it follows
    values, at degree 2 transitions (a meta-transition), and so on.

Field derivatives (when the environment gives a layout: where each watcher is)
    The change of a field of symbols is decomposed into atomic events (the user's convention,
    Blink): a symbol that leaves one watcher and arrives at another moved by Δ; one that
    leaves the field without arriving anywhere went to the graveyard; one that appears from
    nowhere is a creation. A capture is two events: the mover's displacement and the taken
    symbol's departure to the graveyard. Every event type has its decision molette
    (``("F", "move", symbol, Δ, source)``, ``("F", "grave", symbol, source)``...). The field
    molettes: for every ordered pair of occupied watchers, the relation (symbol of the
    first, Δ to the second, free line of sight) and its norm — how often that symbol moves by
    Δ onto what stands there (``checks/chess_derivatives.py``: learned in 2 to 5 games, it
    tells which pieces are about to be taken far better than square-pair meta molettes).
    No rule of any domain: only symbols, positions and straight lattice lines.

Decision molettes
    Every reading of every molette has a note, neutral (0) at first. At the end of an
    episode each reading that occurred tilts toward the outcome on its own, by a constant
    step that is never divided, modulated only by its own belief (an extreme belief is
    harder to move): ``note += step * (1 - note^2)^resistance * (R - note)``.

Choosing the next action
    No search: the environment is never simulated. A candidate action is judged on the
    dynamics it makes now (the transitions of every unit and meta molette, staying
    included), and on the dynamics the molettes expect the world to make next (their norm,
    and their extremes). The action that keeps the dynamics globally favourable is taken;
    how the readings are combined is ``cfg.dyn_measure``.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from itertools import combinations

from .heatmaps import CHANCE, VETO, Layer, lattice_transforms, wilson_low  # noqa: F401  (wilson_low: used here too)

OWN, WORLD = "own", "world"
GRAVE = "grave"
# a decision molette's note is proven when chance would leave a neutral one that far from 0 less
# often than CHANCE (two-sided) — the decision then reads it (``dyn_proven``)
PROOF_Z = 2.5758293035489004
BACK = "↶"  # marks a reading seen from the other side of its transition (read backwards)


class Molette:
    """Norm and extremes of one dynamic.

    ``counts[(reading, source)][next]`` is how the reading moved on (sparse counts that never
    forget: the distribution converges); ``s_mean`` / ``s_m2`` follow the surprise of the
    transitions seen (Welford), so each new transition can be read as standard or out of norm.
    Eva records every transition both ways (``record_both``: transitions are symmetric); the
    one-way ``record`` / ``record_many`` stay for callers that read both ways themselves.
    """

    __slots__ = ("counts", "totals", "n", "s_mean", "s_m2", "extremes")

    def __init__(self):
        self.counts: dict = {}
        self.totals: dict = {}
        self.n = 0
        self.s_mean = 0.0
        self.s_m2 = 0.0
        self.extremes = 0

    def surprise(self, reading, src, nxt) -> float:
        """Bits of surprise of ``nxt`` under the norm (Laplace-smoothed)."""
        key = (reading, src)
        row = self.counts.get(key)
        if not row:
            return 1.0
        return -math.log2((row.get(nxt, 0) + 0.5) / (self.totals[key] + 0.5 * (len(row) + 1)))

    def spread(self) -> float:
        return math.sqrt(self.s_m2 / (self.n - 1)) if self.n > 1 else 0.0

    def is_extreme(self, s: float, z: float) -> bool:
        """Is a transition of surprise ``s`` out of this molette's norm?"""
        if self.n < 20:
            return False
        sd = self.spread()
        return sd > 0 and (s - self.s_mean) / sd > z

    def record(self, reading, src, nxt, z: float) -> bool:
        """Count one transition; returns True if it was out of norm."""
        s = self.surprise(reading, src, nxt)
        extreme = self.is_extreme(s, z)
        self.n += 1
        d = s - self.s_mean
        self.s_mean += d / self.n
        self.s_m2 += d * (s - self.s_mean)
        if extreme:
            self.extremes += 1
        key = (reading, src)
        row = self.counts.get(key)
        if row is None:
            row = self.counts[key] = {}
            self.totals[key] = 0
        row[nxt] = row.get(nxt, 0) + 1
        self.totals[key] += 1
        return extreme

    def record_many(self, reading, src, nxt, n: int, z: float) -> None:
        """Count the same transition ``n`` times (a dynamic that stayed still for n ticks)."""
        if n <= 0:
            return
        s = self.surprise(reading, src, nxt)
        if self.is_extreme(s, z):
            self.extremes += n
        n0 = self.n
        d = s - self.s_mean
        self.n = n0 + n
        self.s_mean += d * n / self.n
        self.s_m2 += d * d * n0 * n / self.n
        key = (reading, src)
        row = self.counts.get(key)
        if row is None:
            row = self.counts[key] = {}
            self.totals[key] = 0
        row[nxt] = row.get(nxt, 0) + n
        self.totals[key] += n

    def record_both(self, reading, src, nxt, back, prev, z: float, n: int = 1) -> bool:
        """Count one transition read both ways — the user's rule (2026-11-10): a transition is
        never a question of time, and transitions are symmetric; read from either side it is the
        same transition, its direction kept. Forward, ``reading`` goes to ``nxt``; backwards,
        ``back`` (the reading seen from the other side, marked ``BACK``, see ``backward``) goes
        to ``prev``, so a point can be recognised from either side. Its surprise is the mean of
        its two readings (as ``detective/investigate.py``); ``n`` counts it n times (a dynamic
        that stayed still). Returns True if it was out of norm."""
        if n <= 0:
            return False
        s = (self.surprise(reading, src, nxt) + self.surprise(back, src, prev)) / 2
        extreme = self.is_extreme(s, z)
        if extreme:
            self.extremes += n
        n0 = self.n
        d = s - self.s_mean
        self.n = n0 + n
        self.s_mean += d * n / self.n
        self.s_m2 += d * d * n0 * n / self.n
        for key, y in (((reading, src), nxt), ((back, src), prev)):
            row = self.counts.get(key)
            if row is None:
                row = self.counts[key] = {}
                self.totals[key] = 0
            row[y] = row.get(y, 0) + n
            self.totals[key] += n
        return extreme

    def forward(self):
        """The counts read forward, ``((reading, source), {next: count})`` — without the same
        transitions read backwards, which would count every transition twice."""
        for key, row in self.counts.items():
            r = key[0]
            if not (type(r) is tuple and len(r) == 2 and r[0] == BACK):
                yield key, row

    def back_dist(self, after, src) -> dict | None:
        """Read backwards: where the reading ``after`` (seen from the other side, as returned
        by ``backward``) came from."""
        return self.dist(after, src)

    def dist(self, reading, src) -> dict | None:
        """Where the norm says the reading goes next."""
        key = (reading, src)
        row = self.counts.get(key)
        if not row:
            return None
        t = self.totals[key]
        return {x: c / t for x, c in row.items()}

    def size(self) -> int:
        return sum(len(r) for r in self.counts.values())


class Track:
    """What one perspective is living through in the current episode."""

    __slots__ = ("hist", "keys", "acted", "start", "obs", "comp_prev", "events", "reward", "ended",
                 "n", "recent", "settled", "msettled", "fkeys", "departs", "sig", "final",
                 "read", "rkeys", "chose", "cand_t", "cand_s", "seen", "choices", "reading_step", "rels",
                 "made", "tried", "explored")

    def __init__(self, obs: dict, vals: dict):
        self.hist: list[dict] = [vals]  # unit values of the last ticks (hist[-1] = now)
        self.keys: dict = {}  # readings that occurred -> tick of their first occurrence (noted at the end)
        self.rels = None  # the field's relations at the last tick (``dyn_relations``)
        self.made = set()  # the relations the last tick created
        self.tried = None  # what the perspective's own action should make (its afterstate)
        self.explored: list = []  # (anchor, tick) of each exploration beyond the norm (``Dynamics.explore``)
        self.acted = False  # the perspective's own action brought the next tick
        self.start = dict(obs)  # watcher values when the episode began
        self.obs = dict(obs)
        self.comp_prev: set = set()  # candidate sets completed at the previous tick
        self.events: list = []  # steps of the last tick
        self.reward = 0.0
        self.ended = False
        # A dynamic that has stayed still long enough has constant readings at every degree:
        # its stays are counted in one go (when it moves again, before a decision, at the end)
        self.n = {OWN: 0, WORLD: 0}  # ticks of each source in this episode
        self.recent: dict = {}  # unit -> ticks left before its readings are constant
        self.settled: dict = {}  # unit -> tick counts when it settled (stays not yet counted)
        self.msettled: dict = {}  # the same for meta molettes
        self.fkeys: dict = {}  # atomic events of the field that occurred -> tick of the first one
        self.sig: list = []  # the signal the domain sent at each tick (captures, promotions...)
        self.final = 0.0  # the end's feedback
        self.departs: list = []  # symbols that left the field at the last tick
        # « la réponse arrive après une lecture » (dyn_reading): the ticks the perspective brings
        # itself without having a choice (it reads), before its first choice, are a reading; the
        # choices that follow it are judged by what it identified. The world moving before the
        # perspective's first choice (an opponent's first move) is not a reading
        self.reading_step = False  # the next tick comes from the perspective's own step without a choice
        self.read: set = set()  # readings of every dynamic before the first choice
        self.rkeys: list | None = None  # the same with their types (built at the first choice)
        self.chose = False  # the perspective has had a choice in this episode
        self.cand_t: list | None = None  # transitions of each candidate of the pending choice
        self.cand_s: list | None = None  # what the reading says of each candidate (before its norm)
        self.seen: list = []  # (transitions, what the reading said) of every candidate judged after it
        self.choices: list = []  # transitions of the actions chosen after the reading


class Voice(float):
    """A note read by the judge with the weight of its voice (``dyn_attention_judge``): how far
    from neutral it is, against what a neutral molette shows after as many tilts."""

    w: float = 0.0


def backward(before, nxt, k: int) -> tuple:
    """The transition ``before`` -> ``nxt`` of a degree-k reading, read backwards: (the reading
    seen from the other side, marked ``BACK``; the value it leads to). Degree 1: from ``nxt``
    one goes back to ``before``; degree k: the values (x1 … xk, y) read from y, i.e.
    (y, xk … x2), goes back to x1. The direction stays in the transition: the backward reading
    is never the forward reading of the reverse transition."""
    if k == 1:
        return (BACK, nxt), before
    return (BACK, (nxt,) + tuple(reversed(before[1:]))), before[0]


def backward_joint(before, nxt, k: int) -> tuple:
    """The same for a joint reading (a meta molette, or its type), member by member."""
    parts = [backward(b, y, k) for b, y in zip(before, nxt)]
    return (BACK, tuple(p[0][1] for p in parts)), tuple(p[1] for p in parts)


def reading(hist: list, u, k: int):
    """Degree-k reading of unit ``u`` at the end of ``hist`` (None if too short)."""
    if k == 1:
        return hist[-1].get(u)
    if len(hist) < k:
        return None
    return tuple(h.get(u) for h in hist[-k:])


class Dynamics:
    def __init__(self, cfg):
        self.cfg = cfg
        self.D = max(1, cfg.dyn_degrees)
        self.units: list = []  # watcher names (str) and elements ("E", steps)
        self.uw: dict = {}  # unit -> frozenset of its watchers
        self.steps: dict = {}  # element -> its steps (watcher, old, new)
        self.by_watcher: dict = defaultdict(list)  # watcher -> units it belongs to
        self.footprints: set = set()
        self.mol: dict = {}  # (unit or meta, degree) -> Molette
        self.metas: list = []  # ("M", k, members): members = base units, sorted
        self.meta_set: set = set()
        self.meta_by_unit: dict = defaultdict(list)
        self.co: dict = defaultdict(int)  # (k, X, Y) -> ticks where one event changed both dynamics
        self.chg: dict = defaultdict(int)  # (k, unit or meta) -> ticks where an event changed its reading
        self.ticks = 0
        self.notes: dict = {}
        self.noted: dict = defaultdict(int)  # episodes in which a reading was noted
        self.track: dict[int, Track] = {}
        self.cand: dict = {}  # candidate element -> [completions then stop, completions then go on]
        self.cand_by_ev: dict = defaultdict(set)
        self.episodes = 0
        self.dissolved = 0
        self.types: dict = {}  # unit or meta -> its type of dynamics
        self._refs: dict = {}
        # field derivatives (a layout is given)
        self.layout: dict | None = None
        self.pos_to_w: dict = {}
        self.fcount: Counter = Counter()  # (symbol, Δ, line of sight, source) -> relations seen
        self.fmove: Counter = Counter()  # ... -> times the symbol moved by Δ onto what stood there
        self._between: dict = {}
        self._att: dict = {}  # symbol -> [(Δ, line of sight, P(it moves by Δ onto what stands there))]
        self._slopes: dict = {}  # symbol -> what one more of it is worth (gradient of its count molette's note)
        self._att_own: dict = {}  # own symbol -> [(Δ, line of sight, 1)] seen possible
        self._memo: dict = {}  # dynamic minimax: fields already valued during this decision
        self._bg = "."  # the background value of the field (set at each decision)
        self._obs_now: dict = {}  # the observation the decision starts from (its other watchers)
        # the end is an event too: a departure never seen without the end that follows it
        self.fdisp: Counter = Counter()  # (symbol, Δ, line of sight, onto an empty watcher, source) -> seen
        self.departs: Counter = Counter()  # symbol -> departures from the field seen
        self.ends: dict = {}  # symbol -> [episodes it departed at the last tick of, sum of their outcomes]
        self._moves: dict = {}  # source -> symbol -> [(Δ, line of sight)] seen onto an empty watcher
        self._attset: dict = {}  # source -> symbol -> {Δ} of its captures with a free line of sight
        self._terminal: dict = {}  # symbol -> what the end its departure brings is worth
        self._side: dict = {}  # source -> symbols seen moving at its ticks (its own pieces)
        self._bound: dict = {}  # (source, symbol, Δ) -> {axis: coordinates it is made from} (``_place_binding``)
        self._never: dict = {}  # source -> relations never seen after its moves (``_never_seen``)

    # ------------------------------------------------------------------ units
    # caches of computation only: emptied, never saved with Eva (``__getstate__``) — the first one
    # had reached 737 147 entries (325 MB) after 112 games and got a 200-game run killed (§ 25)
    TRANSIENT = ("_tkeys", "_step_sets", "_memo", "_cap_lines")

    def __getstate__(self) -> dict:
        state = dict(self.__dict__)
        for k in self.TRANSIENT:
            if k in state:
                state[k] = {}
        return state

    def _reshaped(self) -> None:
        """A unit or a meta molette was born or dissolved: what a step touches changes."""
        self._shape_ver = self.__dict__.get("_shape_ver", 0) + 1

    def _add_unit(self, u, watchers, steps=None) -> None:
        self._reshaped()
        self.units.append(u)
        self.uw[u] = frozenset(watchers)
        if steps is not None:
            self.steps[u] = steps
        for w in watchers:
            self.by_watcher[w].append(u)

    def _remove_unit(self, u) -> None:
        self._reshaped()
        self.units.remove(u)
        for w in self.uw.pop(u):
            self.by_watcher[w].remove(u)
        st = self.steps.pop(u, None)
        if st is not None:
            self.footprints.discard(frozenset((w, o) for w, o, _n in st))
        for m in list(self.meta_by_unit.pop(u, [])):
            self._remove_meta(m)
        self.mol = {k: v for k, v in self.mol.items() if k[0] != u}
        self.notes = {k: v for k, v in self.notes.items() if k[0] != u}

    def _remove_meta(self, m) -> None:
        self._reshaped()
        if m in self.meta_set:
            self.metas.remove(m)
            self.meta_set.discard(m)
        for x in m[2]:
            if m in self.meta_by_unit.get(x, []):
                self.meta_by_unit[x].remove(m)
        for other in [o for o in self.metas if set(m[2]) <= set(o[2]) and o[1] == m[1]]:
            self._remove_meta(other)  # built on it
        self.mol.pop((m, m[1]), None)
        self.notes = {k: v for k, v in self.notes.items() if k[0] != m}

    @staticmethod
    def base(X) -> tuple:
        """The base dynamics a unit or a meta molette is made of."""
        return X[2] if isinstance(X, tuple) and X and X[0] == "M" else (X,)

    def _see_watchers(self, obs: dict) -> None:
        for w in obs:
            if w not in self.uw:
                self._add_unit(w, (w,))

    def values(self, obs: dict, units=None) -> dict:
        """Value of each unit in a state: the watcher's value, an element's magnitude."""
        out = {}
        steps = self.steps
        for u in self.units if units is None else units:
            st = steps.get(u)
            if st is None:
                out[u] = obs.get(u)
                continue
            done = imp = 0
            for w, old, new in st:
                v = obs.get(w)
                if v == new:
                    done += 1
                elif v != old:
                    imp += 1
            out[u] = (done, imp)
        return out

    def molette(self, x, k: int) -> Molette:
        m = self.mol.get((x, k))
        if m is None:
            m = self.mol[(x, k)] = Molette()
        return m

    # --------------------------------------------------------------- episodes
    def begin(self, p: int, obs: dict, layout: dict | None = None) -> None:
        if layout and self.layout is None and self.cfg.dyn_field:
            self.layout = {w: tuple(pos) for w, pos in layout.items()}
            self.pos_to_w = {pos: w for w, pos in self.layout.items()}
        if self.layout is not None:
            if self.__dict__.get("_att_key") != self._att_inputs():  # rebuilt only if something was observed since
                self._rebuild_att()
            self._rebuild_slopes()
        self._see_watchers(obs)
        tr = self.track[p] = Track(obs, self.values(obs))
        tr.recent = {u: self.D for u in self.units}

    def tick(self, p: int, obs: dict, feedback: float = 0.0, learn: bool = True) -> None:
        """One tick seen from perspective p. With ``learn=False`` (Eva is not training) the
        perspective only follows the episode: no count, no reading noted, no birth.

        Only the dynamics that move, or moved in the last ``D`` ticks, are worked on; a
        dynamic that stays still has constant readings and its stays are counted in one go
        (``_flush``), with the same counts as tick by tick."""
        tr = self.track.get(p)
        if tr is None:
            self.begin(p, obs)
            return
        src = OWN if tr.acted else WORLD
        tr.acted = False
        tried, tr.tried = tr.tried, None
        if src == OWN and tried is not None and feedback and obs == tr.obs:
            # its action changed nothing and brought a signal: the world refused it. That signal is
            # the attempted transition's only (« uniquement ce coup, pas tous les coups qui sont
            # venus avant », the user, 2026-11-12): its own molettes tilt toward it, nothing else
            if learn and not self.cfg.dyn_freeze_notes:
                self._refused(tr, tried, feedback)
            tr.explored = [e for e in tr.explored if e[1] != len(tr.sig)]  # it did not happen
            return
        tr.reward += feedback
        prev_obs = tr.obs
        moved_w = [w for w, v in obs.items() if prev_obs.get(w) != v]
        touched = {u for w in moved_w for u in self.by_watcher.get(w, ())}
        H = tr.hist
        vals = dict(H[-1])
        vals.update(self.values(obs, touched))
        tr.obs = dict(obs)
        if not learn:
            if self.layout is not None and self.cfg.dyn_relations and (self._attset.get(OWN) or self._attset.get(WORLD)):
                self._follow_relations(tr, prev_obs, obs, self._background(prev_obs))  # her decisions read « = »
            H.append(vals)
            if len(H) > self.D + 1:
                del H[0]
            if tr.reading_step and not tr.chose and self.cfg.dyn_reading:
                self._note_reading(tr, src)
            tr.reading_step = False
            return
        events = [(w, prev_obs.get(w), obs[w]) for w in moved_w]
        tr.sig.append(feedback)
        now = len(tr.sig) - 1
        if self.layout is not None:
            self._field_tick(tr, prev_obs, obs, src)
            if self.cfg.dyn_story:  # what the static field tells at this tick
                self._bg = self._background(obs)
                for (X, k, r, _s) in self.field_readings(obs):
                    tr.keys.setdefault((X, k, r, src), now)
        if self.cfg.dyn_elements:
            self._watch_completions(tr, obs, events)
        tr.events = events
        moved = {u for u in touched if H[-1].get(u) != vals[u]}  # a transition arrived in these dynamics
        for u in moved:  # their stillness ends: count it before this tick
            if u in tr.settled:
                self._flush(tr, u)
                del tr.settled[u]
            for m in self.meta_by_unit.get(u, ()):
                if m in tr.msettled:
                    self._flush_meta(tr, m)
                    del tr.msettled[m]
        H.append(vals)
        if len(H) > self.D + 1:
            del H[0]
        if tr.reading_step and not tr.chose and self.cfg.dyn_reading:
            self._note_reading(tr, src)
        tr.reading_step = False
        tr.n[src] += 1
        self.ticks += 1
        D, z, keys = self.D, self.cfg.dyn_extreme_z, tr.keys
        tnorm = self.cfg.dyn_types != "off" and self.cfg.dyn_type_norm
        changed: dict[int, list] = {k: [] for k in range(1, D + 1)}
        for u in moved:
            tr.recent[u] = D
        active = set(tr.recent)
        for u in active:
            x = vals[u]
            is_moved = u in moved
            for k in range(1, D + 1):
                if len(H) < k + 1:
                    break
                before = reading(H[:-1], u, k)
                back, prev = backward(before, x, k)  # transitions are symmetric (user, 2026-11-10)
                self.molette(u, k).record_both(before, src, x, back, prev, z)
                if tnorm:
                    self.molette(self._type_of(u), k).record_both(before, src, x, back, prev, z)
                if is_moved and reading(H, u, k) != before:
                    changed[k].append(u)
                    self.chg[(k, u)] += 1
            for k in range(1, min(D, len(H)) + 1):
                keys.setdefault((u, k, reading(H, u, k), src), now)
            if not is_moved:
                left = tr.recent[u] - 1
                if left > 0:
                    tr.recent[u] = left
                else:  # its readings are constant from now on
                    del tr.recent[u]
                    tr.settled[u] = (tr.n[OWN], tr.n[WORLD])
        # meta molettes: their joint dynamics, and the births of new ones
        mact = {m for u in active for m in self.meta_by_unit.get(u, ())}
        for m in mact:
            _, k, ms = m
            if len(H) >= k:
                now_r = tuple(reading(H, x, k) for x in ms)
                keys.setdefault((m, k, now_r, src), now)
                if len(H) >= k + 1:
                    before = tuple(reading(H[:-1], x, k) for x in ms)
                    nxt = tuple(vals[x] for x in ms)
                    self.molette(m, k).record_both(before, src, nxt, *backward_joint(before, nxt, k), z)
                    if tnorm:
                        cb, cn = self._canon(m, before, nxt)
                        self.molette(self._type_of(m), k).record_both(cb, src, cn, *backward_joint(cb, cn, k), z)
                    if now_r != before and moved.issuperset(ms):  # one event moved all its dynamics at once
                        changed[k].append(m)
                        self.chg[(k, m)] += 1
            if not any(x in tr.recent for x in ms):
                tr.msettled[m] = (tr.n[OWN], tr.n[WORLD])
        arity = self.cfg.dyn_meta_arity
        spont = self.cfg.dyn_meta_birth == "spontaneous"
        for k, xs in changed.items():
            if len(xs) > 1:
                for X, Y in combinations(sorted(xs, key=repr), 2):
                    if len(set(self.base(X)) | set(self.base(Y))) > arity or not self._apart(X, Y):
                        continue
                    key = (k, X, Y)
                    c = self.co[key] = self.co[key] + 1
                    if spont and c >= self.cfg.dyn_meta_min:
                        self._consider(key, c)

    def _stays(self, tr: Track, since) -> tuple:
        return ((OWN, tr.n[OWN] - since[0]), (WORLD, tr.n[WORLD] - since[1]))

    def _flush(self, tr: Track, u) -> None:
        """Count the stays of a still unit since it settled (its readings were constant)."""
        x = tr.hist[-1][u]
        z, tnorm = self.cfg.dyn_extreme_z, self.cfg.dyn_types != "off" and self.cfg.dyn_type_norm
        t = self._type_of(u) if tnorm else None
        for src, n in self._stays(tr, tr.settled[u]):
            if n <= 0:
                continue
            for k in range(1, self.D + 1):
                r = x if k == 1 else (x,) * k
                back, prev = backward(r, x, k)
                self.molette(u, k).record_both(r, src, x, back, prev, z, n)
                if tnorm:
                    self.molette(t, k).record_both(r, src, x, back, prev, z, n)
                tr.keys.setdefault((u, k, r, src), sum(tr.settled[u]))

    def _flush_meta(self, tr: Track, m) -> None:
        _, k, ms = m
        xs = tuple(tr.hist[-1][x] for x in ms)
        r = xs if k == 1 else tuple((xi,) * k for xi in xs)
        z, tnorm = self.cfg.dyn_extreme_z, self.cfg.dyn_types != "off" and self.cfg.dyn_type_norm
        for src, n in self._stays(tr, tr.msettled[m]):
            if n <= 0:
                continue
            self.molette(m, k).record_both(r, src, xs, *backward_joint(r, xs, k), z, n)
            if tnorm:
                cb, cn = self._canon(m, r, xs)
                self.molette(self._type_of(m), k).record_both(cb, src, cn, *backward_joint(cb, cn, k), z, n)
            tr.keys.setdefault((m, k, r, src), sum(tr.msettled[m]))

    def _flush_all(self, tr: Track) -> None:
        """Count every pending stay (before a decision reads the norms, and at the end)."""
        now = (tr.n[OWN], tr.n[WORLD])
        for u in tr.settled:
            if tr.settled[u] != now:
                self._flush(tr, u)
                tr.settled[u] = now
        for m in tr.msettled:
            if tr.msettled[m] != now:
                self._flush_meta(tr, m)
                tr.msettled[m] = now

    def end(self, p: int, final: float = 0.0, learn: bool = True) -> None:
        tr = self.track.get(p)
        if tr is None or tr.ended:
            return
        tr.reward += final
        tr.final = final
        tr.ended = True
        if learn:
            self._flush_all(tr)
            if self.cfg.dyn_elements:
                self._end_completions(tr)
            if self.layout is not None:  # the departures of the last tick: the end followed them
                R = max(-1.0, min(1.0, tr.final))
                ends = self.__dict__.setdefault("ends", {})
                for v in set(tr.departs):
                    e = ends.setdefault(v, [0, 0.0])
                    e[0] += 1
                    e[1] += R

    def learn(self) -> None:
        """Every reading that occurred tilts toward the outcome, on its own."""
        cfg = self.cfg
        a, res, notes, noted = cfg.dyn_step, cfg.resistance, self.notes, self.noted
        tau = self.__dict__.get("len_norm")
        T = max((t.n[OWN] + t.n[WORLD] for t in self.track.values()), default=0)
        W = cfg.dyn_signal_window
        for tr in self.track.values():
            if cfg.dyn_freeze_notes:  # a diagnosis: the decision molettes do not move (what is observed still is)
                continue
            local = cfg.dyn_signals and any(tr.sig)
            end = tr.final if local else tr.reward
            end = max(-1.0, min(1.0, end))
            if cfg.dyn_end_distance and tau:
                # « le plus proche de la victoire, le plus loin possible de la victoire adverse »:
                # an end that comes sooner than the norm counts more, a later one less
                end *= 1.0 - 0.5 * T / (T + tau)
            if cfg.dyn_signals and cfg.dyn_signal_mode == "plaisir":
                # « les signaux ne sont pas là pour lui dire ce qui est bon ou ce qui mène à la
                # victoire ou à la défaite mais ce qui est plaisant et ce qui ne l'est pas » ; « même
                # la victoire est un signal » ; « on crédite toutes les molettes qui sont
                # intervenues jusqu'à l'apparition du signal, c'est une généralisation du système
                # actuel » (the user, 2026-11-11). Every signal — a capture, a promotion, the end —
                # credits every decision molette whose reading occurred before it appeared: a
                # reading tilts toward the sum of the signals that came after its first occurrence,
                # the end included. With the end as the only signal (TicTacToe) it is the rule of
                # every episode before: every reading toward the outcome.
                # the end: what came besides the tick signals (a track never ended: its reward)
                end = tr.final if tr.ended else tr.reward - sum(tr.sig)
                post = [0.0] * (len(tr.sig) + 1)
                for i in range(len(tr.sig) - 1, -1, -1):
                    post[i] = post[i + 1] + tr.sig[i]
                n = len(tr.sig)

                bound = cfg.dyn_target_bound

                def target(t, post=post, n=n, end=end, bound=bound):
                    # the bound [-1, 1] flattened every signal of a mated game: its end is already -1,
                    # so losing the queen, a pawn or nothing all gave -1 (98 % of the readings of
                    # mated games against Stockfish, RESULTS.md § 32) — « les signaux apportent des
                    # feedbacks positifs / négatifs, comme des mini victoires et défaites »
                    x = end + post[min(n, max(0, t))]
                    if bound == "none":
                        return x
                    if bound == "tanh":
                        return math.tanh(x)
                    return max(-1.0, min(1.0, x))
            elif local:  # the signals that followed a reading within W ticks (it included)
                pre = [0.0]
                for x in tr.sig:
                    pre.append(pre[-1] + x)
                n = len(tr.sig)

                def target(t, pre=pre, n=n, end=end):
                    return max(-1.0, min(1.0, end + pre[min(n, t + W + 1)] - pre[min(n, t)]))
            else:
                def target(t, end=end):
                    return end
            # the norm of each transition chosen after a reading: its own note before this episode
            base = {x: notes.get(x, 0.0) for t in tr.choices for x in t} if cfg.dyn_reading else {}
            items = dict(tr.keys)
            born = cfg.dyn_birth_note
            tfrom: dict = {}  # a type reading never noted -> one reading of it (its birth note)
            if cfg.dyn_types != "off":
                for k, t in tr.keys.items():
                    tk = self.type_key(k)
                    items[tk] = min(t, items.get(tk, t))
                    if born and tk not in notes and tk not in tfrom:
                        tfrom[tk] = k
            if self.layout is not None and self.cfg.dyn_field:
                for k in self._count_keys(tr):
                    items[k] = len(tr.sig)  # where the episode stops: the end only
            for k, t in tr.fkeys.items():
                items[k] = min(t, items.get(k, t))
            # the norm of what follows a dynamic (« norme et hors norme », applied to outcomes): a
            # note says what follows its dynamic beyond what usually follows any — against a world
            # that always wins, every note slid toward the common level, the frequent ones first,
            # and a note told how often its dynamic occurred (RESULTS.md § 23)
            on = self.__dict__.get("onorm", [0, 0.0]) if cfg.dyn_outcome_norm else [0, 0.0]
            # the norm of what follows a dynamic AT THAT MOMENT of the episode: a reading is credited
            # with all that follows its first occurrence, so in a bad episode an early reading gets
            # all of it and a late one only its end — against one norm for all, a dynamic looked
            # bad for coming early and good for coming late (ten times any dynamic's own effect)
            by_tick = cfg.dyn_outcome_norm and cfg.dyn_norm_by_tick
            at = self.__dict__.setdefault("onorm_at", {}) if by_tick else {}
            n_end = len(tr.sig)

            def norm(t):
                if not by_tick:
                    return on[1]
                st = at.get("end" if t >= n_end else t)
                return st[1] if st and st[0] else on[1]

            sq = cnt = tot = 0.0
            for key, t in items.items():
                R = target(t)
                v = notes.get(key)
                if v is None:  # its first tilt starts from its birth note
                    v = (self._born_note(1, tfrom[key]) if key in tfrom else self._born_note(0, key)) if born else 0.0
                notes[key] = v + a * max(0.0, 1.0 - v * v) ** res * (R - norm(t) - v)
                noted[key] += 1
                sq += R * R
                tot += R
                cnt += 1
            # each exploration's anchor learns what followed it beyond the norm: a good anchor
            # favours exploring around it (« identifier les explorations prometteuses »)
            an = self.__dict__.setdefault("anchor_notes", {})
            an_n = self.__dict__.setdefault("anchor_noted", Counter())
            for m, t in tr.explored:
                v = an.get(m, 0.0)
                an[m] = v + a * max(0.0, 1.0 - v * v) ** res * (target(t) - norm(t) - v)
                an_n[m] += 1
            if cfg.dyn_outcome_norm and cnt:  # a distribution: it converges (not a decision molette)
                on[0] += 1
                on[1] += max(1.0 / on[0], a) * (tot / cnt - on[1])
                self.onorm = on
            if by_tick:  # the norm of each moment: what follows any dynamic from that tick on
                for t in list(range(n_end)) + ["end"]:
                    R = target(n_end if t == "end" else t)
                    st = at.setdefault(t, [0, 0.0])
                    st[0] += 1
                    st[1] += max(1.0 / st[0], a) * (R - st[1])
            if cnt:  # how far the outcomes the notes tilt toward spread (a neutral molette's noise scales with it)
                self.tvar = self.__dict__.get("tvar", sq / cnt) + a * (sq / cnt - self.__dict__.get("tvar", sq / cnt))
            rn = self.__dict__.setdefault("rnorm", {})
            for t, sc in tr.seen:  # the norm of what the reading says of each candidate
                for x in t:
                    # what the reading says drifts as the notes of frequent readings move (over
                    # hundreds of episodes): the norm follows it, over ~1/dyn_reading_norm
                    # episodes — with the notes' own step it followed the noise of the last ~20
                    # images, with a mean of all episodes it stayed where training began
                    # (RESULTS.md § 16, § 17)
                    st = rn.setdefault(x, [0, 0.0])
                    st[0] += 1
                    st[1] += max(1.0 / st[0], cfg.dyn_reading_norm) * (sc - st[1])
            if tr.choices and tr.read and cfg.dyn_reading:  # each reading joined to what was chosen after it
                rk = self._reading_keys(tr)
                for t in tr.choices:
                    for x in t:
                        # what the reading brings beyond the transition's own norm (its note: what
                        # this choice brings whatever was read); without it, a reading present in
                        # every episode only learns how often that choice went well, and those
                        # readings decide (an answer given 498 times out of 500, RESULTS.md § 16)
                        target = end - base[x]  # not clipped: clipping left a bias toward the choice that goes well more often
                        for r in rk:
                            key = ("L", r, x)
                            v = notes.get(key, 0.0)
                            notes[key] = v + a * max(0.0, 1.0 - v * v) ** res * (target - v)
                            noted[key] += 1
        self.track = {}
        if T:
            self.len_norm = T if tau is None else tau + a * (T - tau)  # the norm of episode lengths
        self.episodes += 1
        if self.episodes % cfg.dyn_check_every == 0:
            if cfg.dyn_elements:
                self.grow_elements()
            if cfg.dyn_meta_birth == "spontaneous":  # they are born at the tick (_consider)
                for key in [key for key in self.co if not (self._exists(key[1]) and self._exists(key[2]))]:
                    del self.co[key]
            else:
                self.grow_metas()

    # --------------------------------------------------------------- elements
    def _stat(self, S):
        """Where the evidence about a candidate set is counted. With ``dyn_elem_pool`` the
        same construction built by any side (same watchers, same starting values, steps
        grouped the same way by the values they reach) shares its evidence."""
        if not self.cfg.dyn_elem_pool:
            return self.cand.get(S)
        key = self.__dict__.setdefault("_ckey", {}).get(S)
        if key is None:
            groups: dict = {}
            for w, _o, n in S:
                groups.setdefault(n, set()).add(w)
            key = self._ckey[S] = (frozenset((w, o) for w, o, _n in S), frozenset(frozenset(g) for g in groups.values()))
        pool = self.__dict__.setdefault("cpool", {})
        st = pool.get(key)
        if st is None and S in self.cand:
            st = pool[key] = [0, 0]
        return st

    def _watch_completions(self, tr: Track, obs: dict, events: list) -> None:
        """The world went on after the sets completed at the previous tick; which candidate
        sets does this tick complete?"""
        for S in tr.comp_prev:
            st = self._stat(S)
            if st is not None:
                st[1] += 1
        comp = set()
        for e in events:
            for S in self.cand_by_ev.get(e, ()):
                if all(obs.get(w) == n for w, _o, n in S):
                    comp.add(S)
        tr.comp_prev = comp

    def _end_completions(self, tr: Track) -> None:
        """Nothing moves any more after the last tick: the sets it completed count as
        completions followed by an extreme; the sets the last step built with steps already
        held become candidates."""
        for S in tr.comp_prev:
            st = self._stat(S)
            if st is not None:
                st[0] += 1
        obs, start, cap = tr.obs, tr.start, self.cfg.dyn_max_cand
        held = [(w, start.get(w), v) for w, v in obs.items() if start.get(w) != v]
        for e in tr.events:
            others = [h for h in held if h[0] != e[0]]
            for n in range(1, self.cfg.elem_max_size):
                for T in combinations(others, n):
                    S = frozenset((e,) + T)
                    if S in self.cand or S in tr.comp_prev or len(self.cand) >= cap:
                        continue
                    self.cand[S] = [1, 0]
                    for x in S:
                        self.cand_by_ev[x].add(S)
                    if self.cfg.dyn_elem_pool:
                        self._stat(S)[0] += 1

    def grow_elements(self) -> list:
        """Adopt the sets whose completion is followed by the extreme (smallest first); one
        footprint is one element whichever side builds it; drop the sets whose completion
        clearly is not; dissolve an element whose completion no longer is."""
        cfg, made = self.cfg, []
        for u in [u for u in self.units if u in self.steps]:
            st = self._stat(frozenset(self.steps[u]))
            if st and st[0] + st[1] >= 30 and st[0] / (st[0] + st[1]) < cfg.dyn_ratio:
                self._remove_unit(u)
                self.dissolved += 1
        adopted = [frozenset(st) for st in self.steps.values()]
        for S in sorted(self.cand, key=lambda S: (len(S), repr(sorted(S, key=repr)))):
            stop, go = self._stat(S)
            if stop < cfg.dyn_min_ends or wilson_low(stop, stop + go) < cfg.dyn_ratio:
                continue
            fp = frozenset((w, o) for w, o, _n in S)
            if fp in self.footprints or any(E <= S for E in adopted):
                continue
            steps = tuple(sorted(S, key=repr))
            self._add_unit(("E", steps), [w for w, _o, _n in steps], steps)
            self.footprints.add(fp)
            adopted.append(S)
            made.append(steps)
        for S in [S for S in self.cand if sum(self._stat(S)) >= 30 and self._stat(S)[0] / sum(self._stat(S)) < 0.5]:
            del self.cand[S]
            for x in S:
                self.cand_by_ev[x].discard(S)
        return made

    # ------------------------------------------------------------------ metas
    def _apart(self, X, Y) -> bool:
        """Two different dynamics: none of the base dynamics of one is made of one of the
        other's (a watcher inside an element, or the same unit)."""
        uw = self.uw
        for a in self.base(X):
            for b in self.base(Y):
                if uw[a] <= uw[b] or uw[b] <= uw[a]:
                    return False
        return True

    def _exists(self, X) -> bool:
        return X in self.uw or X in self.meta_set

    def grow_metas(self) -> list:
        """A meta molette over two dynamics (units or meta molettes) that one event changed
        at the same tick much more often than chance (count, lift and z against
        independence), at that degree: over the union of their base dynamics."""
        cfg, made, T = self.cfg, [], max(1, self.ticks)
        best: dict = {}
        best_pair: dict = {}
        for key, c in list(self.co.items()):
            k, X, Y = key
            if not (self._exists(X) and self._exists(Y)):
                del self.co[key]
                continue
            if c < cfg.dyn_meta_min:
                continue
            m = ("M", k, tuple(sorted(set(self.base(X)) | set(self.base(Y)), key=repr)))
            if m in self.meta_set:
                continue
            e = self.chg[(k, X)] * self.chg[(k, Y)] / T
            if e <= 0:
                continue
            lift, z = c / e, (c - e) / math.sqrt(e)
            if lift >= cfg.meta_min_lift and z >= cfg.meta_z and z > best.get(m, -1.0):
                best[m] = z
                best_pair[m] = key
        for m, z in sorted(best.items(), key=lambda r: (len(r[0][2]), -r[1])):  # smallest first
            if self._birth(m, z, best_pair[m]):
                made.append(m)
        return made

    def _consider(self, key, c) -> None:
        """Spontaneous birth: the tick one event changed both dynamics of ``key`` once more,
        their co-changes are weighed at once (count, lift and z against independence, the
        same test as ``grow_metas``); the meta molette is born as soon as the evidence is
        there — not at a check every so many episodes."""
        k, X, Y = key
        m = ("M", k, tuple(sorted(set(self.base(X)) | set(self.base(Y)), key=repr)))
        if m in self.meta_set:
            return
        e = self.chg[(k, X)] * self.chg[(k, Y)] / max(1, self.ticks)
        if e <= 0:
            return
        lift, z = c / e, (c - e) / math.sqrt(e)
        if lift >= self.cfg.meta_min_lift and z >= self.cfg.meta_z:
            self._birth(m, z, key)

    def _birth(self, m, z: float, pair) -> bool:
        """A meta molette is born over ``m``'s base dynamics, within the budget of its degree
        (with ``dyn_meta_compete`` the least significant one of the degree may give way)."""
        cfg = self.cfg
        origin = self.__dict__.setdefault("meta_origin", {})
        k = m[1]
        if sum(1 for o in self.metas if o[1] == k) >= cfg.dyn_max_metas:
            if not cfg.dyn_meta_compete:
                return False
            # the budget is full: the least significant meta molette of this degree gives
            # way if this one is clearly more significant (it dissolves with its notes)
            weakest = min((o for o in self.metas if o[1] == k and o in origin),
                          key=lambda o: self._meta_z(origin[o]), default=None)
            if weakest is None or self._meta_z(origin[weakest]) * 1.25 >= z:
                return False
            self._remove_meta(weakest)
            origin.pop(weakest, None)
            self.dissolved_metas = getattr(self, "dissolved_metas", 0) + 1
            if sum(1 for o in self.metas if o[1] == k) >= cfg.dyn_max_metas:
                return False
        self._reshaped()
        self.metas.append(m)
        self.meta_set.add(m)
        origin[m] = pair
        for x in m[2]:
            self.meta_by_unit[x].append(m)
        return True

    def _meta_z(self, pair) -> float:
        """Significance of the co-changes a meta molette was born from (on current counts)."""
        k, X, Y = pair
        if not (self._exists(X) and self._exists(Y)):
            return 0.0
        e = self.chg[(k, X)] * self.chg[(k, Y)] / max(1, self.ticks)
        return (self.co.get(pair, 0) - e) / math.sqrt(e) if e > 0 else 0.0

    # ---------------------------------------------------------------- reading
    def _note_reading(self, tr: Track, src) -> None:
        """The perspective read (a step of its own without a choice, before its first choice):
        the readings of every dynamic at this tick — transitions and transitions of transitions,
        stays included — and of every meta molette make the reading its later choices follow."""
        H, read = tr.hist, tr.read
        top = min(self.D, len(H))
        for u in self.units:
            for k in range(2, top + 1):
                read.add((u, k, reading(H, u, k), src))
        for m in self.metas:
            _, k, ms = m
            if 2 <= k <= top:
                read.add((m, k, tuple(reading(H, x, k) for x in ms), src))

    def _reading_keys(self, tr: Track) -> list:
        if tr.rkeys is None:
            rk = set(tr.read)
            if self.cfg.dyn_types != "off":
                rk |= {self.type_key(k) for k in tr.read}
            tr.rkeys = list(rk)
        return tr.rkeys

    def reads(self, p: int) -> bool:
        """Did this episode begin with a reading (ticks without a choice)?"""
        tr = self.track.get(p)
        return bool(self.cfg.dyn_reading and tr is not None and tr.read)

    def reading_scores(self, p: int, cands: list) -> list[float]:
        """« la réponse n'arrive pas d'un coup, elle arrive après une lecture de l'image, après
        avoir identifié les dynamiques et les transitions de dynamique » (the user, 2026-11-10).
        A choice that follows a reading is judged by the decision molettes that join each
        reading to the transition the candidate makes, ``("L", reading, transition)`` — a note
        per pair, the type of the reading included, that says what the reading brings beyond
        the transition's own note (see ``learn``). Each reading counts for what it says of a
        candidate beyond what it says of all of them (attention), pooled as the other readings
        are (extremes weigh the most), and each candidate is read against its norm. Nothing here
        knows what is read or answered."""
        tr = self.track[p]
        rk = self._reading_keys(tr)
        cur, how = tr.hist[-1], self.cfg.dyn_measure
        tks = []
        for after, _final in cands:
            moved = [w for w, v in after.items() if tr.obs.get(w) != v]
            touched = {u for w in moved for u in self.by_watcher.get(w, ())}
            tks.append([(u, 2, (cur.get(u), x), OWN) for u, x in self.values(after, touched).items() if x != cur.get(u)])
        n = len(cands)
        num, den = [0.0] * n, [0.0] * n
        rn = self.__dict__.setdefault("rnorm", {})
        for _r, ds, ws in self.reading_votes(rk, tks):
            for i in range(n):
                num[i] += ds[i] * ws[i]
                den[i] += ws[i]
        out = [num[i] if how == "sum" else (num[i] / den[i] if den[i] > 0 else 0.0) for i in range(n)]
        tr.cand_t, tr.cand_s = tks, out
        # each candidate is read against its norm: what the reading usually says of it (each
        # candidate's notes were shaped by its own history; without its norm, one candidate wins
        # whatever is read — RESULTS.md § 16)
        return [sc - sum(rn[x][1] if x in rn else 0.0 for x in t) / max(1, len(t)) for sc, t in zip(out, tks)]

    def reading_votes(self, rk: list, tks: list):
        """For each reading that counts: (reading, what it says of each candidate beyond what it
        says of all, the weight of its voice) — the attention of ``reading_scores``."""
        notes, q, how = self.notes, self.cfg.dyn_power, self.cfg.dyn_measure
        att = getattr(self.cfg, "dyn_attention", "extremes")
        n = len(tks)
        rn = self.__dict__.setdefault("rnorm", {})
        N = max((st[0] for st in rn.values()), default=0)  # readings followed by a choice so far
        noted, ratio = self.noted, self.cfg.dyn_ratio
        salient = att.endswith("+saillance")
        if salient:
            # the norm of this reading itself: how many of its dynamics made the same reading
            # (the background repeats — a smooth wall, grass — the animal's contours do not)
            kinds = Counter(self.type_key(r) for r in rk if not self._is_type(r[0]))
            per_degree = Counter()
            for (t, k, _rd, _s), c in kinds.items():
                per_degree[k] += c
        for r in rk:
            says = [sum(self._val(("L", r, x)) for x in t) / max(1, len(t)) for t in tks]
            if not any(says):
                continue
            # attention: a reading almost always there (lower bound of its frequency ≥ dyn_ratio,
            # the « almost always » of the elements) is the same whatever is read: it cannot tell
            # one reading from another
            if N >= 20 and wilson_low(sum(noted.get(("L", r, x), 0) for t in tks for x in t), N) >= ratio:
                continue
            mean = sum(says) / n
            if att != "extremes":
                # « plus une molette est neutre, moins sa voix doit compter » (the user, 2026-11-11):
                # how far from neutral a note is, against what a neutral molette shows after as
                # many tilts of the constant step (a reading of the background, present in every
                # image, moves at every episode and looks far from 0 while it says nothing)
                spread = math.sqrt(sum(self._neutral_var(sum(noted.get(("L", r, x), 0) for x in t)) for t in tks)) / n
            ds, ws = [], []
            for i in range(n):
                # attention: what the reading says of a candidate beyond what it says of every
                # candidate — a reading that says the same of all cannot tell them apart
                d = says[i] - mean
                if how != "pool":
                    w = 1.0
                elif att == "extremes":
                    w = abs(d) ** q
                else:
                    zz = abs(d) / spread if spread > 0 else 0.0
                    w = max(0.0, zz - 1.0) ** q if att == "neutrality-1" else zz ** q
                ds.append(d)
                ws.append(w)
            if salient:  # what is ordinary within this very reading counts less (its surprise there)
                tk = r if self._is_type(r[0]) else self.type_key(r)
                c, tot = kinds.get(tk, 1), per_degree.get(r[1], 1)
                ws = [w * max(0.0, math.log2(max(tot, 1) / max(c, 1))) for w in ws]
            yield r, ds, ws

    @staticmethod
    def _is_type(X) -> bool:
        """Is X a type of dynamics (as ``_type_of`` makes them) rather than a dynamic?"""
        return isinstance(X, tuple) and bool(X) and (X == ("W",) or (X[0] == "M" and len(X) == 4)
                                                       or (X[0] == "E" and len(X) == 3) or (X[0] == "B" and len(X) == 2))

    def _neutral_var(self, n: int) -> float:
        """How much a neutral decision molette's note varies after n tilts of the constant step
        toward outcomes that are +1 or −1 as often (the spread its own history allows)."""
        a = self.cfg.dyn_step
        return a / (2.0 - a) * (1.0 - (1.0 - a) ** (2 * n))

    def chose(self, p: int, i: int | None = None) -> None:
        """The perspective chose among several actions; ``i``: the candidate it took, when the
        reading judged them (its transitions will be joined to the reading at the end)."""
        tr = self.track.get(p)
        if tr is None:
            return
        tr.chose = True
        if i is not None and tr.cand_t is not None:
            tr.choices.append(tr.cand_t[i])
            tr.seen.extend(zip(tr.cand_t, tr.cand_s))
        tr.cand_t = tr.cand_s = None

    # --------------------------------------------------------------- decision
    def judge(self, p: int, cands: list, trace: list | None = None) -> list[float]:
        """Score of each candidate ``(after_obs, final)``: how favourable the dynamics are.

        For each unit and meta molette, the readings the action makes now (source: own) and
        the dynamics the molettes expect the world to make next. Attention: a molette whose
        readings are the same whatever the action cannot tell the actions apart; it is left out.
        """
        cfg, D = self.cfg, self.D
        tr = self.track[p]
        for t in self.track.values():  # the norms read below include the stays of this episode
            if not t.ended:
                self._flush_all(t)
        cur = tr.hist[-1]
        hb = tr.hist[-(D - 1):] if D > 1 else []  # the ticks before the action
        vals = []
        for after, _final in cands:
            moved = [w for w, v in after.items() if tr.obs.get(w) != v]
            touched = {u for w in moved for u in self.by_watcher.get(w, ())}
            vals.append(self.values(after, touched))
        ucache: dict = {}
        self._refs = {}
        if trace is None and cfg.dyn_measure in ("pool", "sum", "mean"):
            scores = self._judge_fast(cands, vals, cur, hb, ucache, self._field_items(tr, cands))
            return self._with_dynamics(tr, cands, scores)
        per: list[list] = [[] for _ in cands]
        tags: list[list] = [[] for _ in cands]
        for u in self.units:
            xs = [v.get(u, cur.get(u)) for v in vals]
            if len(cands) > 1 and all(x == xs[0] for x in xs):
                continue
            for i, x in enumerate(xs):
                got = ucache.get((u, x))
                if got is None:
                    got = ucache[(u, x)] = self._unit_says(hb, u, x)
                per[i].extend(n for _t, n in got)
                if trace is not None:
                    tags[i].extend((u, x, t, n) for t, n in got)
        touched_any = set().union(*vals) if vals else set()
        metas = {m for u in touched_any for m in self.meta_by_unit.get(u, ())}  # the others read the same whatever the action
        for m in sorted(metas, key=self._meta_rank):
            _, k, ms = m
            if k > len(hb) + 1 or (k == 1 and not cfg.dyn_space and not cfg.dyn_project):
                continue
            xs = [tuple(v.get(x, cur.get(x)) for x in ms) for v in vals]
            if len(cands) > 1 and all(x == xs[0] for x in xs):
                continue
            for i, x in enumerate(xs):
                got = ucache.get((m, x))
                if got is None:
                    got = ucache[(m, x)] = self._meta_says(hb, m, x)
                per[i].extend(n for _t, n in got)
                if trace is not None:
                    tags[i].extend((m, x, t, n) for t, n in got)
        extra = self._field_items(tr, cands)
        out = []
        for i, (_after, final) in enumerate(cands):
            per[i].extend(n for _t, n in extra[i])
            if trace is not None:
                tags[i].extend(("field", None, t, n) for t, n in extra[i])
            if final is not None and cfg.use_final:
                out.append(float(final) * 1e6)
            else:
                out.append(self._combine(per[i]))
            if trace is not None:
                trace.append(tags[i])
        return self._with_dynamics(tr, cands, out)

    def _judge_fast(self, cands, vals, cur, hb, ucache, extra=None) -> list[float]:
        """The same scores as ``judge`` for the additive measures, without reading every
        molette for every action: the readings of "everything stays where it is" are summed
        once; each action only swaps in what it changes."""
        cfg, n = self.cfg, len(cands)
        how, q = cfg.dyn_measure, cfg.dyn_power

        pool = how == "pool"
        sq = pool and q == 2.0

        att = cfg.dyn_attention_judge

        def num_den(vs) -> tuple:
            if pool and att:  # the weight of each voice (attention)
                ws = [self._voice_weight(v) for v in vs]
                return sum(v * w for v, w in zip(vs, ws)), sum(ws)
            if sq:
                return sum(v * v * v for v in vs), sum(v * v for v in vs)
            if pool:
                return sum(v * abs(v) ** q for v in vs), sum(abs(v) ** q for v in vs)
            return sum(vs), float(len(vs))

        def says(X, x):
            got = ucache.get((X, x))
            if got is None:
                got = ucache[(X, x)] = [v for _t, v in (self._unit_says(hb, X, x) if not (isinstance(X, tuple) and X[0] == "M") else self._meta_says(hb, X, x))]
            return got

        ndc: dict = {}

        def nd(X, x) -> tuple:  # (numerator, denominator) of what a molette says at x
            got = ndc.get((X, x))
            if got is None:
                got = ndc[(X, x)] = num_den(says(X, x))
            return got

        changes = [{u: x for u, x in v.items() if x != cur.get(u)} for v in vals]
        swaps: list[list] = [[] for _ in cands]  # (stay readings, readings of the action)
        base_num = base_den = 0.0
        by_unit: dict = defaultdict(list)
        for i, ch in enumerate(changes):
            for u, x in ch.items():
                by_unit[u].append((i, x))
        relevant = []
        for u in self.units:  # same order as the plain judge
            lst = by_unit.get(u)
            if not lst or (n > 1 and len(lst) == n and all(x == lst[0][1] for _i, x in lst)):
                continue
            relevant.append(u)
            stay = nd(u, cur.get(u))
            for i, x in lst:
                swaps[i].append((stay, nd(u, x)))
            base_num += stay[0]
            base_den += stay[1]
        rel = set(relevant)
        mrel = {m for u in rel for m in self.meta_by_unit.get(u, ())}
        touched_m: dict = defaultdict(list)  # meta -> actions that change one of its members
        for i, ch in enumerate(changes):
            for m in {m for u in ch for m in self.meta_by_unit.get(u, ()) if m in mrel}:
                touched_m[m].append(i)
        for m in sorted(touched_m, key=self._meta_rank):
            _, k, ms = m
            if k > len(hb) + 1 or (k == 1 and not cfg.dyn_space and not cfg.dyn_project):
                continue
            x0 = tuple(cur.get(x) for x in ms)
            moves = []
            for i in touched_m[m]:
                ch = changes[i]
                xi = tuple(ch.get(x, cur.get(x)) for x in ms)
                if xi != x0:
                    moves.append((i, xi))
            if not moves or (n > 1 and len(moves) == n and all(x == moves[0][1] for _i, x in moves)):
                continue
            stay = nd(m, x0)
            for i, xi in moves:
                swaps[i].append((stay, nd(m, xi)))
            base_num += stay[0]
            base_den += stay[1]
        out = []
        for i, (_after, final) in enumerate(cands):
            if final is not None and cfg.use_final:
                out.append(float(final) * 1e6)
                continue
            num, den = base_num, base_den
            for stay, mine in swaps[i]:
                num += mine[0] - stay[0]
                den += mine[1] - stay[1]
            if extra and extra[i]:
                fn, fd = num_den([n for _t, n in extra[i]])
                num += fn
                den += fd
            if how == "sum":
                out.append(num)
            elif den <= 1e-12:
                out.append(0.0)
            else:
                out.append(num / den)
        return out

    # ------------------------------------------------------------ field derivatives
    def _background(self, obs: dict):
        """The value most of the field holds (empty squares)."""
        return Counter(obs.get(w) for w in self.layout).most_common(1)[0][0]

    def atomic_events(self, before: dict, after: dict, bg) -> list:
        """The change of the field as atomic events (symbol, from, to): from=None is a
        creation, to=GRAVE a departure from the field."""
        left, arrived = defaultdict(list), defaultdict(list)
        for w in self.layout:
            x, y = before.get(w), after.get(w)
            if x != y:
                if x != bg:
                    left[x].append(w)
                if y != bg:
                    arrived[y].append(w)
        ev = []
        for v, targets in arrived.items():
            sources = left.get(v, [])
            for b in targets:
                ev.append((v, sources.pop(0) if sources else None, b))
        for v, sources in left.items():
            ev.extend((v, a, GRAVE) for a in sources)
        return ev

    def _delta(self, a, b) -> tuple:
        cache = self.__dict__.setdefault("_deltas", {})
        d = cache.get((a, b))
        if d is None:
            d = cache[(a, b)] = tuple(y - x for x, y in zip(self.layout[a], self.layout[b]))
        return d

    def _inside(self, a, b) -> tuple:
        """The watchers strictly between a and b on their straight lattice line."""
        got = self._between.get((a, b))
        if got is None:
            d = self._delta(a, b)
            g = math.gcd(*map(abs, d)) if any(d) else 0
            got = ()
            if g > 1:
                step = tuple(x // g for x in d)
                pa = self.layout[a]
                got = tuple(w for w in (self.pos_to_w.get(tuple(x + k * s for x, s in zip(pa, step))) for k in range(1, g))
                            if w is not None)
            self._between[(a, b)] = got
        return got

    def _event_key(self, ev, src):
        v, a, b = ev
        if a is None:
            return ("F", "create", v, src)
        if b == GRAVE:
            return ("F", "grave", v, src)
        return ("F", "move", v, self._delta(a, b), src)

    def _field_tick(self, tr: Track, before: dict, after: dict, src) -> None:
        """Atomic events of this tick (their decision molettes are noted at the end), and the
        norm of every relation of the state before: did its symbol move by Δ onto what stood
        there?"""
        self._fver = self.__dict__.get("_fver", 0) + 1  # the field's dynamics may change: ``begin`` rebuilds them
        bg = self._background(before)
        ev = self.atomic_events(before, after, bg)
        now = len(tr.sig) - 1
        for e in ev:
            tr.fkeys.setdefault(self._event_key(e, src), now)
        # the signal that came with each departure or creation: its immediate pleasure (a norm
        # that converges), what the dynamic minimax adds step by step (it builds the rest itself)
        es = self.__dict__.setdefault("esig", {})
        sig = tr.sig[now] if now >= 0 else 0.0
        for e in ev:
            if e[1] is None or e[2] == GRAVE:
                st = es.setdefault(self._event_key(e, src), [0, 0.0])
                st[0] += 1
                st[1] += (sig - st[1]) / st[0]
        tr.departs = [v for v, _a, b in ev if b == GRAVE]
        fd, dp = self.__dict__.setdefault("fdisp", Counter()), self.__dict__.setdefault("departs", Counter())
        disp = [(v, a, b) for v, a, b in ev if a is not None and b != GRAVE]
        for v, a, b in ev:
            if b == GRAVE:
                dp[v] += 1
        # a displacement seen alone in its event: a way the symbol can go on its own (one seen only
        # with another — a king and a rook at once — is a joint dynamic; so is one onto an empty
        # watcher while a piece departs from another watcher: a pawn taking « en passant »)
        fp = self.__dict__.setdefault("fplace", Counter())
        if len(disp) == 1 and not (before.get(disp[0][2]) == bg and any(b == GRAVE for _v, _a, b in ev)):
            v, a, b = disp[0]
            fd[(v, self._delta(a, b), all(before.get(x) == bg for x in self._inside(a, b)),
                before.get(b) == bg, src)] += 1
            if before.get(b) == bg:  # where it was made: the heatmap of its places (``_place_binding``)
                fp[(v, self._delta(a, b), src, self.layout[a])] += 1
        moved = {(a, b) for _v, a, b in ev if a is not None and b != GRAVE}
        occupied = [w for w in self.layout if before.get(w) != bg]
        # its chances: where each of this side's symbols could have made each displacement it is
        # known to make (onto an empty watcher, free line) — the heatmap ``_place_binding`` reads
        fo = self.__dict__.setdefault("fchance", Counter())
        known = self._moves.get(src, {})
        for w in occupied:
            x = before[w]
            for d, los in known.get(x, ()):
                t = self._shift(w, d)
                if t is not None and before.get(t) == bg and not (los and any(before.get(y) != bg for y in self._inside(w, t))):
                    fo[(x, d, src, self.layout[w])] += 1
        # the relations the field holds after this side's move: which symbol lies within which
        # symbol's capture dynamics, against chance (were the pieces anywhere, how often the
        # watchers each one reaches would hold that symbol) — the heatmap ``_never`` reads
        atts = self._attset
        if self.cfg.dyn_relations and (atts.get(OWN) or atts.get(WORLD)):
            rb, ra, prev = self._follow_relations(tr, before, after, bg)
            keys = self._relation_keys(rb, ra, src, prev)
            if self.cfg.dyn_relation_metas:  # one event changed these relation dynamics together
                keys = self._grow_rmetas(keys, src)
            for k in keys:
                tr.fkeys.setdefault(k, now)
        if atts.get(OWN) or atts.get(WORLD):
            field = {w: after[w] for w in self.layout if after.get(w) != bg}
            n = len(field)
            comp = Counter(field.values())
            ro = self.__dict__.setdefault("rel_seen", Counter())
            rc = self.__dict__.setdefault("rel_chance", Counter())
            for a, x in field.items():
                ds = atts.get(OWN, {}).get(x) or atts.get(WORLD, {}).get(x)
                if not ds or n < 2:
                    continue
                reached = 0
                for d in ds:
                    t = self._shift(a, d)
                    if t is None or t not in field or any(y in field for y in self._inside(a, t)):
                        continue
                    reached += 1
                    ro[(x, field[t], src)] += 1
                if reached:
                    for y, k in comp.items():
                        rc[(x, y, src)] += reached * (k - (y == x)) / (n - 1)
        fc, fm = self.fcount, self.fmove
        for b in occupied:
            w = before[b]
            for a in occupied:
                if a == b:
                    continue
                key = (w, self._delta(b, a), all(before.get(x) == bg for x in self._inside(b, a)), src)
                fc[key] += 1
                if (b, a) in moved:
                    fm[key] += 1

    # a symbol's captures and its displacements onto empty watchers are one dynamic when they share
    # at least this part of their displacements (Jaccard): the pieces of chess ~0.7-1 after 12
    # games, the pawn 0 (it moves straight and takes diagonally)
    SAME_DYNAMIC = 0.6
    FACED = 3  # times a relation was met before a side's move, always ended by it, to be out of norm
    LINE_RUN = 3  # successive distances along a lattice line after which a displacement continues

    def _along_lines(self, ds: set) -> set:
        """A displacement seen at 1, 2, … ``LINE_RUN`` successive distances along one lattice
        direction is one dynamic along that line, like a curve keeping its gradient: it goes on
        to the edge of the field (where the line is free — the line of sight still decides). A
        pawn's two steps forward, a knight's or a king's single ones are not continued."""
        by_dir: dict = defaultdict(set)
        for d in ds:
            g = math.gcd(*map(abs, d)) if any(d) else 0
            if g:
                u = tuple(x // g for x in d)
                if all(abs(x) <= 1 for x in u):
                    by_dir[u].add(g)
        span = self.__dict__.get("_span")
        if span is None:
            xs = list(zip(*self.layout.values()))
            span = self._span = max(max(c) - min(c) for c in xs)
        out = set(ds)
        for u, gs in by_dir.items():
            if all(k in gs for k in range(1, self.LINE_RUN + 1)):
                out.update(tuple(k * x for x in u) for k in range(1, span + 1))
        return out

    def heatmaps(self) -> dict:
        """The field's dynamics as heatmaps (eva/heatmaps.py, the user's definition of 2026-11-12):
        for each symbol, source and what it lands on (an empty watcher or an occupied one), the
        displacements Δ it was seen to make with a free line, by how often. The space is the
        space of the displacements: nothing depends on where on the field they were made."""
        maps: dict = defaultdict(dict)
        for (w, d, los, src), c in self.fmove.items():
            if los and c > 0:
                h = maps[(w, "occupied", src)]
                h[d] = h.get(d, 0) + c
        for (w, d, los, empty, src), c in self.__dict__.get("fdisp", {}).items():
            if los and empty:
                h = maps[(w, "empty", src)]
                h[d] = h.get(d, 0) + c
        return dict(maps)

    def heat_layer(self, metas: bool = False) -> Layer:
        """Molettes (concentrations), transition molettes (the transformations proven between
        them, and what they imply) and, with ``metas``, the meta molettes (intersections) of the
        field's heatmaps; the space is bounded by the field's own extent."""
        cols = list(zip(*self.layout.values()))
        bound = [(-(max(c) - min(c)), max(c) - min(c)) for c in cols]
        return Layer(self.heatmaps(), lattice_transforms(len(cols)), bound=bound, metas=metas)

    def _att_inputs(self) -> tuple:
        """What ``_rebuild_att`` reads: the field's observations (their version, raised by every
        ``_field_tick``) and the settings and constants that shape the dynamics. ``begin`` rebuilds
        only when this changed (a decision without learning in between reads the same dynamics)."""
        c = self.cfg
        return (self.__dict__.get("_fver", 0), c.dyn_field_danger, c.dyn_same_dynamic, c.dyn_explore,
                c.dyn_norm_only, c.dyn_place, c.dyn_never, self.SAME_DYNAMIC, self.LINE_RUN, self.FACED)

    def _rebuild_att(self) -> None:
        """For each symbol, the displacements by which the world moves it onto what stands
        there, with their probability under the norm (smoothed toward the mean rate)."""
        self._att_key = self._att_inputs()
        self._cap_lines = {}  # the capture dynamics laid on the field (``_caps``), for these dynamics
        n = sum(c for k, c in self.fcount.items() if k[3] == WORLD)
        m = sum(c for k, c in self.fmove.items() if k[3] == WORLD)
        p0 = m / n if n else 0.0
        att = defaultdict(list)
        for key, c in self.fcount.items():
            w, d, los, src = key
            if src != WORLD:
                continue
            p = (self.fmove.get(key, 0) + 2 * p0) / (c + 2)
            if self.cfg.dyn_field_danger == "possible":  # the extreme: it has been seen to happen
                if self.fmove.get(key, 0) > 0:
                    att[w].append((d, los, 1.0))
            elif p >= 0.01:
                att[w].append((d, los, p))
        self._att = dict(att)
        # what the perspective's own symbols have been seen to do (the extremes of the
        # relation molettes, own source): the dynamics it can start
        own = defaultdict(list)
        for key, c in self.fmove.items():
            w, d, los, src = key
            if src == OWN and c > 0:
                own[w].append((d, los, 1.0))
        self._att_own = dict(own)
        # where each side's symbols were seen to go onto an empty watcher (their ways out,
        # their ways in between), and the captures as sets for quick reading
        moves: dict = {OWN: defaultdict(set), WORLD: defaultdict(set)}
        for (w, d, los, empty, src), c in self.__dict__.get("fdisp", {}).items():
            if empty:
                moves[src][w].add((d, los))
        if self.cfg.dyn_same_dynamic == "heatmap":  # the transitions proven between heatmaps
            layer = self.heat_layer()
            if self.cfg.dyn_explore == "space":  # where an exploration can look, anchored, space-free
                self._zones, self._hnorm = self._exploration_zones(layer)
            for (w, onto, src) in layer.heatmaps:
                new = layer.implied((w, onto, src))
                if not new:
                    continue
                if onto == "occupied":
                    caps = att if src == WORLD else own
                    old = {d for d, _l, _p in caps.get(w, ())}
                    caps[w].extend((d, True, 1.0) for d in sorted(new - old))
                else:
                    moves[src][w].update((d, True) for d in new)
            if self.cfg.dyn_norm_only:  # out of norm: it happened, but needs its cause (not placed)
                for m in layer.molettes:
                    w, onto, src = m.source
                    out = m.out - layer.implied(m.source)
                    if not out:
                        continue
                    if onto == "occupied":
                        caps = att if src == WORLD else own
                        caps[w] = [x for x in caps.get(w, ()) if x[0] not in out]
                    else:
                        moves[src][w] = {x for x in moves[src][w] if x[0] not in out}
            self._att, self._att_own = dict(att), dict(own)
        elif self.cfg.dyn_same_dynamic:  # one dynamic seen in several contexts (rules by hand)
            for src, caps in ((WORLD, att), (OWN, own)):
                for w, mv in moves[src].items():
                    C = {d for d, los, _p in caps.get(w, ()) if los}
                    M = {d for d, los in mv if los}
                    # read backwards (« les transitions doivent être symétriques »): a symbol seen
                    # making most of its displacements both ways makes each both ways (a pawn: none)
                    U = C | M
                    if U and sum(tuple(-x for x in d) in U for d in U) >= self.SAME_DYNAMIC * len(U):
                        C |= {tuple(-x for x in d) for d in C}
                        M |= {tuple(-x for x in d) for d in M}
                    C, M = self._along_lines(C), self._along_lines(M)
                    # onto an empty watcher / onto an occupied one: its captures are its displacements
                    if C and len(C & M) >= self.SAME_DYNAMIC * len(C | M):
                        C = M = C | M
                    old = {d for d, _l, _p in caps.get(w, ())}
                    if C - old:
                        caps[w].extend((d, True, 1.0) for d in sorted(C - old))
                    mv.update((d, True) for d in M)
            self._att, self._att_own = dict(att), dict(own)
        self._moves = {s: {w: sorted(m) for w, m in ms.items()} for s, ms in moves.items()}
        self._side = {OWN: set(), WORLD: set()}
        for (w, _d, _los, _empty, src) in self.__dict__.get("fdisp", {}):
            self._side[src].add(w)
        self._attset = {WORLD: {w: {d for d, los, _p in xs if los} for w, xs in self._att.items()},
                        OWN: {w: {d for d, los, _p in xs if los} for w, xs in self._att_own.items()}}
        self._bound = self._place_binding() if self.cfg.dyn_place else {}
        self._never = self._never_seen() if self.cfg.dyn_never else {}

    def _place_binding(self) -> dict:
        """Does a dynamic depend on the place where it is made? (the question the user left open,
        2026-11-12: the places answer it.) Each displacement onto an empty watcher has a heatmap
        of the places it was made from; the symbol, a heatmap of where it stood when its side
        moved (its chances). Were the dynamic the same everywhere, it would be made from each
        place in proportion to how often the symbol stood there (where the displacement stays
        inside the field). Along an axis of the field, the places whose coordinate it was never
        made from carry an expected mass: above ``VETO`` (it would have been seen there, P <
        1 %, the veto raised with the number of dynamics read at once), the dynamic is bound, on that
        axis, to the coordinates it was seen at. Its chances are
        counted where it could have been made (the watcher it would reach empty, the line free): a
        king next to its own rook had no chance to go there. A pawn's two steps: only from its first
        row; its one step, a rook's 7: anywhere they fit."""
        seen: dict = defaultdict(Counter)
        for (w, d, src, pos), n in self.__dict__.get("fplace", {}).items():
            seen[(w, d, src)][pos] += n
        chance: dict = defaultdict(Counter)
        for (w, d, src, pos), n in self.__dict__.get("fchance", {}).items():
            chance[(w, d, src)][pos] += n
        bound = {}
        # many dynamics are read at once: each one's veto rises with their number (Bonferroni)
        veto = math.log(max(1, len(seen) * len(next(iter(self.layout.values())))) / CHANCE)
        for (w, d, src), places in seen.items():
            valid = chance.get((w, d, src))
            tot = sum(valid.values()) if valid else 0
            if not tot:
                continue
            rate = min(1.0, sum(places.values()) / tot)
            axes = {}
            for i in range(len(d)):
                vals = {p[i] for p in places}
                if rate * sum(n for p, n in valid.items() if p[i] not in vals) > veto:
                    axes[i] = vals
            if axes:
                bound[(src, w, d)] = axes
        return bound

    def _from(self, src, x, b, d) -> bool:
        """Can ``src``'s symbol x make the displacement d from watcher b? (``_place_binding``)"""
        axes = self._bound.get((src, x, d))
        if not axes:
            return True
        pos = self.layout[b]
        return all(pos[i] in vals for i, vals in axes.items())

    # ------------------------------------------------------------- exploration
    EXPLORE_SAFETY = 0.25  # an exploration stays within this share of the score range below the best

    def norm_favourable(self) -> bool:
        """Is what usually follows a dynamic favourable (the norm of outcomes, ``onorm``)?"""
        return self.__dict__.get("onorm", [0, 0.0])[1] >= 0.0

    def _out_of_norm(self, u, c, x) -> bool:
        """Would unit u going from c to x now be out of its molette's norm (an extreme)?"""
        mol = self.mol.get((u, 1))
        return mol is not None and mol.is_extreme(mol.surprise(c, OWN, x), self.cfg.dyn_extreme_z)

    def unfavourable(self) -> float:
        """How unfavourable the norm of outcomes is, in its own spread: 0 (favourable) to 1."""
        on, tv = self.__dict__.get("onorm", [0, 0.0])[1], self.__dict__.get("tvar", 0.0)
        return 0.0 if on >= 0 or tv <= 0 else min(1.0, -on / math.sqrt(tv))

    def _exploration_zones(self, layer) -> tuple:
        """Where Eva can look beyond a norm, anchored (the user, 2026-11-12: « les méta molettes et
        les molettes de transition, l'intersection et l'union, sont des points d'ancrage »), in the
        space of changes — nothing names a place. For each of her own heatmaps, the cells out of its
        norm that an anchor holds in a norm: a union (a transition molette proven both ways) carries
        them from the other side's norm; an intersection (a concentration of another heatmap sharing
        cells with hers) holds them in its own. The part kept in norm is the safety net.
        Returns ({(heatmap, Δ): anchors}, {heatmap: its norm})."""
        norms: dict = defaultdict(set)
        for m in layer.molettes:
            norms[m.source] |= m.norm
        zones: dict = defaultdict(set)
        for b in layer.bridges:
            if not b.union:
                continue
            for g, t, h in ((b.a, b.t, b.b), (b.b, b.back[0], b.a)):
                H = h.source
                if H[2] != OWN:
                    continue
                for c in g.norm:
                    y = t(c)
                    if y is not None and y not in norms[H] and layer._inside(y):
                        zones[(H, y)].add(("U", g.source, t.name, H))
        ms = layer.molettes
        idx: dict = defaultdict(set)
        for k, m in enumerate(ms):
            for c in m.cells:
                idx[c].add(k)
        for i, A in enumerate(ms):
            if A.source[2] != OWN:
                continue
            for j in set().union(*(idx[c] for c in A.cells)) - {i}:
                B = ms[j]
                if B.source == A.source or len(A.cells.keys() & B.cells.keys()) < 2:
                    continue
                for y in B.norm - norms[A.source]:
                    zones[(A.source, y)].add(("I", A.source, B.source))
        return dict(zones), {k: frozenset(v) for k, v in norms.items()}

    @staticmethod
    def _anchor_type(A) -> tuple:
        """What an anchor is, whatever its symbols: its transformation (union) or the sides it joins
        (intersection), and which of symbol / landing / source its two members share."""
        if A[0] == "U":
            _, g, tname, h = A
            return ("U", tname, g[0] == h[0], g[1] == h[1], g[2] == h[2])
        _, a, b = A
        return ("I", a[0] == b[0], a[1] == b[1], a[2] == b[2])

    def _quantum(self) -> float:
        """The commonest signal's size (what the most frequent departure brought): the scale of the
        smallest usual change of what follows, found by Eva (in the chess domain, a pawn)."""
        es = self.__dict__.get("esig", {})
        if not es:
            return 0.0
        n, mean = max(es.values(), key=lambda v: v[0])
        return abs(mean)

    def explore_space(self, p: int, cands: list, scores: list):
        """« Quand la norme n'est pas favorable, chercher dans le hors norme d'une bonne dynamique
        est acceptable » (the user, 2026-11-12), space-free. Prudence: among the actions whose
        foreseen value (the dynamic minimax over learned dynamics, before the notes) loses at most
        the commonest signal against the action Eva would play — her best itself excluded. A variant
        pushes exactly one dial beyond its norm, the others within theirs (the safety net):
        a displacement beyond its heatmap's norm, into a zone an anchor (a union or an intersection
        of the heat layer) holds in its norm (``_zones``). (Relations rarer than chance were tried
        as dials: against random placement nearly every relation is rare — not a norm.)
        The anchor's promise chooses: its note, started from its type's (what anchors of its kind
        taught), plus optimism that fades as it is tried and grows as the norm worsens; a known-bad
        one is never explored. Without an anchored variant, a prudent one at random. None: nothing is
        prudent (Eva then plays her best)."""
        zones, hnorm = self.__dict__.get("_zones") or {}, self.__dict__.get("_hnorm", {})
        if self.layout is None or not cands or len(cands) < 2:
            return None
        tr = self.track[p]
        a, tv = self.cfg.dyn_step, self.__dict__.get("tvar", 0.0)
        sig = math.sqrt(a / (2.0 - a) * tv) if tv > 0 else 0.0
        q = self._quantum() or sig
        mm = self.__dict__.get("_foreseen", {})
        top = max(range(len(scores)), key=lambda i: scores[i])
        ref = mm.get(top)
        bg = self._background(tr.obs)
        prudent: list = []
        notes = self.__dict__.setdefault("anchor_notes", {})
        tried = self.__dict__.setdefault("anchor_noted", Counter())
        u = self.unfavourable()
        picks = []
        for i, (after, final) in enumerate(cands):
            if i == top or final is not None:
                continue
            if ref is not None and (mm.get(i) is None or mm[i] < ref - q):
                continue  # it foresees losing more than the commonest signal
            if ref is None and scores[i] < scores[top] - sig:
                continue
            outs, anchors = [], []
            for v, x, y in self.atomic_events(tr.obs, after, bg):
                if x is None or y == GRAVE:
                    continue
                H = (v, "empty" if tr.obs.get(y) == bg else "occupied", OWN)
                d = self._delta(x, y)
                if d not in hnorm.get(H, (d,)):
                    outs.append(("D", H, d))
                    anchors = list(zones.get((H, d), ()))
            prudent.append(i)
            if len(outs) != 1 or not anchors:  # one dial beyond its norm, the others within theirs
                continue
            for A in anchors:
                T = self._anchor_type(A)
                W = 1.0 - (1.0 - a) ** tried[A]  # how much of its note is evidence
                promise = notes.get(A, 0.0) + (1.0 - W) * notes.get(T, 0.0) + u * sig * (1.0 - W)
                picks.append((promise, scores[i], -i, i, A, T))
        t = len(tr.sig)
        if picks:
            promise, _s, _n, i, A, T = max(picks)
            if promise >= -sig:  # the most promising is not known to go worse than the norm
                tr.explored.extend([(A, t), (T, t)])
                self.explorations = self.__dict__.get("explorations", 0) + 1
                return i
        if not prudent:
            return None
        # no anchored variant here: a prudent one, at random among those foreseen to lose nothing
        # beyond the commonest signal (its outcome is learned too, as the unanchored kind)
        i = prudent[int(self._rng_draw() * len(prudent))]
        tr.explored.append((("P",), t))
        self.prudent_explorations = self.__dict__.get("prudent_explorations", 0) + 1
        return i

    def _rng_draw(self) -> float:
        rng = self.__dict__.get("_xrng")
        if rng is None:
            import random as _random
            rng = self._xrng = _random.Random(self.cfg.seed + 7)
        return rng.random()

    def explore(self, p: int, cands: list, scores: list):
        """« Quand la norme n'est pas favorable, chercher dans le hors norme d'une bonne dynamique
        est acceptable » ; « choisir des molettes liées par une méta molette et chercher dans une
        des molettes de base des positions hors norme, en laissant une partie dans la norme comme
        filet de sécurité » ; « les méta molettes et les molettes de transition sont des points
        d'ancrage » (the user, 2026-11-12). Among the actions Eva judges near her best (within
        ``EXPLORE_SAFETY`` of the score range: prudence), one whose transition is out of norm for
        exactly one base molette, anchored either by a meta molette over it whose other members
        stay in their norm (the safety net), or by that molette's own transition, a known one
        (its degree-2 reading seen before) going somewhere new. The anchor whose explorations
        went best (its exploration note, learned beyond the norm) and Eva's own judgement choose.
        None: no such action."""
        if not cands or len(cands) < 2:
            return None
        tr = self.track[p]
        cur, hb = tr.hist[-1], tr.hist[-(self.D - 1):] if self.D > 1 else []
        best, worst = max(scores), min(scores)
        floor = best - self.EXPLORE_SAFETY * (best - worst)
        notes = self.__dict__.setdefault("anchor_notes", {})
        picks = []
        for i, (after, _final) in enumerate(cands):
            if scores[i] < floor:
                continue
            moved = [w for w, v in after.items() if tr.obs.get(w) != v]
            touched = {u for w in moved for u in self.by_watcher.get(w, ())}
            vals = self.values(after, touched)
            changed = {u: x for u, x in vals.items() if x != cur.get(u)}
            out = [u for u, x in changed.items() if self._out_of_norm(u, cur.get(u), x)]
            if len(out) != 1:  # one base molette beyond its norm, the others within it
                continue
            u = out[0]
            anchors = [m for m in self.meta_by_unit.get(u, ()) if not any(y in out for y in m[2] if y != u)]
            m2 = self.mol.get((u, 2))
            before = tr.hist[-2].get(u) if len(tr.hist) >= 2 else None  # the transition that led here
            if m2 is not None and before is not None and m2.totals.get(((before, cur.get(u)), OWN), 0) >= 5:
                anchors.append(("T", u))  # a transition it knows, going somewhere new
            if not anchors:
                continue
            m = max(anchors, key=lambda a: notes.get(a, 0.0))
            picks.append((scores[i] + notes.get(m, 0.0), i, m))
        if not picks:
            return None
        _, i, m = max(picks, key=lambda t: (t[0], -t[1]))
        tr.explored.append((m, len(tr.sig)))
        self.explorations = self.__dict__.get("explorations", 0) + 1
        return i

    def relations(self, field: dict) -> set:
        """The field's relations: (x, y) for every symbol y within symbol x's capture dynamics
        (free line) — each placed heatmap's intersection with what stands on the field."""
        atts, out = self._attset, set()
        own, world = atts.get(OWN, {}), atts.get(WORLD, {})
        for a, x in field.items():
            for d in own.get(x) or world.get(x) or ():
                t = self._shift(a, d)
                if t is not None and t in field and not any(z in field for z in self._inside(a, t)):
                    out.add((a, t, x, field[t]))
        return out

    def _relation_keys(self, before: set, after: set, src, prev: set = frozenset()) -> set:
        """What a transition does to the field's relations, space-free: the kinds it creates, the
        kinds it ends, and the kinds the transition before it created that it leaves standing (a
        transition of transitions: the other side made it, this one did not undo it) — decision
        molettes (« R », +/−/=, x, y, source) that generalise: one learned on any square holds on
        every square."""
        made = {("R", "+", x, y, src) for _a, _t, x, y in after - before}
        ended = {("R", "-", x, y, src) for _a, _t, x, y in before - after}
        left = {("R", "=", x, y, src) for _a, _t, x, y in prev & after}
        return made | ended | left

    def _follow_relations(self, tr: Track, before: dict, after: dict, bg) -> tuple:
        """The field's relations before and after a tick, and the ones the tick before it created:
        what a perspective follows in every episode, learning or not. Before 2026-11-13 they were
        followed only while learning: an Eva measured without learning never read the relations the
        world's last move created and her move would leave standing (« = »). RESULTS.md § 36"""
        rb = tr.rels
        if rb is None:
            rb = self.relations({w: before[w] for w in self.layout if before.get(w) != bg})
        ra = self.relations({w: after[w] for w in self.layout if after.get(w) != bg})
        prev = tr.made
        tr.rels, tr.made = ra, ra - rb
        return rb, ra, prev

    # « le mur est juste une molette découverte et notée négativement » (the user, 2026-11-13): the
    # relation dynamics one move makes together more often than chance get a meta molette over them,
    # ``("RM", members)``, an intersection (then intersections of intersections, up to
    # ``dyn_meta_arity`` members), with its own decision molette, born with the mean of its two
    # parents' notes (``dyn_birth_note``) and noted as every reading is. It takes part in a decision
    # when the move makes all its members.
    def _active_rmetas(self, keys) -> list:
        """The relation meta molettes a move activates: all their members among its ``keys``."""
        by = self.__dict__.get("rm_by_key")
        if not by or not self.cfg.dyn_relation_metas:
            return []
        out = []
        for k in keys:
            for rm in by.get(k, ()):  # each one is filed under its first member
                if all(x in keys for x in rm[1]):
                    out.append(rm)
        return out

    def _rel_objects(self, keys) -> set:
        """Relation dynamics as the objects they are (``dyn_relation_unions``): the members of a proven
        union, all made by the move, are that one object; a member made alone stays itself."""
        ru = self.__dict__.get("ru_of")
        if not ru or not self.cfg.dyn_relation_unions:
            return set(keys)
        out = set(keys)
        for k in keys:
            U = ru.get(k)
            if U is not None and k in out and all(x in keys for x in U[1]):
                out.difference_update(U[1])
                out.add(U)
        return out

    def rel_molettes(self, keys) -> set:
        """Every relation molette a move makes (her decision and the analyses read the same ones): its
        relation dynamics as objects (unions), and the intersections they activate."""
        objs = self._rel_objects(keys)
        return objs | set(self._active_rmetas(objs))

    def rel_voice(self, k) -> float:
        """What a relation molette says in a decision: its note; an intersection's, with
        ``dyn_meta_relative``, only what it adds to its parents (« information relative »)."""
        v = self._val(k)
        if self.cfg.dyn_meta_relative and k[0] == "RM":
            v -= self._born_note(0, k)
        return v

    def _is_object(self, X) -> bool:
        """Still one of the relation molettes (a dynamic not inside a union, a union not merged into a
        larger one, an intersection not dropped)."""
        d = self.__dict__
        if X[0] == "RM":
            return X in d.get("rm_origin", {})
        U = d.get("ru_of", {}).get(X[1][0] if X[0] == "RU" else X)
        return U is None if X[0] != "RU" else U == X

    def _drop_rmetas(self, gone) -> None:
        d = self.__dict__
        origin, by = d.get("rm_origin", {}), d.get("rm_by_key", {})
        for rm in [rm for rm in origin if gone(rm)]:
            del origin[rm]
            lst = by.get(rm[1][0])
            if lst and rm in lst:
                lst.remove(rm)

    def _unite(self, X, Y, c: int) -> None:
        """X and Y were never seen one without the other: a proven union, one object (the user,
        2026-11-14), born with the mean of their notes. The intersections over its parts go: they
        were parts of one object, not intersections."""
        d = self.__dict__
        ru, uo = d.setdefault("ru_of", {}), d.setdefault("ru_origin", {})
        mem = tuple(sorted(set(X[1] if X[0] == "RU" else (X,)) | set(Y[1] if Y[0] == "RU" else (Y,)), key=repr))
        U = ("RU", mem)
        uo[U] = (X, Y)
        for m in mem:
            ru[m] = U
        d["rcnt"][U] = c
        ms = set(mem)
        self._drop_rmetas(lambda rm: any(set(x[1] if x[0] == "RU" else (x,)) & ms for x in rm[1]))
        d["unions_made"] = d.get("unions_made", 0) + 1

    def _dissolve(self, U) -> None:
        """One member of union U was made without the others: it was not proven. Its members are
        dynamics of their own again, each with what the union learned."""
        d = self.__dict__
        ru = d.get("ru_of", {})
        for m in U[1]:
            if ru.get(m) == U:
                del ru[m]
            if U in self.notes:
                self.notes[m] = self.notes[U]
        self._drop_rmetas(lambda rm: U in rm[1])
        d["unions_dissolved"] = d.get("unions_dissolved", 0) + 1

    def _grow_rmetas(self, keys: set, src) -> set:
        """One event (a move of ``src``) changed these relation dynamics at once. With
        ``dyn_relation_unions``, members of a union are that one object (a member made alone dissolves
        it). Their co-changes are counted two by two (an object or an intersection with another, never
        sharing a member): two never seen one without the other become one object (a proven union);
        otherwise an intersection is born over a pair as soon as its co-changes pass the meta
        molettes' test against independence (count, lift, z), within ``dyn_relation_metas_max``.
        Returns the relation molettes this move made (objects and the intersections it activated)."""
        cfg = self.cfg
        d = self.__dict__
        cnt, co = d.setdefault("rcnt", Counter()), d.setdefault("rco", Counter())
        ticks = d.setdefault("rticks", Counter())
        origin, by = d.setdefault("rm_origin", {}), d.setdefault("rm_by_key", {})
        unions = cfg.dyn_relation_unions
        if unions:
            ru = d.setdefault("ru_of", {})
            for U in {ru[k] for k in keys if k in ru}:
                if not all(x in keys for x in U[1]):
                    self._dissolve(U)
        objs = self._rel_objects(keys)
        active = self._active_rmetas(objs)
        ticks[src] += 1
        items = sorted(list(objs) + active, key=repr)
        for x in items:
            cnt[x] += 1
        arity, T = cfg.dyn_meta_arity, ticks[src]
        united = False
        for i, X in enumerate(items):
            bx = X[1] if X[0] == "RM" else (X,)
            for Y in items[i + 1:]:
                by_ = Y[1] if Y[0] == "RM" else (Y,)
                if len(bx) + len(by_) > arity or any(b in bx for b in by_):
                    continue
                c = co[(X, Y)] = co[(X, Y)] + 1
                if c < cfg.dyn_meta_min:
                    continue
                if united and not (self._is_object(X) and self._is_object(Y)):
                    continue
                if unions and X[0] != "RM" and Y[0] != "RM" and cnt[X] == c and cnt[Y] == c:
                    self._unite(X, Y, c)  # never one without the other: one object
                    united = True
                    continue
                rm = ("RM", tuple(sorted(bx + by_, key=repr)))
                if rm in origin or len(origin) >= cfg.dyn_relation_metas_max:
                    continue
                e = cnt[X] * cnt[Y] / T
                if e <= 0 or c / e < cfg.meta_min_lift or (c - e) / math.sqrt(e) < cfg.meta_z:
                    continue
                origin[rm] = (X, Y)
                by.setdefault(rm[1][0], []).append(rm)
                cnt[rm] = c  # the ticks all its members were made together: its co-changes
                active.append(rm)
        if united:
            return self.rel_molettes(keys)
        return objs | set(active)

    def _refused(self, tr: Track, tried: dict, signal: float) -> None:
        """A refused action's signal goes to its own molettes only: the atomic events it would
        have made and what it would have done to the field's relations."""
        bg = self._background(tr.obs)
        keys = {self._event_key(e, OWN) for e in self.atomic_events(tr.obs, tried, bg)}
        if self.cfg.dyn_relations and self.layout is not None:
            r0 = tr.rels if tr.rels is not None else self.relations(
                {w: tr.obs[w] for w in self.layout if tr.obs.get(w) != bg})
            r1 = self.relations({w: tried[w] for w in self.layout if tried.get(w) != bg})
            rk = self._relation_keys(r0, r1, OWN, tr.made)
            keys |= self.rel_molettes(rk)
        a, res, notes = self.cfg.dyn_step, self.cfg.resistance, self.notes
        for k in keys:
            v = notes.get(k)
            if v is None:
                v = self._born_note(0, k) if self.cfg.dyn_birth_note else 0.0
            notes[k] = v + a * max(0.0, 1.0 - v * v) ** res * (signal - v)
            self.noted[k] += 1
        self.refusals = self.__dict__.get("refusals", 0) + 1

    def _never_seen(self) -> dict:
        """The meta molettes of the field's relations: after a side's move, symbol y within the
        capture dynamics of symbol x. Their chance mass (``rel_chance``: were the pieces placed
        anywhere, how often the watchers x reaches would hold y) grows with every game. Read as a
        transition (cause → effect): a relation the side met before its move (after the other
        side's: ``FACED`` times at least) and never left after it, where chance expected more than
        ``VETO`` (raised with the number of relations read at once), is one its moves always end
        — out of norm after them. One never met at all is only rare (a queen next to a king in 12
        games): not out of norm, else Eva would never try it and never see it. Nothing names what
        it is: what cannot happen becomes, little by little, what is never seen where it should
        have been. {source: {y: {x: its capture Δs}}}"""
        seen, chance = self.__dict__.get("rel_seen", {}), self.__dict__.get("rel_chance", {})
        veto = math.log(max(1, len(chance)) / CHANCE)  # as many relations read at once (Bonferroni)
        out: dict = {}
        for (x, y, src), e in chance.items():
            faced = seen.get((x, y, WORLD if src == OWN else OWN), 0)
            if e > veto and not seen.get((x, y, src)) and faced >= self.FACED:
                ds = self._attset.get(OWN, {}).get(x) or self._attset.get(WORLD, {}).get(x)
                if ds:
                    out.setdefault(src, {}).setdefault(y, {})[x] = ds
        return out

    def _exposes(self, field: dict, side) -> bool:
        """Would ``field``, made by ``side``'s move, hold a relation never seen after that side's
        moves (``_never_seen``)? Out of norm: that move is not one of its dynamics."""
        nv = self._never.get(side)
        if not nv:
            return False
        return any(self._hit(field, t, nv[y]) for t, y in field.items() if y in nv)

    # ------------------------------------------------------------- dynamic minimax
    def _with_dynamics(self, tr: Track, cands: list, scores: list) -> list:
        """Eva thinks in dynamics, not in moves: an action either continues a dynamic (a
        recapture in an exchange) or creates a transition of dynamics (it starts an exchange,
        a double threat, a sacrifice). It is worth what that dynamic is worth until it ends,
        against the world's worst response — the best dynamic such that the worst possible
        response puts it least in difficulty. The responses are the dynamics the world was
        seen able to make (relation molettes' extremes), applied to Eva's own reading of the
        field: the environment is never stepped. The decision molettes judge whether each
        dynamic is good or bad (« ce sont les molettes de décision qui jugent si une dynamique
        est bonne ou mauvaise »): Eva's action by all of hers (``scores``), each response in
        the tree by the notes of the transition it makes (``_step_value``); the count molettes'
        gradient (what a piece is worth) and the end add to them."""
        if self.layout is None or not self.cfg.dyn_field or self.cfg.dyn_field_decision != "minimax":
            return scores
        bg = self._bg = self._background(tr.obs)
        self._obs_now = tr.obs
        self._memo = {}  # also holds the steps and captures already read during this decision
        out = []
        foreseen: dict = {}  # what the minimax foresees of each candidate, before the notes
        self._foreseen = foreseen
        for (after, final), sc in zip(cands, scores):
            if final is not None and self.cfg.use_final:
                out.append(sc)
                continue
            gain = 0.0
            evs = [e for e in self.atomic_events(tr.obs, after, bg) if e[1] is None or e[2] == GRAVE]
            if self.cfg.dyn_capture_value == "signal":  # what each event brought at once (its signal)
                es = self.__dict__.get("esig", {})
                gain = self._combine([es.get(self._event_key(e, OWN), (0, 0.0))[1] for e in evs])
            elif self.cfg.dyn_capture_value == "event":  # a promotion is one event: its notes are combined
                gain = self._combine([self._val(self._event_key(e, OWN)) for e in evs])
            else:
                for v, a, b in evs:
                    gain += self._slopes.get(v, 0.0) if a is None else -self._slopes.get(v, 0.0)
            field = {w: after[w] for w in self.layout if after.get(w) != bg}
            last = {w: tr.obs.get(w) for w in self.layout if tr.obs.get(w) != after.get(w)}
            value = gain + self._v_world(field, self.cfg.dyn_depth, last)
            foreseen[len(out)] = value
            if not self.cfg.dyn_tiebreak:
                out.append(value)
            elif self.cfg.dyn_minimax_notes:
                out.append(value + sc)
            else:
                out.append(value + 1e-4 * sc)
        return out

    def _shift(self, b, d):
        cache = self.__dict__.setdefault("_shifts", {})
        got = cache.get((b, d), 0)
        if got == 0:
            got = cache[(b, d)] = self.pos_to_w.get(tuple(x + y for x, y in zip(self.layout[b], d)))
        return got

    def _caps(self, field: dict, side) -> list:
        """The capture dynamics ``side`` (OWN: Eva, WORLD) can start in ``field`` (occupied
        watchers only): its symbol at b moves by Δ onto a's occupant — never one of the
        symbols seen moving at its own ticks — which goes to the graveyard. Gain for Eva:
        minus what one more of the departing symbol is worth — or, if that departure is the
        end (never seen without it), what the end is worth, and the dynamic stops there."""
        ckey = (frozenset(field.items()), side)
        seen = self._memo.setdefault("caps", {})  # reset with the memo, at each decision
        got = seen.get(ckey)
        if got is not None:
            return got
        out = []
        att = self._att_own if side == OWN else self._att
        mine = self._side.get(side, ())
        shifts = self.__dict__.setdefault("_shifts", {})
        slopes, term = self._slopes, self._terminal
        by_event = self.cfg.dyn_capture_value == "event"
        by_signal = self.cfg.dyn_capture_value == "signal"
        es = self.__dict__.get("esig", {})
        # each symbol's capture dynamics laid on the field from its watcher, once: the watcher
        # each reaches and the ones it passes over (kept while those dynamics stay the same list)
        lines_of = self.__dict__.setdefault("_cap_lines", {})
        for b, w in field.items():
            lst = att.get(w)
            if not lst:
                continue
            ent = lines_of.get((side, w, b))
            if ent is None or ent[0] is not lst:
                laid = []
                for d, los, _p in lst:
                    a = shifts.get((b, d), 0)
                    if a == 0:
                        a = self._shift(b, d)
                    if a is not None:
                        laid.append((a, los, self._inside(b, a)))
                ent = lines_of[(side, w, b)] = (lst, tuple(laid))
            for a, los, between in ent[1]:
                x = field.get(a)
                if x is None or x in mine:
                    continue
                free = True
                for y in between:
                    if y in field:
                        free = False
                        break
                if free != los:
                    continue
                if self._never.get(side) and x not in term and self._exposes(self._apply(field, b, a), side):
                    continue
                t = term.get(x)
                if t is not None:
                    out.append((t, b, a, True))
                elif by_signal:  # the signal that came with the departure of x at this side's tick
                    out.append((es.get(("F", "grave", x, side), (0, 0.0))[1], b, a, False))
                elif by_event:  # what the departure of x at this side's tick was followed by
                    out.append((self._val(("F", "grave", x, side)), b, a, False))
                else:
                    out.append((-slopes.get(x, 0.0), b, a, False))
        out.sort(key=lambda r: -abs(r[0]))
        got = seen[ckey] = out[: self.cfg.dyn_breadth]
        return got

    @staticmethod
    def _apply(field: dict, b, a) -> dict:
        f = dict(field)
        f[a] = f.pop(b)
        return f

    def _hit(self, field: dict, s, att: dict) -> bool:
        """Some symbol of ``field`` has a capture dynamic onto watcher ``s`` (free line)."""
        for c, w in field.items():
            ds = att.get(w)
            if ds and c != s and self._delta(c, s) in ds and not any(y in field for y in self._inside(c, s)):
                return True
        return False

    def _ray(self, a, u) -> tuple:
        """The watchers from ``a`` (excluded) along the lattice direction ``u``, in order."""
        cache = self.__dict__.setdefault("_rays", {})
        got = cache.get((a, u))
        if got is None:
            x, y = self.layout[a]
            out, k = [], 1
            while True:
                w = self.pos_to_w.get((x + k * u[0], y + k * u[1]))
                if w is None:
                    break
                out.append(w)
                k += 1
            got = cache[(a, u)] = tuple(out)
        return got

    def _opened(self, field: dict, a, side) -> list:
        """The capture dynamics of ``side`` that pass through the empty watcher ``a`` of
        ``field``: a symbol of ``side`` on one side of ``a``, a symbol of the other side on the
        other, nothing else between them, by a displacement ``side`` was seen to capture with.
        While ``a`` was occupied they were held shut: what stood there is part of them — its
        departure is a transition of these dynamics (it unmasks a capture; it exposes a piece
        behind it: the pin). Read in a static field (« un tableau statique peut tout aussi
        contenir des transitions de dynamiques »). Returns [(attacker, target)]."""
        att = self._attset.get(side, {})
        mine = self._side.get(side, ())
        out = []
        for u in self.LATTICE_DIRS:
            p = next((w for w in self._ray(a, u) if w in field), None)
            q = next((w for w in self._ray(a, (-u[0], -u[1])) if w in field), None)
            if p is None or q is None:
                continue
            for c, t in ((p, q), (q, p)):
                if field[c] in mine and field[t] not in mine and self._delta(c, t) in att.get(field[c], ()):
                    out.append((c, t))
        return out

    def _worth(self, x, taker) -> float:
        """What ``taker`` capturing the symbol ``x`` is worth for Eva (as ``_caps`` values it)."""
        t = self._terminal.get(x)
        if t is not None:
            return t
        if self.cfg.dyn_capture_value == "signal":
            return self.__dict__.get("esig", {}).get(("F", "grave", x, taker), (0, 0.0))[1]
        if self.cfg.dyn_capture_value == "event":
            return self._val(("F", "grave", x, taker))
        return -self._slopes.get(x, 0.0)

    def _parry(self, field: dict, a, by: set, mover):
        """How the side ``mover`` parries, in one event, every dynamic aimed at its piece on
        ``a``: its piece leaves — to a watcher its symbol was seen to reach, which no capture
        dynamic of the other side reaches once it has left — or, against one line, one of its
        pieces steps in between. A symbol never seen moving: its ways out are unknown (it can).
        A piece with nowhere to go and no one to step in is « à découvert »: None.

        Otherwise what the parry still costs, for Eva (0: nothing). A way out whose departure
        opens a line of the other side onto another of ``mover``'s pieces (``_opened``) costs
        that piece: the departure changes the dynamics that passed through it (a pinned piece
        cannot leave for free). The cheapest way out is taken."""
        moves = self._moves.get(mover, {})
        x = field[a]
        mv = moves.get(x)
        if mv is None:
            return 0.0
        other = WORLD if mover == OWN else OWN
        att = self._attset.get(other, {})
        lines = self.cfg.dyn_lines
        rest = dict(field)
        del rest[a]
        cost = None
        for d, los in mv:
            s = self._shift(a, d)
            if s is None or s in field or (los and any(y in field for y in self._inside(a, s))):
                continue
            if self._hit(rest, s, att) or not self._from(mover, x, a, d):
                continue
            f2 = dict(rest)
            f2[s] = x
            if self._exposes(f2, mover):
                continue
            if not lines:
                return 0.0
            exposed = [self._worth(f2[t], other) for _c, t in self._opened(f2, a, other)]
            if not exposed:
                return 0.0
            c = max(exposed) if other == OWN else min(exposed)  # the other side takes the best
            if cost is None or (c < cost if other == OWN else c > cost):
                cost = c
        if len(by) == 1:
            between = set(self._inside(next(iter(by)), a))
            if between:
                for c, y in field.items():
                    if c == a:
                        continue
                    for d, los in moves.get(y, ()):
                        s = self._shift(c, d)
                        if s in between and not (los and any(z in field for z in self._inside(c, s))):
                            return 0.0
        return cost

    def _can_parry(self, field: dict, a, by: set, mover) -> bool:
        return self._parry(field, a, by, mover) is not None

    def _after_parry(self, field: dict, threats: dict, mover, best) -> float:
        """What the threats of one side are worth once the other (``mover``) has made its
        quiet response: it parries the most valuable threatened piece if it can — leaving
        changes every dynamic aimed at it at once — and the next one remains (a double threat);
        if it cannot, that threat goes through. A parry that exposes another piece (a pinned
        piece leaving) leaves the threatening side the better of that piece and the next threat,
        unless letting the first threat through costs less. ``best`` is the threatening side's
        choice."""
        if not threats:
            return 0.0
        order = sorted((v for v, _by in threats.values()), reverse=best is max)
        v1 = order[0]
        if (best is max and v1 <= 0) or (best is min and v1 >= 0):
            return 0.0
        rest = order[1] if len(order) > 1 else 0.0
        a1 = next(a for a, (v, _by) in threats.items() if v == v1)
        p = self._parry(field, a1, threats[a1][1], mover)
        if p is None:
            left = v1
        elif best is max:
            left = min(v1, max(rest, p))
        else:
            left = max(v1, min(rest, p))
        return max(0.0, left) if best is max else min(0.0, left)

    def _quiet_threats(self, field: dict, mover, want) -> list:
        """The quiet dynamics of side ``mover`` that aim a capture at a piece whose departure
        is the end (``want`` = whose end it is worth seeking): it moves onto an empty watcher
        it was seen to reach, from which it has a capture dynamic on that piece."""
        term = self._terminal
        targets = [a for a, x in field.items() if x in term and want(term[x])]
        if not targets:
            return []
        moves, att = self._moves.get(mover, {}), self._attset.get(mover, {})
        out = []
        for b, x in field.items():
            mv, ds = moves.get(x), att.get(x)
            if not mv or not ds:
                continue
            for d, los in mv:
                s = self._shift(b, d)
                if s is None or s in field or (los and any(y in field for y in self._inside(b, s))):
                    continue
                if not self._from(mover, x, b, d) or self._exposes(self._apply(field, b, s), mover):
                    continue
                for t in targets:
                    if self._delta(s, t) in ds and not any(y in field and y != b for y in self._inside(s, t)):
                        out.append((b, s))
                        break
        return out[: self.cfg.dyn_breadth]

    def _quiet_dynamics(self, field: dict, mover, want) -> list:
        """The quiet dynamics of side ``mover`` that make a transition of dynamics: one
        displacement onto an empty watcher (one its symbol was seen to make) after which
        capture dynamics exist that did not — from where it arrives, or from another piece of
        its side whose line its departure opens (``_opened``) — and that
        - aims at the piece whose departure is the end (``want``), as ``_quiet_threats``, or
        - creates capture dynamics on two pieces at once (one event, several dynamics: the
          other side can parry only one), or
        - creates one on a piece that cannot leave for free (``_parry``: nowhere to go, or its
          departure would expose another piece — it is pinned).
        Only real threats count (the target is not covered, or is worth more than the piece that
        would take it), and not from a watcher where the other side takes the piece for more than
        it threatens. The most valuable first (``dyn_breadth``)."""
        term = self._terminal
        moves, att = self._moves.get(mover, {}), self._attset.get(mover, {})
        other = OWN if mover == WORLD else WORLD
        att_other = self._attset.get(other, {})
        mine = self._side.get(mover, ())
        out = []
        for b, x in field.items():
            mv = moves.get(x)
            if not mv:
                continue
            ds = att.get(x, ())
            lose_x = abs(self._worth(x, other))  # what the piece is worth if the other side takes it
            for d, los in mv:
                s = self._shift(b, d)
                if s is None or s in field or (los and any(y in field for y in self._inside(b, s))):
                    continue
                if not self._from(mover, x, b, d):
                    continue
                f2 = self._apply(field, b, s)
                if self._exposes(f2, mover):
                    continue
                new: dict = {}
                for dd in ds:
                    t = self._shift(s, dd)
                    if t is None or t not in f2 or f2[t] in mine:
                        continue
                    if not any(y in f2 for y in self._inside(s, t)):
                        new[t] = s  # a new capture dynamic (a piece already aimed at counts: a new attacker)
                for c, t in self._opened(f2, b, mover):
                    new.setdefault(t, c)
                if not new:
                    continue
                # a capture dynamic is a real threat when it gains: the target is not covered by
                # the other side, or is worth more than the piece that would take it (retaken)
                real = {}
                for t, c in new.items():
                    w = abs(self._worth(f2[t], mover))
                    if f2[t] in term or not self._hit(f2, t, att_other) or w > abs(self._worth(f2[c], other)):
                        real[t] = w
                if not real:
                    continue
                end = any(f2[t] in term and want(term[f2[t]]) for t in real)
                best = max(real.values())
                if not end and self._hit(f2, s, att_other) and lose_x >= best:
                    continue  # it arrives where the other side takes it for more than it threatens
                if not end and len(real) < 2:
                    t = next(iter(real))
                    if self._parry(f2, t, {new[t]}, other) == 0.0:
                        continue
                out.append((sum(real.values()) + (2.0 if end else 0.0), b, s))
        out.sort(key=lambda r: -r[0])
        return [(b, s) for _w, b, s in out[: self.cfg.dyn_breadth]]

    def _step_value(self, before: dict, after: dict, last: dict, src, changed=None) -> float:
        """What the decision molettes say of one step of a dynamic (``before`` → ``after``,
        made by ``src``) — all of them, read as the judge reads them for Eva's own action:
        every unit the step changes (watchers, elements) with its readings at every degree,
        their types, what the next dynamic is expected to say (projection), the meta molettes
        over them, and the step's atomic displacements; combined as the judge combines.
        ``last`` holds the watchers the previous step changed, as they were before it (the
        degree-3 readings). Departures are valued by the count molettes (``_caps``). ``changed``:
        the watchers the step changes, when the caller knows them (``_step``: where the symbol
        left and where it arrived) — else found by comparing the two fields."""
        if not self.cfg.dyn_minimax_notes:
            return 0.0
        bg, cfg = self._bg, self.cfg
        if changed is None:
            changed = [w for w in set(before) | set(after) if before.get(w, bg) != after.get(w, bg)]
        # what a step touches depends only on the watchers it changes and on the units and meta
        # molettes that exist: kept until one is born or dissolved (it was rebuilt at every call;
        # keyed by their numbers, the entries of every older shape stayed: 53 212 after 112 games)
        sets = self.__dict__.get("_step_sets")
        if sets is None or self.__dict__.get("_step_sets_ver") != self.__dict__.get("_shape_ver", 0):
            sets = self._step_sets = {}
            self._step_sets_ver = self.__dict__.get("_shape_ver", 0)
        sk = frozenset(changed)
        got_sets = sets.get(sk)
        if got_sets is None:
            if len(sets) > 50_000:
                sets.clear()
            touched = {u for w in changed for u in self.by_watcher.get(w, ())}
            ms = {m for u in touched for m in self.meta_by_unit.get(u, ())}
            need = touched | {x for m in ms for x in m[2]}
            watchers = set()
            for u in need:
                watchers.update(self.uw.get(u, (u,)))
            layout = self.layout or {}
            got_sets = sets[sk] = (touched, ms, need, tuple(sorted(watchers)),
                                   tuple(w in layout for w in sorted(watchers)))
        touched, ms, need, watchers, on_field = got_sets
        now = self._obs_now
        gb, ga, gl, gn = before.get, after.get, last.get, now.get
        parts = []  # (watcher, before, after, before the previous step), in the watchers' order
        for w, f in zip(watchers, on_field):
            x = gb(w, bg) if f else gn(w)
            parts.append((w, x, ga(w, bg), gl(w, x)))
        key = (src, tuple(parts))
        cache = self._memo.setdefault("steps", {})  # reset with the memo, at each decision
        got = cache.get(key)
        if got is not None:
            return got
        ob = {p[0]: p[1] for p in parts}
        oa, o2 = dict(ob), dict(ob)
        for w in changed:
            oa[w] = after.get(w, bg)
        for w, x in last.items():
            if w in o2:
                o2[w] = x
        vb, va = self.values(ob, need), self.values(oa, need)
        hb = [self.values(o2, need), vb][-(self.D - 1):] if self.D > 1 else []
        ns = []
        # what a molette says depends only on its own readings: many steps of one decision make
        # the same ones (nothing is learned during a decision; the memo is emptied at each one)
        says = self._memo.setdefault("says", {})
        for u in touched:
            x = va.get(u)
            if x != vb.get(u):
                sk2 = (u, x, src, tuple(h.get(u) for h in hb))
                got2 = says.get(sk2)
                if got2 is None:
                    got2 = says[sk2] = [n for _t, n in self._unit_says(hb, u, x, src)]
                ns.extend(got2)
        for m in ms:
            _, k, mem = m
            if k > len(hb) + 1 or (k == 1 and not cfg.dyn_space and not cfg.dyn_project):
                continue
            xm = tuple(va.get(y) for y in mem)
            if xm != tuple(vb.get(y) for y in mem):
                sk2 = (m, xm, src, tuple(tuple(h.get(a) for h in hb) for a in mem))
                got2 = says.get(sk2)
                if got2 is None:
                    got2 = says[sk2] = [n for _t, n in self._meta_says(hb, m, xm, src)]
                ns.extend(got2)
        moved_from = [w for w in changed if before.get(w, bg) != bg and after.get(w, bg) == bg]
        for a in moved_from:
            for b in changed:
                if b != a and after.get(b) == before.get(a):  # the displacement of a symbol
                    ns.append(self._val(("F", "move", before[a], self._delta(a, b), src)))
        got = cache[key] = self._combine(ns)
        return got

    def _step(self, field: dict, b, a, last: dict, src) -> tuple:
        """One step of a dynamic: ``src``'s symbol on b moves to a. The field after it, what
        the decision molettes say of it, and what the next step reads as « before »."""
        after = self._apply(field, b, a)
        bg = self._bg
        return after, self._step_value(field, after, last, src, (b, a)), {b: field.get(b, bg), a: field.get(a, bg)}

    def _then_world(self, field: dict, d: int, last: dict) -> float:
        """What follows a capture, the world to move. At the horizon (no step left) the
        dynamic is still judged to the reply that follows it: the world's best immediate
        capture, or nothing — a piece taken where it is defended is not a clean gain."""
        if d >= 1:
            return self._v_world(field, d, last)
        best = 0.0
        for g, b, a, _e in self._caps(field, WORLD):
            _after, t, _l = self._step(field, b, a, last, WORLD)
            best = min(best, g + t)
        return best

    def _then_own(self, field: dict, d: int, last: dict) -> float:
        """The same, Eva to move: her best immediate capture, or nothing."""
        if d >= 1:
            return self._v_own(field, d, last)
        best = 0.0
        for g, b, a, _e in self._caps(field, OWN):
            _after, t, _l = self._step(field, b, a, last, OWN)
            best = max(best, g + t)
        return best

    def _v_world(self, field: dict, d: int, last: dict | None = None) -> float:
        """Value for Eva of the dynamics that follow, the world to move: it takes (a capture
        dynamic), it aims a quiet dynamic at the piece whose departure ends Eva's game, or it
        parries the most valuable of Eva's threats — the threatened piece leaves, which
        changes every dynamic aimed at it; a double threat on two pieces still leaves the
        second one; a piece that cannot be parried is lost. Each step is worth what the
        decision molettes say of it, plus what it takes. The world chooses what is worst for
        Eva."""
        if d <= 0:
            return 0.0
        last = last or {}
        key = (frozenset(field.items()), frozenset(last.items()), 0, d)
        got = self._memo.get(key)
        if got is not None:
            return got
        opts = []
        for g, b, a, end in self._caps(field, WORLD):
            after, t, nl = self._step(field, b, a, last, WORLD)
            opts.append(g + t if end else g + t + self._then_own(after, d - 1, nl))
        if d >= 2:  # the world's quiet dynamics that make a transition of dynamics (Eva's: the end only,
            # her own are all judged at the root — deeper they would multiply the cost)
            quiet = self._quiet_dynamics if self.cfg.dyn_lines else self._quiet_threats
            for b, s in quiet(field, WORLD, lambda t: t < 0):
                after, t, nl = self._step(field, b, s, last, WORLD)
                opts.append(t + self._v_own(after, d - 1, nl))
        mine: dict = {}
        for g, b, a, end in self._caps(field, OWN):
            after, t, nl = self._step(field, b, a, last, OWN)
            v = g + t if end else g + t + self._then_world(after, d - 2, nl)
            cur = mine.get(a)
            if cur is None:
                mine[a] = [v, {b}]
            else:
                cur[0] = max(cur[0], v)
                cur[1].add(b)
        quiet = self._after_parry(field, mine, WORLD, max)
        got = self._memo[key] = min([quiet] + opts)
        return got

    def _v_own(self, field: dict, d: int, last: dict | None = None) -> float:
        """The same, Eva to move: she starts the best capture dynamic or quiet dynamic on the
        piece whose departure ends the world's game, or parries the world's worst threat (its
        second one remains; one she cannot parry goes through)."""
        if d <= 0:
            return 0.0
        last = last or {}
        key = (frozenset(field.items()), frozenset(last.items()), 1, d)
        got = self._memo.get(key)
        if got is not None:
            return got
        opts = []
        for g, b, a, end in self._caps(field, OWN):
            after, t, nl = self._step(field, b, a, last, OWN)
            opts.append(g + t if end else g + t + self._then_world(after, d - 1, nl))
        if d >= 2:
            for b, s in self._quiet_threats(field, OWN, lambda t: t > 0):
                after, t, nl = self._step(field, b, s, last, OWN)
                opts.append(t + self._v_world(after, d - 1, nl))
        theirs: dict = {}
        for g, b, a, end in self._caps(field, WORLD):
            after, t, nl = self._step(field, b, a, last, WORLD)
            v = g + t if end else g + t + self._then_own(after, d - 2, nl)
            cur = theirs.get(a)
            if cur is None:
                theirs[a] = [v, {b}]
            else:
                cur[0] = min(cur[0], v)
                cur[1].add(b)
        quiet = self._after_parry(field, theirs, OWN, min)
        got = self._memo[key] = max([quiet] + opts)
        return got

    def _count_keys(self, tr: Track) -> set:
        """The count of each symbol where the episode stops (the integral of the atomic
        events): its decision molette, one note per level."""
        bg = self._background(tr.obs)
        final = Counter(tr.obs.get(w) for w in self.layout)
        symbols = {tr.start.get(w) for w in self.layout} | set(final)
        return {("F", "count", v, final.get(v, 0), "end") for v in symbols if v != bg}

    def _rebuild_slopes(self) -> None:
        """The gradient of each count molette's note along the count: what one more of that
        symbol is worth (the mean difference between adjacent levels, weighted by how often
        both were noted)."""
        levels: dict = defaultdict(dict)
        for key, v in self.notes.items():
            if key[0] == "F" and key[1] == "count":
                n = self.noted.get(key, 0)
                if self.cfg.dyn_debias and n:  # what the outcomes said, not how often they said it
                    v = v / self._reach(n)
                levels[key[2]][key[3]] = (v, n)
        slopes = {}
        for sym, lv in levels.items():
            num = den = 0.0
            for c, (v, n) in lv.items():
                lower = lv.get(c - 1)
                if lower is None:
                    continue
                w = min(n, lower[1])
                num += w * (v - lower[0])
                den += w
            slopes[sym] = num / den if den else 0.0
        self._slopes = slopes
        # a departure never seen without the end following it is the end: it is worth what
        # the end it brought was worth (the outcome is an event, the last one)
        dp = self.__dict__.get("departs", {})
        self._terminal = {v: max(-1.0, min(1.0, sr / n)) for v, (n, sr) in self.__dict__.get("ends", {}).items()
                          if self.cfg.dyn_ends and n >= 1 and n >= dp.get(v, 0)}

    def _reach(self, n: int) -> float:
        """How far a note can have moved from neutral after ``n`` tilts all toward the same
        outcome (the tilt rule of ``learn``). A note that has seen the same outcome ``n``
        times is ``reach(n)`` times that outcome: a level noted more often is further from
        neutral even if the outcome never depended on it. Read against its reach, a note says
        what the outcomes said, whatever how often it was noted (with every game lost, every
        level says −1 and no piece gets a value it never earned)."""
        z = self.__dict__.setdefault("_reaches", [0.0])
        a, res = self.cfg.dyn_step, self.cfg.resistance
        while len(z) <= n:
            x = z[-1]
            z.append(x + a * max(0.0, 1.0 - x * x) ** res * (1.0 - x))
        return z[n] or 1.0

    LATTICE_DIRS = ((1, 0), (0, 1), (1, 1), (1, -1))  # →, ↑, ↗, ↘; the opposite ones read them backwards

    def field_readings(self, obs: dict, around=None) -> list:
        """« Même le tableau statique peut avoir les transitions de dynamique : le tableau raconte
        une histoire » (the user, 2026-11-11). The field is read as an image is (RESULTS.md § 14):
        along each lattice direction δ, a watcher and the next one make a transition (degree 2:
        (A, B), the first degree of transition of the base molettes), and three in a row a
        transition of transitions (degree 3: (A, B, C), the transitions of the first degree's).
        Keys ``(("B", watcher, δ), k, reading, OWN)``: where the reading starts and which way; its
        type ``("B", δ)`` holds wherever it is. Readings made only of background are left out.
        ``around``: only the readings that pass through these watchers (what an action changes)."""
        lay, pos, bg = self.layout, self.pos_to_w, self._bg
        starts = None
        if around is not None:
            starts = set()
            for w in around:
                x, y = lay[w]
                for d in self.LATTICE_DIRS:
                    for back in (0, 1, 2):
                        s_ = pos.get((x - back * d[0], y - back * d[1]))
                        if s_ is not None:
                            starts.add((s_, d))
        out = []
        for w, (x, y) in lay.items():
            for d in self.LATTICE_DIRS:
                if starts is not None and (w, d) not in starts:
                    continue
                b = pos.get((x + d[0], y + d[1]))
                if b is None:
                    continue
                A, B = obs.get(w), obs.get(b)
                if A == bg and B == bg:
                    continue
                out.append((("B", w, d), 2, (A, B), OWN))
                c = pos.get((x + 2 * d[0], y + 2 * d[1]))
                if c is not None:
                    out.append((("B", w, d), 3, (A, B, obs.get(c)), OWN))
        return out

    def _field_items(self, tr: Track, cands: list) -> list:
        """What the field says of each action: the notes of the atomic events it makes, and for
        every occupied watcher the chance that the world moves something onto it next (its
        occupant goes to the graveyard) times the note of that departure. Danger the same for
        every action cannot tell them apart: it is left out (attention)."""
        if self.layout is None or not self.cfg.dyn_field:
            return [[] for _ in cands]
        notes = self.notes
        bg = self._background(tr.obs)
        by_count = self.cfg.dyn_field_value == "count"
        if self.cfg.dyn_field_decision == "minimax":  # captures and danger: the dynamic minimax
            out = [[("ev", self._val(self._event_key(e, OWN))) for e in self.atomic_events(tr.obs, after, bg)
                    if e[1] is not None and e[2] != GRAVE] for after, _f in cands]
            if self.cfg.dyn_relations:  # what each action does to the field's relations
                r0 = self.relations({w: tr.obs[w] for w in self.layout if tr.obs.get(w) != bg})
                for i, (after, _f) in enumerate(cands):
                    r1 = self.relations({w: after[w] for w in self.layout if after.get(w) != bg})
                    ks = self.rel_molettes(self._relation_keys(r0, r1, OWN, tr.made))  # unions, intersections
                    out[i].extend(("rel", self.rel_voice(k)) for k in ks)
            if self.cfg.dyn_story:
                self._bg = bg
                for i, (after, _f) in enumerate(cands):
                    moved = [w for w in self.layout if after.get(w) != tr.obs.get(w)]
                    for key in self.field_readings(after, around=moved):
                        for v in self._views():
                            out[i].append(("story", self._note(v, key)))
            return out
        own, danger = [], []
        for after, _final in cands:
            items = []
            for e in self.atomic_events(tr.obs, after, bg):
                if by_count and e[1] is None:  # a creation: one more of that symbol
                    items.append(("ev", self._slopes.get(e[0], 0.0)))
                elif by_count and e[2] == GRAVE:  # a departure: one less of that symbol
                    items.append(("ev", -self._slopes.get(e[0], 0.0)))
                else:
                    items.append(("ev", self._val(self._event_key(e, OWN))))
            own.append(items)
            q: dict = {}
            occupied = [w for w in self.layout if after.get(w) != bg]
            for b in occupied:
                pb = self.layout[b]
                for d, los, p in self._att.get(after[b], ()):
                    a = self.pos_to_w.get(tuple(x + y for x, y in zip(pb, d)))
                    if a is None or after.get(a) == bg:
                        continue
                    if all(after.get(x) == bg for x in self._inside(b, a)) != los:
                        continue
                    q[a] = q.get(a, 1.0) * (1.0 - p)
            danger.append({a: (after[a], 1.0 - qa) for a, qa in q.items() if qa < 0.99})
        out = []
        for i in range(len(cands)):
            items = list(own[i])
            for a, (v, pa) in danger[i].items():
                if len(cands) > 1 and all(dj.get(a) == (v, pa) for dj in danger):
                    continue
                worth = -self._slopes.get(v, 0.0) if by_count else self._val(("F", "grave", v, WORLD))
                items.append(("danger", pa * worth))
            out.append(items)
        return out

    # Each reading is read by the molette of its unit and by the molette of its *type* of
    # dynamics (units with the same shape of dynamics: what is learned of one holds for all).
    def _type_of(self, X):
        t = self.types.get(X)
        if t is None:
            if isinstance(X, str):
                t = ("W",)
            elif X[0] == "E":
                t = ("E", len(X[1]), frozenset(n for _w, _o, n in X[1]))
            elif X[0] == "B":  # a reading of the static field: its type is its direction
                t = ("B", X[2])
            else:
                _, k, ms = X
                uw = self.uw
                shared = tuple(sorted(len(uw[a] & uw[b]) for a, b in combinations(ms, 2)))
                t = ("M", k, tuple(sorted((self._type_of(a) for a in ms), key=repr)), shared)
            self.types[X] = t
        return t

    def _order(self, m, r) -> list:
        """The members of a meta molette in the order of its type: by type, then by how many
        other members they cross, then by reading (members with the same role are
        interchangeable)."""
        ms, uw = m[2], self.uw
        key = self.__dict__.setdefault("_roles", {}).get(m)
        if key is None:
            key = self._roles[m] = [(repr(self._type_of(a)), sum(1 for b in ms if b != a and uw[a] & uw[b])) for a in ms]
        return sorted(range(len(ms)), key=lambda i: (key[i], repr(r[i])))

    def _meta_rank(self, m) -> int:
        """Meta molettes in the order they were born (the same order as before)."""
        rank = self.__dict__.setdefault("_mrank", {})
        if len(rank) != len(self.metas):
            rank.clear()
            rank.update((x, i) for i, x in enumerate(self.metas))
        return rank.get(m, 0)

    def type_key(self, key):
        cache = self.__dict__.setdefault("_tkeys", {})
        got = cache.get(key)
        if got is None:
            if len(cache) > 200_000:  # a cache: bounded (2 000 000 held 325 MB at 737 147, § 25)
                cache.clear()
            got = cache[key] = self._type_key(key)
        return got

    def _type_key(self, key):
        X, k, r, src = key
        t = self._type_of(X)
        if t[0] == "M" and r is not None:
            r = tuple(r[i] for i in self._order(X, r))
        return (t, k, r, src)

    def _canon(self, m, r, nxt):
        """A meta molette's joint reading and next joint value in the order of its type."""
        o = self._order(m, r)
        return tuple(r[i] for i in o), tuple(nxt[i] for i in o)

    def _views(self) -> tuple:
        t = self.cfg.dyn_types
        return (0,) if t == "off" else (1,) if t == "type" else (0, 1)

    def _val(self, k) -> float:
        """A decision molette's note as a decision reads it. With ``dyn_proven`` (« à une certaine
        étape, un sous-ensemble des molettes est activé ; ce sont celles-là qui participent »), only
        a note proven beyond chance takes part: farther from 0 than a neutral molette's note wanders
        after as many tilts (CHANCE, two-sided); the others are silent. Learning is not touched.
        A meta molette's note never tilted yet is its birth note (``dyn_birth_note``)."""
        v = self.notes.get(k)
        if v is None:
            v = self._born_note(0, k) if self.cfg.dyn_birth_note else 0.0
        if v and self.cfg.dyn_proven:
            sp = math.sqrt(self._neutral_var(self.noted.get(k, 0)) * self.__dict__.get("tvar", 1.0))
            if abs(v) <= PROOF_Z * sp:
                return 0.0
        return v

    def _parents(self, key) -> tuple:
        """The decision molettes of the two dynamics a meta molette was born from (« les molettes qui
        l'ont engendrée »), at the same reading: a unit's reading, or a meta molette's over its own
        members. A relation meta molette's: the relation dynamics (or relation meta molettes) it was
        born over. Any other molette was not born of others: ()."""
        if not isinstance(key, tuple) or not key:
            return ()
        if key[0] == "RM":
            return self.__dict__.get("rm_origin", {}).get(key, ())
        if key[0] == "RU":
            return self.__dict__.get("ru_origin", {}).get(key, ())
        m = key[0]
        if len(key) != 4 or not isinstance(m, tuple) or len(m) != 3 or m[0] != "M":
            return ()
        pair = self.__dict__.get("meta_origin", {}).get(m)
        if pair is None and m not in self.meta_set:
            return ()
        _m, k, r, src = key
        ms = m[2]
        if r is None or len(r) != len(ms):
            return ()
        idx = {x: i for i, x in enumerate(ms)}
        out = []
        for P in ((pair[1], pair[2]) if pair else ms):
            if isinstance(P, tuple) and P and P[0] == "M":
                if not all(x in idx for x in P[2]):
                    return ()
                out.append((P, k, tuple(r[idx[x]] for x in P[2]), src))
            elif P in idx:
                out.append((P, k, r[idx[P]], src))
            else:
                return ()
        return tuple(out)

    def _born_note(self, view: int, key) -> float:
        """The note a meta molette's decision molette is born with (``dyn_birth_note``): the mean of
        the notes of the molettes it was born from, at the same reading (view 1: of their types);
        one of them never tilted either gives its own birth note. 0 for a molette born of none."""
        ps = self._parents(key)
        if not ps:
            return 0.0
        notes, tot = self.notes, 0.0
        for p in ps:
            k = p if view == 0 else self.type_key(p)
            v = notes.get(k)
            tot += v if v is not None else self._born_note(view, p)
        return tot / len(ps)

    def _note(self, view: int, key) -> float:
        k = key if view == 0 else self.type_key(key)
        if view and self.cfg.dyn_birth_note and k not in self.notes:
            v = self._born_note(1, key)
        else:
            v = self._val(k)
        if v and self.cfg.dyn_attention_judge:
            # « plus une molette est neutre moins sa voix doit compter »: the weight of its voice is
            # how far from neutral the note is, against what a neutral molette shows after as many
            # tilts (a note that every episode moves wanders far from 0 while saying nothing)
            sp = math.sqrt(self._neutral_var(self.noted.get(k, 0)) * self.__dict__.get("tvar", 1.0))
            out = Voice(v)
            out.w = (abs(v) / sp) ** self.cfg.dyn_power if sp > 0 else 0.0
            return out
        return v

    def _voice_weight(self, v) -> float:
        """The weight of a value in the pool: a Voice's own weight; with the attention on, any
        other value (an expected note, an event's note) as if seen by a saturated molette."""
        w = getattr(v, "w", None)
        if w is not None:
            return w
        q = self.cfg.dyn_power
        if self.cfg.dyn_attention_judge:
            sp = math.sqrt(self.cfg.dyn_step / (2.0 - self.cfg.dyn_step) * self.__dict__.get("tvar", 1.0))
            return (abs(v) / sp) ** q if sp > 0 else 0.0
        return abs(v) ** q

    def _unit_says(self, hb: list, u, x, src=OWN) -> list[tuple]:
        """Notes of the readings a unit makes if it goes to ``x`` now, and of the dynamics
        its molettes expect the world to make next: ``(what, note)`` pairs. With
        ``cfg.dyn_relative`` each is read against the norm: what it says beyond what the
        molette expected the action to bring (its own norm before the action)."""
        D, cfg, note = self.D, self.cfg, self._note
        top = min(D, len(hb) + 1)
        nxt = WORLD if src == OWN else OWN  # who makes the next dynamic

        def rk(k, y):  # the degree-k reading if the unit goes to y now
            if k == 1:
                return y
            if k == 2:
                return (hb[-1].get(u), y)
            return tuple(h.get(u) for h in hb[-(k - 1):]) + (y,)

        def proj(v, k, y):  # what the world's next dynamic says, from the degree-k reading
            r = rk(k, y)
            mol = self.mol.get((u, k) if v == 0 or not cfg.dyn_type_norm else (self._type_of(u), k))
            dist = mol.dist(r, nxt) if mol else None
            if not dist or (cfg.dyn_alive and set(dist) == {y}):  # a frozen dynamic says nothing of the future
                return None
            return self._expect(dist, lambda z: note(v, (u, k + 1, (r, z) if k == 1 else r + (z,), nxt)))

        out = []
        for v in self._views():
            for k in range(1 if cfg.dyn_space else 2, top + 1):
                n = note(v, (u, k, rk(k, x), src))
                if cfg.dyn_relative and k >= 2:
                    n -= self._ref(("own", v, u, k), lambda k=k: self._norm_mean(hb, u, k, lambda y: note(v, (u, k, rk(k, y), OWN))))
                out.append((f"{'t' if v else ''}{k}", n))
            if cfg.dyn_project:
                for k in range(1, min(D - 1, top) + 1):
                    e = proj(v, k, x)
                    if e is None:
                        continue
                    if cfg.dyn_relative:
                        e -= self._ref(("proj", v, u, k), lambda k=k: self._norm_mean(hb, u, max(2, k), lambda y: proj(v, k, y) or 0.0))
                    out.append((f"{'t' if v else ''}w{k + 1}", e))
        return out

    def _ref(self, key, fn) -> float:
        got = self._refs.get(key)
        if got is None:
            got = self._refs[key] = fn()
        return got

    def _norm_mean(self, hb: list, u, k: int, value) -> float:
        """What the own norm expects of ``value(y)``: y is the unit's next value after the
        degree-(k-1) reading before the action (0 if the norm has never seen it)."""
        if not hb:
            return 0.0
        rd = hb[-1].get(u) if k == 2 else tuple(h.get(u) for h in hb[-(k - 1):])
        mol = self.mol.get((u, k - 1))
        dist = mol.dist(rd, OWN) if mol else None
        if not dist:
            return 0.0
        return sum(q * value(y) for y, q in dist.items())

    def _meta_says(self, hb: list, m, x, src=OWN) -> list[tuple]:
        """The same for a meta molette: its joint reading now, and the joint dynamics the
        norm expects next (noted by the meta molette of the next degree). With
        ``dyn_meta_relative`` each says only what it adds to its parents (« information relative »)."""
        D, cfg, note = self.D, self.cfg, self._note
        if cfg.dyn_meta_relative:
            whole = note

            def note(v, key):
                return whole(v, key) - self._born_note(v, key)
        _, k, ms = m
        if k == 1:
            r = x
            parts = tuple((xi,) for xi in x)
        else:
            parts = tuple(tuple(h.get(a) for h in hb[-(k - 1):]) + (xi,) for a, xi in zip(ms, x))
            r = parts
        out = []
        views = self._views()
        nxt = WORLD if src == OWN else OWN
        if k > 1 or cfg.dyn_space:
            for v in views:
                out.append((f"{'t' if v else ''}{k}", note(v, (m, k, r, src))))
        if cfg.dyn_project and k < D:
            nm = ("M", k + 1, ms)
            born = nm in self.meta_set
            for v in views:
                if v == 0 and not born:  # the joint dynamic is noted by the next degree's meta molette
                    continue
                if v == 1 and cfg.dyn_type_norm:  # the norm of the type of dynamics
                    o = self._order(m, r)
                    rr, cx = tuple(r[i] for i in o), tuple(x[i] for i in o)
                    pp = tuple(parts[i] for i in o)
                    mol = self.mol.get((self._type_of(m), k))
                else:
                    mol, rr, cx, pp = self.mol.get((m, k)), r, x, parts
                dist = mol.dist(rr, nxt) if mol else None
                if not dist or (cfg.dyn_alive and set(dist) == {cx}):
                    continue
                out.append((f"{'t' if v else ''}w{k + 1}", self._expect(
                    dist, lambda y: note(v, (nm, k + 1, tuple(pi + (yi,) for pi, yi in zip(pp, y)), nxt)))))
        return out

    def _expect(self, dist: dict, note) -> float:
        """What the world's next dynamic says: its expectation under the norm, pulled toward
        the worst possible one by ``cfg.dyn_risk``."""
        e, worst = 0.0, 1.0
        for y, q in dist.items():
            n = note(y)
            e += q * n
            if n < worst:
                worst = n
        risk = self.cfg.dyn_risk
        return e if not risk else (1 - risk) * e + risk * min(e, worst)

    def _combine(self, xs: list) -> float:
        how, q = self.cfg.dyn_measure, self.cfg.dyn_power
        if not xs:
            return 0.0
        if how == "sum":
            return sum(xs)
        if how == "mean":
            return sum(xs) / len(xs)
        if how == "pool":  # the extremes weigh the most; nothing is counted twice
            w = [self._voice_weight(x) for x in xs] if self.cfg.dyn_attention_judge else [abs(x) ** q for x in xs]
            s = sum(w)
            return sum(x * wi for x, wi in zip(xs, w)) / s if s > 0 else 0.0
        if how == "worst":  # the worst dynamic first, the best one breaks ties
            return min(xs) + 1e-3 * max(xs)
        raise ValueError(how)

    # ------------------------------------------------------------------ misc
    def stats(self) -> dict:
        per, arity = defaultdict(int), defaultdict(int)
        for m in self.metas:
            per[m[1]] += 1
            arity[len(m[2])] += 1
        return {
            "units": len(self.units),
            "elements": len(self.steps),
            "elements_dissolved": self.dissolved,
            "meta_molettes": dict(sorted(per.items())),
            "meta_arity": dict(sorted(arity.items())),
            "molettes": len(self.mol),
            "extremes_seen": sum(m.extremes for m in self.mol.values()),
            "notes": len(self.notes),
            "statistical_entries": sum(m.size() for m in self.mol.values()),
            "ends": dict(self.__dict__.get("_terminal", {})),  # departures that are the end
        }
