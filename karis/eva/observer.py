"""Observer: every channel of Eva, base watchers and meta molettes (n9, n12).

The observer receives one observation ``dict[watcher, value]`` per tick and per p.
It creates a base ``Channel`` for each watcher it meets, and a meta ``Channel`` for each
group of channels the ``CorrelationTracker`` finds correlated. A meta channel's value is
the tuple of its members' values, so it carries a distribution over combinations (meta
molette standard) and, being a channel, its own time molette and N-time hierarchy (meta
molettes de temps).
"""

from __future__ import annotations

import math
from collections import defaultdict, deque
from typing import Callable, Hashable

from .molettes import Channel, Cursor
from .discovery import discover as discover_lens, is_raw_number
from .construction import ConstructionTracker, MTrans, PairTracker, Summary, _pair, live_value, footprint, element_class, element_name, magnitude, members, unit_name, unit_value, unit_values
from .sequences import SequenceTracker, advance

Name = Hashable  # a watcher name (str) or a meta name (tuple of watcher names)


def chain_name(C: tuple) -> tuple:
    """Channel name of a chain molette (kept apart from the meta molettes)."""
    return ("~chain", C)


def members_of(name: Name) -> tuple[str, ...]:
    return name if isinstance(name, tuple) else (name,)


class CorrelationTracker:
    """Finds channels whose changes are correlated.

    Two criteria, both cheap and sparse:

    - *timing*: a and b change within ``window`` ticks of each other far more often than
      independence predicts (lift and z-score): two things that move together.
    - *content*: a and b nearly always change together (so timing says nothing) but the
      transition of one tells a lot about the transition of the other (mutual information,
      bias-corrected). Typical of a shift register (a value handed from one watcher to
      the next).
    """

    def __init__(self, cfg):
        self.cfg = cfg
        self.ticks = 0
        self.n: dict[Name, float] = defaultdict(float)
        self.co: dict[tuple, float] = defaultdict(float)
        # Changes of the previous ticks, per perspective: window 1 = same tick only.
        self.recent: dict[int, deque] = {}
        self.joint: dict[tuple, dict] = {}  # pair -> {(ta, tb): count}
        self.rejected: set[tuple] = set()

    @staticmethod
    def _key(a: Name, b: Name) -> tuple:
        return (a, b) if repr(a) <= repr(b) else (b, a)

    def observe(self, changed: dict[Name, tuple], p: int = 0) -> None:
        """``changed`` maps each channel that changed at this tick to its transition."""
        self.ticks += 1
        names = list(changed)
        for a in names:
            self.n[a] += 1
        for i, a in enumerate(names):
            ma = set(members_of(a))
            for b in names[i + 1 :]:
                if ma.intersection(members_of(b)):
                    continue
                k = self._key(a, b)
                self.co[k] += 1
                j = self.joint.get(k)
                if j is not None:
                    t = (changed[k[0]], changed[k[1]])
                    j[t] = j.get(t, 0) + 1
        if self.cfg.meta_window > 1:
            recent = self.recent.get(p)
            if recent is None:
                recent = self.recent[p] = deque(maxlen=self.cfg.meta_window - 1)
            for prev in recent:
                for a in names:
                    ma = set(members_of(a))
                    for b in prev:
                        if b == a or ma.intersection(members_of(b)):
                            continue
                        self.co[self._key(a, b)] += 1
            recent.append(names)

    def decay(self, factor: float) -> None:
        """Gradual forgetting, so that correlations describe the recent past (the référentiel
        follows what happens). Tiny counts are dropped to keep memory small."""
        if factor >= 1.0:
            return
        self.ticks *= factor
        for d in (self.n, self.co):
            for k in list(d):
                d[k] *= factor
                if d[k] < 0.5:
                    del d[k]
        for k, j in self.joint.items():
            for t in list(j):
                j[t] *= factor
                if j[t] < 0.5:
                    del j[t]

    def zscore(self, a, b) -> tuple[float, float]:
        """(lift, z) of the co-changes of a and b against independence, on current counts."""
        width = 2 * max(1, self.cfg.meta_window) - 1
        na, nb = self.n.get(a, 0.0), self.n.get(b, 0.0)
        expected = width * na * nb / max(1.0, self.ticks)
        if expected <= 0:
            return 0.0, 0.0
        c = self.co.get(self._key(a, b), 0.0)
        return c / expected, (c - expected) / math.sqrt(expected)

    def forget(self, p: int) -> None:
        self.recent.pop(p, None)

    def candidates(self, existing: set) -> list[tuple[float, tuple, str]]:
        """Correlated pairs not yet merged, best first: (score, pair, criterion)."""
        cfg, T = self.cfg, max(1, self.ticks)
        width = 2 * max(1, cfg.meta_window) - 1
        out = []
        for k, c in self.co.items():
            if c < cfg.meta_min_count or k in self.rejected:
                continue
            union = tuple(sorted(set(members_of(k[0])) | set(members_of(k[1]))))
            if len(union) > cfg.meta_max_arity or union in existing:
                continue
            na, nb = self.n[k[0]], self.n[k[1]]
            expected = width * na * nb / T
            if expected <= 0:
                continue
            if c / min(na, nb) >= 0.5 and na / T > 0.3 and nb / T > 0.3:
                # They change together most of the time: judge the content instead.
                j = self.joint.get(k)
                if j is None:
                    self.joint[k] = {}
                    continue
                mi = self._mutual_information(j)
                if mi is None:
                    continue
                if mi >= 0.5:
                    out.append((10.0 + mi, k, "content"))
                else:
                    self.rejected.add(k)
                    self.joint.pop(k, None)
                continue
            lift = c / expected
            z = (c - expected) / math.sqrt(expected)
            if lift >= cfg.meta_min_lift and z >= cfg.meta_z:
                out.append((z, k, "timing"))
        out.sort(key=lambda t: -t[0])
        return out

    def _mutual_information(self, joint: dict) -> float | None:
        """Mutual information in bits (Miller-Madow corrected) if it is significant,
        0.0 if enough data shows independence, None while undecided.

        Significance: G = 2 n ln2 MI is ~ chi2 with (|A|-1)(|B|-1) degrees of freedom under
        independence; the plug-in MI of sparse tables is large even for independent
        channels, so the effect size alone is not enough."""
        n = sum(joint.values())
        if n < 4 * self.cfg.meta_min_count:
            return None
        pa, pb = defaultdict(int), defaultdict(int)
        for (ta, tb), c in joint.items():
            pa[ta] += c
            pb[tb] += c
        mi = 0.0
        for (ta, tb), c in joint.items():
            mi += c / n * math.log2(c * n / (pa[ta] * pb[tb]))
        df = max(1, (len(pa) - 1) * (len(pb) - 1))
        g = 2 * n * math.log(2) * mi
        if g > df + self.cfg.meta_z * math.sqrt(2 * df):
            bias = (len(joint) - len(pa) - len(pb) + 1) / (2 * n * math.log(2))
            return mi - max(0.0, bias)
        if n >= 8 * df:  # plenty of data and still not significant: independent
            return 0.0
        return None

    def size(self) -> int:
        return len(self.n) + len(self.co) + sum(len(j) for j in self.joint.values())


class Observer:
    def __init__(self, cfg):
        self.cfg = cfg
        self.channels: dict[Name, Channel] = {}
        self.metas: list[tuple[str, ...]] = []
        self.meta_kind: dict[tuple[str, ...], str] = {}  # "timing" | "content"
        self.by_member: dict[str, list[tuple[str, ...]]] = defaultdict(list)
        self.cursors: dict[int, dict[Name, Cursor]] = {}
        self.tracker = CorrelationTracker(cfg)
        self.ticks = 0
        self.listeners: list[Callable[[tuple[str, ...]], None]] = []
        self.dissolve_listeners: list[Callable[[tuple[str, ...]], None]] = []
        self.meta_pair: dict[tuple[str, ...], tuple] = {}  # the correlated pair it came from
        self.dissolved = 0
        # time axis of the net: chain molettes over successive transitions
        self.seq = SequenceTracker(cfg)
        self.chains: list[tuple] = []
        self.chain_cur: dict[int, dict] = {}  # perspective -> chain -> (progress, last tick)
        self.tick_of: dict[int, int] = {}  # perspective -> ticks in this episode
        self.chains_dissolved = 0
        # construction elements: what the current state is built of
        self.ctracker = ConstructionTracker(cfg)
        self.elements: list[frozenset] = []
        self.elem_parent: dict[frozenset, tuple] = {}
        self.occurred: dict[int, set] = {}  # perspective -> events of this episode
        self.known_events: set = set()  # every transition ever seen
        self.elem_episodes = 0
        self.elements_dissolved = 0
        # discovered dynamics: meta molettes over units that transition together
        self.emetas: list[tuple] = []
        self.ptracker = PairTracker(cfg)
        self.tracked: set = set()
        self.emetas_dissolved = 0
        self.coprog: dict = {}  # pairs of elements that progressed at the same tick
        self.mtrans: list = []  # meta-transition molettes
        self.mt_by_pair: dict = {}
        self.mt_by_elem: dict = defaultdict(list)
        self.mtcount: dict = {}  # pairs of elements whose transitions changed together
        # discovery of the elements from the dynamics: set of steps -> [completions after
        # which nothing moved any more, completions after which the world went on]
        self.dcand: dict = {}
        self.dcand_by_ev: dict = defaultdict(set)
        self._dlast: dict = {}
        self._focus: tuple = (None, [])  # the state shown now, and the meta molettes live in it

    # --------------------------------------------------------------- discovery
    def view(self, p: int, obs: dict) -> dict:
        """What the molettes see of an observation: raw numeric watchers go through the
        lens Eva discovered for them (and are only buffered until it is discovered)."""
        if not self.cfg.discover:
            return obs
        lenses = self.__dict__.setdefault("lenses", {})
        raw = self.__dict__.setdefault("raw", {})
        lstate = self.__dict__.setdefault("lens_state", {}).setdefault(p, {})
        out = {}
        for k, v in obs.items():
            if not is_raw_number(v):
                out[k] = v
                continue
            lens = lenses.get(k)
            if lens is None:
                eps = raw.setdefault(k, {}).setdefault(p, [[]])
                eps[-1].append(v)
                n = sum(len(e) for per in raw[k].values() for e in per)
                if n >= self.cfg.discover_ticks:
                    lenses[k] = discover_lens([e for per in raw.pop(k).values() for e in per if e],
                                              min_dwell=self.cfg.discover_min_dwell)
                continue
            out[k] = lens.position(v, lstate.setdefault(k, {}))
        return out

    def _new_episode_view(self, p: int) -> None:
        if not self.cfg.discover:
            return
        self.__dict__.setdefault("lens_state", {})[p] = {}
        for per in self.__dict__.get("raw", {}).values():
            if p in per and per[p][-1]:
                per[p].append([])

    # ----------------------------------------------------------------- helpers
    def channel(self, name: Name) -> Channel:
        ch = self.channels.get(name)
        if ch is None:
            members = name if isinstance(name, tuple) else None
            ch = self.channels[name] = Channel(name, self.cfg, members)
        return ch

    @staticmethod
    def value(name: Name, obs: dict):
        if isinstance(name, tuple):
            return tuple(obs.get(m) for m in name)
        return obs.get(name)

    def net(self) -> set:
        """The net (filet): a cover of every watcher by what is judged important.

        Where a strong correlation called for a meta molette, that combination is in the
        net and stands for its members (the hand is one component); the watchers no strong
        correlation explains stay in the net as singletons (the needle). Groups may nest: a
        combination of two groups (a compromise of compromises) joins them, it does not
        replace them."""
        if self.cfg.construction:
            covered = set().union(*self.elements) if self.elements else set()
            singles = {("~ev", e) for e in self.ctracker.n if len(e) == 1 and next(iter(e)) not in covered}
            return {unit_name(k) for k in self.units()} | singles
        groups = list(self.metas)
        covered = set().union(*groups) if groups else set()
        singles = {n for n, ch in self.channels.items() if ch.members is None and n not in covered}
        return set(groups) | singles | {chain_name(C) for C in self.chains}

    def in_net(self, name) -> bool:
        """True if ``name`` is evaluated (always when the net is off)."""
        if not self.cfg.net:
            return True
        return name in self._net_cache()

    def _net_cache(self) -> set:
        key = (len(self.metas), len(self.channels), len(self.elements), len(self.emetas), len(self.ctracker.n))
        if getattr(self, "_net_key", None) != key:
            self._net_key, self._net_set = key, self.net()
        return self._net_set

    def names(self, obs: dict) -> list[Name]:
        return list(obs.keys()) + list(self.metas)

    def cursor(self, p: int, name: Name) -> Cursor:
        cs = self.cursors.setdefault(p, {})
        cur = cs.get(name)
        if cur is None:
            cur = cs[name] = Cursor()
        return cur

    # ---------------------------------------------------------------- learning
    def begin(self, p: int, obs: dict) -> None:
        self._new_episode_view(p)
        obs = self.view(p, obs)
        self.cursors[p] = {}
        for name in self.names(obs):
            self.channel(name).tick(self.cursor(p, name), self.value(name, obs))
        if self.cfg.sequences:
            self.chain_cur[p] = {}
            self.tick_of[p] = 0
            self.seq.forget(p)
            for C in self.chains:
                self.channel(chain_name(C)).tick(self.cursor(p, chain_name(C)), 0)
        if self.cfg.construction:
            self.occurred[p] = set()
            for k in self.units():
                self.channel(unit_name(k)).tick(self.cursor(p, unit_name(k)), unit_value(k, obs))

    def tick(self, p: int, obs: dict) -> list[Name]:
        """Feed one observation. Returns the channels that changed."""
        obs = self.view(p, obs)
        self.ticks += 1
        changed: dict[Name, tuple] = {}
        for name in self.names(obs):
            cur = self.cursor(p, name)
            old = cur.pos
            v = self.value(name, obs)
            if self.channel(name).tick(cur, v):
                changed[name] = (old, v)
        if self.cfg.construction:
            self._tick_elements(p, obs, changed)
            return list(changed)
        self.tracker.observe(changed, p)  # every tick counts, even when nothing changed
        if self.cfg.sequences:
            self._tick_chains(p, obs, changed)
        if self.ticks % self.cfg.meta_check_every == 0:
            self.tracker.decay(self.cfg.meta_decay)
            self.dissolve_metas()
            self.grow_metas()
            if self.cfg.sequences:
                self.seq.decay(self.cfg.meta_decay)
                self.dissolve_chains()
                self.grow_chains()
        return list(changed)

    def end(self, p: int) -> None:
        for name, cur in self.cursors.get(p, {}).items():
            self.channel(name).end(cur)
        self.cursors.pop(p, None)
        self.tracker.forget(p)
        self.seq.forget(p)
        self.chain_cur.pop(p, None)
        occ = self.occurred.pop(p, None)
        dyn = getattr(self.cfg, "elem_from_dynamics", False)
        if dyn:
            self._end_completions(p)
        if self.cfg.construction and occ is not None:
            self.ctracker.observe(occ, self.elements)
            self.elem_episodes += 1
            if self.elem_episodes % self.cfg.elem_check_every == 0:
                self.ctracker.decay(self.cfg.meta_decay)
                self.dissolve_elements()
                self.grow_elements()
                if dyn:
                    self.grow_dyn_elements()
                self.update_classes()
                if self.cfg.elem_metas and self.cfg.meta_birth == "timing":
                    self.ptracker.decay(self.cfg.meta_decay)
                    self.dissolve_emetas()
                    self.grow_emetas()

    def grow_metas(self) -> list[tuple[str, ...]]:
        """Create meta channels for the correlated groups (n9). Returns the new ones."""
        made = []
        existing = set(self.metas)
        for _score, (a, b), kind in self.tracker.candidates(existing):
            if len(self.metas) >= self.cfg.max_meta_channels:
                break
            union = tuple(sorted(set(members_of(a)) | set(members_of(b))))
            if union in existing:
                continue
            existing.add(union)
            self.metas.append(union)
            self.meta_kind[union] = kind
            self.meta_pair[union] = (a, b)
            for m in union:
                self.by_member[m].append(union)
            self.channel(union)
            made.append(union)
            for fn in self.listeners:
                fn(union)
        return made

    def adopt(self, S: tuple[str, ...], kind: str = "feedback") -> bool:
        """Give a combination proven useful by feedback its statistical molettes (its
        transitions, its time molettes): it becomes part of the net like a correlation."""
        S = tuple(sorted(S))
        if S in self.metas:
            return False
        self.metas.append(S)
        self.meta_kind[S] = kind
        for m in S:
            self.by_member[m].append(S)
        self.channel(S)
        return True

    def release(self, S: tuple[str, ...]) -> None:
        """A combination adopted from feedback that is no longer useful leaves the net."""
        if S not in self.metas or self.meta_kind.get(S) != "feedback":
            return
        self.metas.remove(S)
        for m in S:
            if S in self.by_member.get(m, []):
                self.by_member[m].remove(S)
        self.meta_kind.pop(S, None)
        self.channels.pop(S, None)
        for cs in self.cursors.values():
            cs.pop(S, None)

    def dissolve_metas(self) -> list[tuple[str, ...]]:
        """The référentiel follows what happens: a correlation molette whose pair no longer
        changes together significantly more often than chance (z < ``meta_dissolve_z`` on
        the recent, decayed counts) is dissolved, with every meta built on it. A pair that
        always changes together keeps its molette (content correlation, judged by the
        share of co-changes). Hysteresis: born at z >= meta_z and lift >= meta_min_lift."""
        cfg, tr = self.cfg, self.tracker
        gone: list[tuple[str, ...]] = []
        for S in list(self.metas):
            pair = self.meta_pair.get(S)
            if pair is None:
                continue
            a, b = pair
            na, nb = tr.n.get(a, 0.0), tr.n.get(b, 0.0)
            if min(na, nb) < cfg.meta_min_count:
                continue  # not enough recent evidence either way
            together = tr.co.get(tr._key(a, b), 0.0) / min(na, nb)
            lift, z = tr.zscore(a, b)
            if self.meta_kind.get(S) == "content":
                if together < 0.25:
                    gone.append(S)
            elif z < cfg.meta_dissolve_z:
                gone.append(S)
        # cascade: metas built on a dissolved one go too
        changed = bool(gone)
        while changed:
            changed = False
            for S in self.metas:
                if S in gone:
                    continue
                pair = self.meta_pair.get(S, ())
                if any(isinstance(x, tuple) and x in gone for x in pair):
                    gone.append(S)
                    changed = True
        for S in gone:
            self.metas.remove(S)
            for m in S:
                if S in self.by_member.get(m, []):
                    self.by_member[m].remove(S)
            self.meta_kind.pop(S, None)
            self.meta_pair.pop(S, None)
            self.channels.pop(S, None)
            for cs in self.cursors.values():
                cs.pop(S, None)
            self.dissolved += 1
            for fn in self.dissolve_listeners:
                fn(S)
        return gone

    # ------------------------------------------------------------- chains
    def _tick_chains(self, p: int, obs: dict, changed: dict) -> None:
        t = self.tick_of.get(p, 0) + 1
        self.tick_of[p] = t
        events = {(k, old, new) for k, (old, new) in changed.items() if not isinstance(k, tuple)}
        curs = self.chain_cur.setdefault(p, {})
        completed = []
        W = self.cfg.seq_window
        for C in self.chains:
            prog, last = curs.get(C, (0, 0))
            prog, last = advance(C, prog, last, events, t, W)
            curs[C] = (prog, last)
            if prog == len(C):
                completed.append(C)
            self.channel(chain_name(C)).tick(self.cursor(p, chain_name(C)), prog)
        self.seq.observe(p, t, sorted(events, key=repr) + completed)

    def chain_after(self, p: int, C: tuple, events: set) -> int:
        """Progress of chain C if the next tick brought ``events``."""
        prog, last = self.chain_cur.get(p, {}).get(C, (0, 0))
        return advance(C, prog, last, events, self.tick_of.get(p, 0) + 1, self.cfg.seq_window)[0]

    def events_after(self, p: int, obs_after: dict) -> set:
        cs = self.cursors.get(p, {})
        out = set()
        for k, v in obs_after.items():
            cur = cs.get(k)
            if cur is not None and cur.started and cur.pos != v:
                out.add((k, cur.pos, v))
        return out

    def grow_chains(self) -> list:
        made = []
        existing = set(self.chains)
        for _z, C in self.seq.candidates(existing):
            if len(self.chains) >= self.cfg.max_chains:
                break
            if C in existing:
                continue
            existing.add(C)
            self.chains.append(C)
            self.channel(chain_name(C))
            made.append(C)
        return made

    def dissolve_chains(self) -> list:
        """A succession that is no longer significant dissolves (with the chains built on it)."""
        gone = []
        for C in list(self.chains):
            prefix = C[0] if len(C) == 2 else C[:-1]
            c, lift, z = self.seq.stats(prefix, C[-1])
            if self.seq.n.get(prefix, 0.0) >= self.cfg.meta_min_count and z < self.cfg.meta_dissolve_z:
                gone.append(C)
        gone += [C for C in self.chains if C not in gone and any(C[: len(G)] == G for G in gone)]
        for C in gone:
            self.chains.remove(C)
            self.channels.pop(chain_name(C), None)
            for cs in self.cursors.values():
                cs.pop(chain_name(C), None)
            for cc in self.chain_cur.values():
                cc.pop(C, None)
            self.chains_dissolved += 1
        return gone

    # -------------------------------------------------------- construction
    def _tick_elements(self, p: int, obs: dict, changed: dict) -> None:
        occ = self.occurred.setdefault(p, set())
        events = [(k, old, new) for k, (old, new) in changed.items() if not isinstance(k, tuple)]
        occ.update(events)
        self.known_events.update(events)
        if getattr(self.cfg, "elem_from_dynamics", False):
            self._watch_completions(p, obs, events)
        moved = []
        tracked = self.tracked
        units = self.units()
        cs = self.cursors.setdefault(p, {})
        chans = self.channels
        live = self.cfg.live_metas
        prog = []
        if live and self.emetas:  # a meta molette turns only while it is live
            live_now = set(self.focus(obs))
            lp = getattr(self, "_live_by_p", None)
            if lp is None:
                lp = self._live_by_p = {}
            for k in lp.get(p, set()) - live_now:
                cs.pop(unit_name(k), None)  # no longer live: it restarts when live again
            lp[p] = live_now
            em = set(self.emetas)
            units = [k for k in units if not (isinstance(k, tuple) and k in em)] + list(live_now)
        vals = unit_values(units, obs)
        mt_on = getattr(self.cfg, "meta_transitions", False)
        if mt_on:  # where the elements stood before this tick
            prevpos = {}
            for k in self.elements:
                c0 = cs.get(unit_name(k))
                if c0 is not None and c0.started:
                    prevpos[k] = c0.pos
        for k in units:
            name = unit_name(k)
            cur = cs.get(name)
            v = vals[k]
            if cur is not None and cur.started and cur.pos == v:
                cur.dwell += 1  # the molette stays: only its time molette counts a tick
                continue
            if live and isinstance(k, frozenset) and cur is not None and cur.started and v[1] == 0 and v[0] > cur.pos[0]:
                prog.append(k)  # progressed this tick and still constructible
            ch = chans.get(name) or self.channel(name)
            if ch.tick(cur if cur is not None else self.cursor(p, name), v) and k in tracked:
                moved.append(k)
        if self.cfg.elem_metas and self.cfg.meta_birth == "timing":
            self.ptracker.observe(moved)
        if len(prog) > 1:
            self._co_progress(prog)
        if mt_on:
            self._tick_mtrans(p, cs, prevpos, vals)

    def _tick_mtrans(self, p: int, cs: dict, prevpos: dict, vals: dict) -> None:
        """Meta-transitions: the transition molettes of live elements that changed at this
        tick are counted together (a meta-transition is born after ``mt_min`` such ticks);
        each meta-transition follows the pair while both are live."""
        cfg, chans = self.cfg, self.channels
        ts = getattr(cfg, "two_sided", False)
        chg = [k for k, v0 in prevpos.items() if live_value(v0, ts) and vals.get(k, v0) != v0]
        if len(chg) > 1:
            for i, a in enumerate(chg):
                for b in chg[i + 1 :]:
                    if a <= b or b <= a:
                        continue
                    pair = _pair(a, b)
                    if pair in self.mt_by_pair:
                        continue
                    c = self.mtcount[pair] = self.mtcount.get(pair, 0) + 1
                    if c >= cfg.mt_min:
                        mt = MTrans(pair)
                        self.mtrans.append(mt)
                        self.mt_by_pair[pair] = mt
                        for x in pair:
                            self.mt_by_elem[x].append(mt)
                        self.channel(unit_name(mt))
                        del self.mtcount[pair]
        touched = {k for k, v0 in prevpos.items() if live_value(v0, ts)}
        touched.update(k for k in self.elements if k in vals and live_value(vals[k], ts))
        seen = set()
        for k in touched:
            for mt in self.mt_by_elem.get(k, ()):
                if mt in seen:
                    continue
                seen.add(mt)
                a, b = mt.pair
                pa, pb = prevpos.get(a), prevpos.get(b)
                va, vb = vals.get(a), vals.get(b)
                lb = pa is not None and pb is not None and live_value(pa, ts) and live_value(pb, ts)
                ln = va is not None and vb is not None and live_value(va, ts) and live_value(vb, ts)
                name = unit_name(mt)
                cur = cs.get(name)
                if lb and cur is not None and cur.started:
                    chans[name].tick(cur, (va, vb))  # a joint transition (or a tick of stay)
                if ln:
                    if cur is None or not cur.started:
                        chans[name].tick(self.cursor(p, name), (va, vb))  # starts following
                elif cur is not None:
                    del cs[name]

    def live_mtrans(self, state: dict) -> list:
        """The meta-transitions live in a state (both elements started and constructible)."""
        if not self.mtrans:
            return []
        cache = getattr(self, "_mt_live", (None, []))
        if cache[0] is state:
            return cache[1]
        ev = unit_values([k for k in self.mt_by_elem if self.mt_by_elem[k]], state)
        live = {k for k, v in ev.items() if live_value(v, getattr(self.cfg, "two_sided", False))}
        out, seen = [], set()
        for k in live:
            for mt in self.mt_by_elem[k]:
                if mt not in seen and all(x in live for x in mt.pair):
                    seen.add(mt)
                    out.append(mt)
        self._mt_live = (state, out)
        return out

    def _watch_completions(self, p: int, obs: dict, events: list) -> None:
        """Which candidate sets of steps were completed by this tick, and whether the world
        went on after the ones completed at the previous tick."""
        prev = self._dlast.get(p)
        if prev is not None:
            for S in prev[0]:
                st = self.dcand.get(S)
                if st is not None:
                    st[1] += 1  # completed, and the dynamics went on
        comp = set()
        for e in events:
            for S in self.dcand_by_ev.get(e, ()):
                if all(obs.get(w) == n for w, _o, n in S):
                    comp.add(S)
        self._dlast[p] = (comp, events, obs)

    def _end_completions(self, p: int) -> None:
        """Episode over: nothing moves any more after the last tick. The sets completed by
        it count as completions after which the dynamics stopped; the sets the last step
        built with steps already held become candidates."""
        from itertools import combinations

        last = self._dlast.pop(p, None)
        if last is None:
            return
        comp, events, obs = last
        for S in comp:
            self.dcand[S][0] += 1
        held = [e for e in self.known_events if obs.get(e[0]) == e[2]]
        cap = self.cfg.dyn_max_cand
        for e in events:
            others = [h for h in held if h[0] != e[0]]
            for k in range(1, self.cfg.elem_max_size):
                for T in combinations(others, k):
                    S = frozenset((e,) + T)
                    if S in self.dcand or len(self.dcand) >= cap:
                        continue
                    self.dcand[S] = [1, 0]
                    for x in S:
                        self.dcand_by_ev[x].add(S)

    def grow_dyn_elements(self) -> list:
        """Adopt the sets whose completion stops the dynamics (smallest first; a set that
        contains an element already adopted adds nothing); forget the candidates whose
        completion clearly does not."""
        cfg, made = self.cfg, []
        born = self.__dict__.setdefault("dyn_elems", set())
        for E in [E for E in born if E in self.dcand]:  # its completion no longer stops the dynamics
            en, co = self.dcand[E]
            if en + co >= 30 and en / (en + co) < cfg.dyn_ratio:
                born.discard(E)
                if E in self.elem_set:
                    self.remove_element(E)
        have = set(self.elements)
        for S, (en, co) in sorted(self.dcand.items(), key=lambda kv: len(kv[0])):
            if S in have or en < cfg.dyn_min_ends or en / (en + co) < cfg.dyn_ratio:
                continue
            if any(E <= S for E in have):
                continue
            if self.adopt_element(S):
                have.add(S)
                born.add(S)
                made.append(S)
        dead = [S for S, (en, co) in self.dcand.items() if en + co >= 30 and en / (en + co) < 0.5 and S not in born]
        for S in dead:
            del self.dcand[S]
            for x in S:
                self.dcand_by_ev[x].discard(S)
        return made

    def _co_progress(self, prog: list) -> None:
        """Two dynamics changed at the same tick: their correlation starts being counted, and
        after ``live_meta_min`` such ticks a meta molette follows their joint dynamics."""
        cfg, have = self.cfg, set(self.emetas)
        for i, a in enumerate(prog):
            for b in prog[i + 1 :]:
                if a <= b or b <= a:
                    continue
                pair = _pair(a, b)
                if pair in have:
                    continue
                c = self.coprog[pair] = self.coprog.get(pair, 0) + 1
                if c >= cfg.live_meta_min and len(self.emetas) < cfg.max_elem_metas:
                    self.emetas.append(pair)
                    have.add(pair)
                    self.channel(unit_name(pair))
                    del self.coprog[pair]

    def focus(self, state: dict) -> list:
        """The meta molettes live in the state shown now: both members started and still
        constructible. They join the net of the decisions taken from this state."""
        if state is self._focus[0]:
            return self._focus[1]
        live = []
        if self.cfg.live_metas and self.emetas:
            idx = self._meta_index()
            vals = unit_values(list(idx), state)
            up = {m for m, v in vals.items() if v[0] > 0 and v[1] == 0}
            seen = set()
            for m in up:
                for pair in idx[m]:
                    if pair not in seen and all(x in up for x in pair):
                        seen.add(pair)
                        live.append(pair)
        self._focus = (state, live)
        return live

    def _meta_index(self) -> dict:
        """Element -> the meta molettes built on it (rebuilt when the meta molettes change)."""
        key = (len(self.emetas), self.emetas[-1] if self.emetas else None)
        cache = getattr(self, "_midx", None)
        if cache is None or cache[0] != key:
            idx = defaultdict(list)
            for pair in self.emetas:
                if all(isinstance(m, frozenset) for m in pair):
                    for m in pair:
                        idx[m].append(pair)
            cache = self._midx = (key, idx)
        return cache[1]

    def units(self) -> list:
        """Every molette of the construction: the elements, the class molettes and the
        discovered meta molettes."""
        out = self.elements
        summ = getattr(self, "summaries", None)
        if summ:
            out = out + summ
        return out + self.emetas if self.emetas else out

    def update_classes(self) -> None:
        """Class molettes follow the elements: members are refreshed, a class appears when
        it has at least two elements (its molette keeps its notes across refreshes)."""
        if not self.cfg.class_molettes:
            return
        by = defaultdict(list)
        for E in self.elements:
            by[element_class(E)].append(E)
        old = {s: s for s in getattr(self, "summaries", [])}
        out = []
        for cls, els in by.items():
            if len(els) < 2:
                continue
            for d in range(1, cls[0]):
                key = Summary(cls, d, els)
                kept = old.get(key)
                if kept is not None:
                    kept.members = tuple(els)
                    key = kept
                out.append(key)
                self.channel(unit_name(key))
        for gone in set(old) - set(out):
            self.channels.pop(unit_name(gone), None)
        self.summaries = out

    def track(self, utility: dict, recent=()) -> None:
        """The units watched for joint transitions (the ``meta_track`` most useful ones) and
        the net that is evaluated (the ``net_size`` most useful ones + those on probation)."""
        pool = self.units()
        if self.cfg.live_metas:  # meta molettes enter the net when they are live, not by rank
            pool = [k for k in pool if not (isinstance(k, tuple) and k in set(self.emetas))]
        ranked = sorted(pool, key=lambda k: -utility.get(k, 0.0))
        self.tracked = set(ranked[: self.cfg.meta_track])
        if self.cfg.net_size:
            keep = ranked[: self.cfg.net_size]
            units = set(ranked)
            keep += [k for k in recent if k in units and k not in set(keep)]
            self.eval_units = keep

    def eval_set(self) -> list:
        """The units evaluated for a decision: the net, or every unit."""
        ev = getattr(self, "eval_units", None)
        if not self.cfg.net_size or ev is None:
            out = self.units()
            if self.cfg.live_metas:  # meta molettes only when live
                em = set(self.emetas)
                out = [k for k in out if k not in em] + self._focus[1]
            return out
        summ = getattr(self, "summaries", None)
        if summ:  # the class molettes are few and always in the net
            have = set(ev)
            ev = ev + [k for k in summ if k not in have]
        if self.cfg.live_metas and self._focus[1]:  # and what the instant shows
            have = set(ev)
            ev = ev + [k for k in self._focus[1] if k not in have]
        return ev

    def _enter_net(self, key) -> None:
        ev = getattr(self, "eval_units", None)
        if self.cfg.net_size and ev is not None and key not in ev:
            ev.append(key)  # born: evaluated during its probation

    def grow_emetas(self) -> list:
        made, existing = [], set(self.emetas)
        units = set(self.units())
        for _z, pair in self.ptracker.candidates(existing):
            if len(self.emetas) >= self.cfg.max_elem_metas:
                break
            if not all(k in units for k in pair):
                continue
            existing.add(pair)
            self.emetas.append(pair)
            self.channel(unit_name(pair))
            made.append(pair)
        return made

    def adopt_meta(self, pair: tuple) -> bool:
        """A meta molette born from feedback over units that are still there."""
        if pair in self.emetas or len(self.emetas) >= self.cfg.max_elem_metas:
            return False
        units = set(self.units())
        if not all(k in units for k in pair):
            return False
        self.emetas.append(pair)
        self.channel(unit_name(pair))
        self._enter_net(pair)
        return True

    def dissolve_emetas(self) -> list:
        gone = []
        for pair in self.emetas:
            c, lift, z = self.ptracker.stats(pair)
            if min(self.ptracker.n.get(k, 0.0) for k in pair) >= self.cfg.meta_min_count and z < self.cfg.meta_dissolve_z:
                gone.append(pair)
        for pair in gone:
            self.remove_unit(pair)
            self.emetas_dissolved += 1
        return gone

    def remove_unit(self, key) -> None:
        """Remove a unit and every meta molette built on it."""
        dead = {key}
        changed = True
        while changed:
            changed = False
            for m in self.emetas:
                if m not in dead and any(x in dead for x in m):
                    dead.add(m)
                    changed = True
        for k in dead:
            if isinstance(k, frozenset):
                if k in self.elements:
                    self.elements.remove(k)
                self.elem_parent.pop(k, None)
            elif k in self.emetas:
                self.emetas.remove(k)
                self.coprog.pop(k, None)
                self._midx = None
            self.channels.pop(unit_name(k), None)
            for cs in self.cursors.values():
                cs.pop(unit_name(k), None)
            self.tracked.discard(k)
        ev = getattr(self, "eval_units", None)
        if ev is not None:
            self.eval_units = [k for k in ev if k not in dead]
        self.ptracker.forget(dead)
        for mt in [m for m in getattr(self, "mtrans", []) if any(x in dead for x in m.pair)]:
            self.mtrans.remove(mt)
            self.mt_by_pair.pop(mt.pair, None)
            for x in mt.pair:
                if mt in self.mt_by_elem.get(x, []):
                    self.mt_by_elem[x].remove(mt)
            self.channels.pop(unit_name(mt), None)
            for cs in self.cursors.values():
                cs.pop(unit_name(mt), None)

    def held_events(self, obs: dict) -> list:
        """The known construction steps whose result holds in ``obs``."""
        return [e for e in self.known_events if obs.get(e[0]) == e[2]]

    @property
    def elem_set(self) -> set:
        return set(self.elements)

    def adopt_element(self, S: frozenset) -> bool:
        """An element born from feedback (no co-occurrence parent; never dissolved by the
        co-occurrence statistics)."""
        if S in self.elem_set:
            return False
        if getattr(self.cfg, "two_sided", False):  # the same construction seen from the other side
            fp = footprint(S)
            if any(footprint(U) == fp for U in self.elements if isinstance(U, frozenset)):
                return False
        fb = sum(1 for U in self.elements if self.elem_parent.get(U) is None)
        if fb >= self.cfg.max_feedback_elements:
            return False
        self.elements.append(S)
        self.elem_parent[S] = None
        self.channel(element_name(S))
        self._enter_net(S)
        return True

    def grow_elements(self) -> list:
        made = []
        existing = set(self.elements)
        for _z, U, parent in self.ctracker.candidates(existing):
            if sum(1 for U in self.elements if self.elem_parent.get(U) is not None) >= self.cfg.max_elements:
                break
            if len(parent[0]) > 1 and parent[0] not in existing:
                continue
            existing.add(U)
            self.elements.append(U)
            self.elem_parent[U] = parent
            self.channel(element_name(U))
            self._enter_net(U)
            made.append(U)
        return made

    def dissolve_elements(self) -> list:
        """An association no longer significant dissolves, with the elements built on it."""
        gone = set()
        for U in self.elements:
            if self.elem_parent[U] is None:
                continue  # born from feedback
            P, b = self.elem_parent[U]
            _, _, z = self.ctracker.stats(P, b)
            if self.ctracker.n.get(P, 0.0) >= self.cfg.meta_min_count and z < self.cfg.meta_dissolve_z:
                gone.add(U)
        changed = True
        while changed:
            changed = False
            for U in self.elements:
                if U not in gone and self.elem_parent[U] is not None and self.elem_parent[U][0] in gone:
                    gone.add(U)
                    changed = True
        for U in gone:
            self.remove_element(U)
            self.elements_dissolved += 1
        return list(gone)

    def remove_element(self, U: frozenset) -> None:
        self.remove_unit(U)

    # -------------------------------------------------------------- prediction
    def action(self, p: int, obs_after: dict, mode: str) -> float:
        """How much the molettes would move if the next tick showed ``obs_after`` (n11)."""
        total = 0.0
        cs = self.cursors.get(p, {})
        if self.cfg.construction:
            for k in self.eval_set():
                name = unit_name(k)
                cur = cs.get(name)
                if cur is None or not cur.started:
                    continue
                v = unit_value(k, obs_after)
                if mode == "displacement":
                    total += 0.0 if v == cur.pos else 1.0
                else:
                    total += self.channels[name].surprise(cur, v)
            return total
        for name in self.names(obs_after):
            if not self.in_net(name):
                continue
            cur = cs.get(name)
            if cur is None or not cur.started:
                continue
            v = self.value(name, obs_after)
            if mode == "displacement":
                total += 0.0 if v == cur.pos else 1.0
            elif mode == "shift":
                total += self.channels[name].shift(cur, v)
            else:
                total += self.channels[name].surprise(cur, v)
        if self.cfg.sequences and self.chains:
            events = self.events_after(p, obs_after)
            for C in self.chains:
                cur = cs.get(chain_name(C))
                if cur is None or not cur.started:
                    continue
                v = self.chain_after(p, C, events)
                if mode == "displacement":
                    total += 0.0 if v == cur.pos else 1.0
                else:
                    total += self.channels[chain_name(C)].surprise(cur, v)
        return total

    def dwell_after(self, p: int, name: Name, value) -> tuple[Hashable, int]:
        """Position and ticks-in-position of a channel if the next tick showed ``value``."""
        cur = self.cursors.get(p, {}).get(name)
        if cur is None or not cur.started or cur.pos != value:
            return value, 0
        return value, cur.dwell + 1

    def rhythm_positions(self, p: int, name: Name) -> list:
        cur = self.cursors.get(p, {}).get(name)
        return [lc.pos for lc in cur.levels] if cur else []

    def predict(self, p: int, watcher: str) -> dict:
        """Distribution of ``watcher``'s value at the next tick, combining its own molettes
        with every meta molette that contains it (longest context first, backing off
        Witten-Bell style to shorter ones)."""
        cs = self.cursors.get(p, {})
        base_cur = cs.get(watcher)
        base = self.channels.get(watcher)
        if base is None or base_cur is None or not base_cur.started:
            return {}
        dist = {v: base.p_next(base_cur, v) for v in base.trans.alphabet}
        dist.setdefault(base_cur.pos, base.p_next(base_cur, base_cur.pos))
        metas = sorted(self.by_member.get(watcher, []), key=len)
        for meta in metas:
            ch, cur = self.channels[meta], cs.get(meta)
            if cur is None or not cur.started:
                continue
            row = ch.trans.counts.get(cur.pos)
            n = ch.trans.totals.get(cur.pos, 0)
            if not row or n == 0:
                continue
            i = meta.index(watcher)
            h = ch.hazard(cur)
            local: dict = defaultdict(float)
            for nxt, c in row.items():
                local[nxt[i]] += h * c / n
            local[cur.pos[i]] += 1.0 - h
            w = n / (n + len(row))  # Witten-Bell confidence in the longer context
            keys = set(dist) | set(local)
            dist = {k: w * local.get(k, 0.0) + (1 - w) * dist.get(k, 0.0) for k in keys}
        z = sum(dist.values()) or 1.0
        return {k: v / z for k, v in dist.items()}

    def size(self) -> int:
        return sum(ch.size() for ch in self.channels.values()) + self.tracker.size()
