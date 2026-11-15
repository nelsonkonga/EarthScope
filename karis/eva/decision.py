"""Molettes de décision (n8) et méta molettes de décision (n10).

Every channel of the observer (standard, time, N-time, meta) has a decision molette: a
table of scores, neutral (0) at first. A decision is described by the *afterstate* it
produces; its score is the sum of the scores of the entries it activates. After each
episode every activated entry is pushed toward its target (max backup or lambda-return).

A meta decision molette scores *combinations* of positions (a compromise): it is created
when the error left by the single molettes is consistently biased whenever a given
combination is present, i.e. when the combination is worth more (or less) than the sum
of its parts.
"""

from __future__ import annotations

import math
from collections import defaultdict
from operator import itemgetter
from dataclasses import dataclass, field
from typing import Hashable

from .molettes import bucket

Feature = tuple


@dataclass
class Record:
    """One decision taken during an episode."""

    feats: list[Feature]
    after: dict
    changed: tuple[str, ...]
    reward: float = 0.0
    value: float = 0.0
    extra: dict = field(default_factory=dict)


class DecisionBank:
    def __init__(self, cfg, observer):
        self.cfg = cfg
        self.obs = observer
        self.w: dict[Feature, float] = {}
        self.metas: list[tuple[str, ...]] = []
        self.meta_set: set[tuple[str, ...]] = set()
        self.by_member: dict[str, list[tuple[str, ...]]] = defaultdict(list)
        # (watcher set, joint value) -> [n, sum of errors, sum of squared errors]
        self.cand: dict[tuple, list[float]] = {}
        self.ecand: dict[frozenset, list[float]] = {}  # construction elements from feedback
        self.elem_born: dict = {}
        self.mcand: dict = {}  # (pair of units, joint value) -> outcome residual stats
        self._touched: set[tuple] = set()
        self.created_from_stats = 0
        self.created_from_feedback = 0
        self.alpha = cfg.alpha  # current step, decayed by the agent
        self._getters: dict = {}  # meta -> itemgetter of its watchers (fast joints)
        self.seen: dict[Feature, int] = {}  # how many times each entry was judged
        # backup "converge": each molette's own count (its distribution converges) and the
        # mean outcome (an unknown molette says nothing: it stands at the mean)
        self.nupd: dict[Feature, int] = {}
        self.base, self.base_n = 0.0, 0
        self.origin: dict[tuple[str, ...], str] = {}  # "stats" | "feedback"
        self.born: dict[tuple[str, ...], int] = {}  # episode of creation
        # pruned combinations cannot be reborn before this episode (not forever: what was
        # useless early may become useful once the rest has been learned)
        self.blocked: dict[tuple[str, ...], int] = {}
        self.episode = 0
        self.pruned = 0
        observer.listeners.append(self._on_observer_meta)
        observer.dissolve_listeners.append(self._on_observer_dissolve)

    # ------------------------------------------------------------ structure
    def _on_observer_meta(self, members: tuple[str, ...]) -> None:
        """Every meta molette standard gets its decision molette."""
        if self.add_meta(members, origin="stats"):
            self.created_from_stats += 1

    def _on_observer_dissolve(self, members: tuple[str, ...]) -> None:
        """A correlation molette that dissolves takes its decision molette with it (it may
        come back if the correlation does)."""
        if self.origin.get(members) == "stats":
            self.remove_meta(members)

    def remove_meta(self, S: tuple[str, ...], block: bool = False) -> None:
        if S not in self.meta_set:
            return
        self.metas = [x for x in self.metas if x != S]
        self.meta_set.discard(S)
        if block:
            self.blocked[S] = self.episode + self.cfg.md_block_for
        for m in S:
            self.by_member[m] = [x for x in self.by_member[m] if x != S]
        self.w = {f: v for f, v in self.w.items() if not (f[0] in ("m", "mt") and f[1] == S)}
        self.origin.pop(S, None)

    def probation(self, S: tuple[str, ...]) -> int:
        """Episodes before a new combination may be judged useless: the larger it is, the
        more configurations it has to learn (one pruning period per watcher beyond two)."""
        return self.cfg.md_prune_every * max(1, len(S) - 2)

    def is_blocked(self, S: tuple[str, ...]) -> bool:
        until = self.blocked.get(S)
        return until is not None and until > self.episode

    def add_meta(self, members: tuple[str, ...], origin: str = "feedback") -> bool:
        """Create a meta decision molette. One born from a statistical correlation
        (origin "stats") is always created — every correlation molette has its decision
        molette — ignores the budget and is never pruned; if feedback had already created
        it, it is simply adopted."""
        members = tuple(sorted(members))
        if origin == "stats":
            self.blocked.pop(members, None)
            if members in self.meta_set:
                self.origin[members] = "stats"
                return True
        elif members in self.meta_set or self.is_blocked(members):
            return False
        elif len(self.metas) >= self.cfg.max_meta_decisions:
            return False
        self.origin[members] = origin
        self.born[members] = self.episode
        self.meta_set.add(members)
        self.metas.append(members)
        for m in members:
            self.by_member[m].append(members)
        return True

    # ------------------------------------------------------------- features
    def time_features(self, before: dict, after: dict) -> list:
        """Only the time part of a move (``cfg.time_net``): the transitions of the elements,
        of the raw watchers and the meta-transitions it triggers. Enough to choose; the space
        part is computed for the move taken (it learns to judge the position)."""
        from .construction import unit_values

        obs = self.obs
        els = obs.elements
        cache = getattr(self, "_tf_before", None)
        if cache is not None and cache[0] is before and cache[1] == len(els):
            bv = cache[2]
        else:
            bv = unit_values(els, before)
            self._tf_before = (before, len(els), bv)
        av = unit_values(els, after)
        # every molette gives one note of time: its transition, or its staying (a dynamics
        # may stay the same): all moves are compared on the same molettes
        out = [("c", k, bv[k], av[k]) for k in els]
        out.extend(("c", k, before.get(k), v) for k, v in after.items() if isinstance(k, str) and before.get(k) != after.get(k) or (isinstance(k, str) and v == "." ))
        if getattr(self.cfg, "meta_transitions", False) and obs.mtrans:
            for mt in obs.live_mtrans(before):
                x, y = mt.pair
                if x in bv and y in bv and bv[x] != av[x] and bv[y] != av[y]:
                    out.append(("mt", mt, (bv[x], av[x]), (bv[y], av[y])))
        return out

    def features(self, p: int, before: dict, after: dict) -> tuple[list[Feature], tuple[str, ...]]:
        cfg, obs = self.cfg, self.obs
        feats: list[Feature] = []
        changed = tuple(k for k, v in after.items() if before.get(k) != v)
        in_net = obs.in_net
        if cfg.construction:
            obs.focus(before)  # the net of this decision: what the state shows now
            return self._construction_features(p, before, after), changed
        for k, v in after.items():
            if not in_net(k):
                continue
            feats.append(("p", k, v))
            if cfg.time_features:
                _, d = obs.dwell_after(p, k, v)
                feats.append(("t", k, v, bucket(d) if d else 0))
        if cfg.change_features:
            for k in changed:
                if in_net(k):
                    feats.append(("c", k, before.get(k), after[k]))
        if cfg.rhythm_features:
            for k in after:
                if not in_net(k):
                    continue
                for lvl, pos in enumerate(obs.rhythm_positions(p, k)):
                    feats.append(("n", k, lvl + 2, pos))
        getters = self._getters
        for S in self.metas:
            if cfg.net and not in_net(S):
                continue  # only the combinations of the net (largest statistical ones)
            g = getters.get(S)
            if g is None:
                g = getters[S] = itemgetter(*S)
            try:
                joint = g(after)
            except KeyError:  # a watcher absent from this observation
                joint = tuple(after.get(m) for m in S)
            feats.append(("m", S, joint))
            if cfg.time_features and S in obs.channels:
                _, d = obs.dwell_after(p, S, joint)
                feats.append(("mt", S, joint, bucket(d) if d else 0))
        if cfg.sequences and obs.chains:
            events = {(k, before.get(k), after[k]) for k in changed}
            from .observer import chain_name

            for C in obs.chains:
                if not in_net(chain_name(C)):
                    continue
                prog = obs.chain_after(p, C, events)
                feats.append(("s", C, prog))
                if cfg.time_features:
                    _, d = obs.dwell_after(p, chain_name(C), prog)
                    feats.append(("st", C, prog, bucket(d) if d else 0))
        return feats, changed

    def _construction_features(self, p: int, before: dict, after: dict) -> list[Feature]:
        """Decision molettes of the construction elements present in the state (magnitude
        > 0): one per element and magnitude
        (and per time in that magnitude, and per position of its higher derivatives), plus
        the events no element explains (construction steps on their own)."""
        from .construction import present, unit_name, unit_values

        cfg, obs = self.cfg, self.obs
        feats: list[Feature] = []
        covered = set().union(*obs.elements) if obs.elements else set()
        units = obs.eval_set()
        vals = unit_values(units, after)
        for k in units:
            v = vals[k]
            if not present(k, v) and not cfg.absent_notes:
                continue  # not part of what the current state is built of
            feats.append(("e", k, v))
            name = unit_name(k)
            if cfg.time_features:
                _, d = obs.dwell_after(p, name, v)
                feats.append(("et", k, v, bucket(d) if d else 0))
            if cfg.rhythm_features:
                for lvl, pos in enumerate(obs.rhythm_positions(p, name)):
                    feats.append(("n", k, lvl + 2, pos))
        for e in obs.held_events(after):
            if e not in covered:
                feats.append(("ev", e))
        if getattr(cfg, "time_net", False):  # the raw watchers have their decision molettes too
            feats.extend(("e", k, v) for k, v in after.items() if isinstance(k, str))
        if cfg.change_features:
            feats.extend(self.transition_features(before, after, vals))
        return feats

    def transition_features(self, before: dict, after: dict, after_vals: dict | None = None) -> list:
        """The transitions of the elements between two states: ('c', E, from, to)."""
        from .construction import present, unit_value, unit_values

        self.obs.focus(before)
        units = self.obs.eval_set()
        cache = getattr(self, "_before_vals", None)
        if cache is not None and cache[0] is before and cache[1] == len(units):
            bv = cache[2]
        else:
            bv = unit_values(units, before)
            self._before_vals = (before, len(units), bv)
        av = after_vals if after_vals is not None else unit_values(units, after)
        out = []
        ts = getattr(self.cfg, "two_sided", False)
        for k in units:
            a, b = bv[k], av[k]
            if a != b and (present(k, a) or present(k, b) or (ts and isinstance(k, frozenset) and (a[1] or b[1]))):
                out.append(("c", k, a, b))
        cfg, obs = self.cfg, self.obs
        if getattr(cfg, "time_net", False):
            # the elements that stay give their note of time too (a dynamics may stay the same)
            out.extend(("c", k, bv[k], av[k]) for k in units if isinstance(k, frozenset) and bv[k] == av[k])
            # transitions of the raw watchers (and the free ones that stay)
            out.extend(("c", k, before.get(k), v) for k, v in after.items()
                       if isinstance(k, str) and (before.get(k) != v or v == "."))
        if getattr(cfg, "meta_transitions", False) and obs.mtrans:
            for mt in obs.live_mtrans(before):  # both transition molettes change at once
                x, y = mt.pair
                x0, y0 = bv[x] if x in bv else unit_value(x, before), bv[y] if y in bv else unit_value(y, before)
                x1, y1 = av[x] if x in av else unit_value(x, after), av[y] if y in av else unit_value(y, after)
                if x0 != x1 and y0 != y1:
                    out.append(("mt", mt, (x0, x1), (y0, y1)))
        return out

    def combine_time(self, items) -> float:
        """The time part of the net, from (molette, weight, phase) items — phase 0: the
        transitions the move makes, phase 1: the standard transitions that follow.
        - what a transition says: its note (with ``cfg.time_impact``: the change it brings,
          its note minus the note of the state it leaves);
        - attention: only molettes with an impact of their own (|what it says| >= attention);
        - factorisation: each element's dynamics counts once, by itself; a meta-transition
          adds only what its members together do not say (its note minus theirs: e.g. two
          threats made at once), if that has an impact; each member enters at most one
          meta-transition (the most telling first), so nothing is counted twice;
        - the net is the sum."""
        note, tau = self.note, self.cfg.attention
        impact = getattr(self.cfg, "time_impact", False)

        def says(f) -> float:
            n = note(f)
            if impact == "stay":  # what the change brings compared with staying where it is
                if f[0] == "c":
                    n -= note(("c", f[1], f[2], f[2]))
            elif impact:  # the change the transition brings to what the state already said
                if f[0] == "c":
                    n -= note(("e", f[1], f[2]))
                elif f[0] == "mt":  # the joint state it leaves: what its members said
                    x, y = f[1].pair
                    n -= (note(("e", x, f[2][0])) + note(("e", y, f[3][0]))) / 2
            return n

        total = 0.0
        trace = self.trace_time = []
        mts = []
        for f, q, ph in items:
            if f[0] == "mt":
                x, y = f[1].pair
                cx, cy = ("c", x) + f[2], ("c", y) + f[3]
                if impact == "stay":  # the pair together compared with each on its own
                    extra = note(f) - (note(cx) + note(cy)) / 2
                else:
                    extra = says(f) - says(cx) - says(cy)
                if abs(extra) >= tau:
                    mts.append((abs(q * extra), f, q, ph, extra))
                continue
            n = says(f)
            if abs(n) >= tau:
                total += q * n
                trace.append((f, ph, q * n))
        used = {0: defaultdict(float), 1: defaultdict(float)}  # share of each member taken
        self.last_factored = 0
        for _w, f, q, ph, extra in sorted(mts, key=lambda t: -t[0]):
            x, y = f[1].pair
            u = used[ph]
            q = min(q, 1.0 - max(u[x], u[y]))
            if q <= 1e-9:
                continue
            u[x] += q
            u[y] += q
            total += q * extra
            trace.append((f, ph, q * extra))
            self.last_factored += 1
        return total

    def _collect_metas(self, rec: Record, err: float) -> None:
        """Units moved together by this step (among the watched ones) and the joint value
        they reach: a combination the outcome keeps judging apart from what is believed is a
        correlation of decision molettes — a meta molette over them (e.g. two threats made by
        one step)."""
        from .construction import _pair, members, present, unit_values

        before = rec.extra.get("before")
        if before is None:
            return
        tracked = list(self.obs.tracked)
        av, bv = unit_values(tracked, rec.after), unit_values(tracked, before)
        moved = [(k, av[k]) for k in tracked if present(k, av[k]) and bv[k] != av[k]]
        cand = self.mcand
        for i, (a, va) in enumerate(moved):
            for b, vb in moved[i + 1 :]:
                ma, mb = members(a), members(b)
                if ma <= mb or mb <= ma:
                    continue
                pair = _pair(a, b)
                joint = (va, vb) if pair[0] is a else (vb, va)
                key = (pair, joint)
                st = cand.get(key)
                if st is None:
                    st = cand[key] = [0, 0.0, 0.0]
                st[0] += 1
                st[1] += err
                st[2] += err * err

    def grow_unit_metas(self) -> list:
        cfg, obs = self.cfg, self.obs
        best = {}
        for (pair, _joint), (n, s, ss) in self.mcand.items():
            if n < cfg.elem_fb_min_count:
                continue
            mean = s / n
            var = max(ss / n - mean * mean, 1e-9)
            z = abs(mean) / math.sqrt(var / n)
            if abs(mean) >= cfg.md_min_effect and z >= cfg.elem_fb_z:
                best[pair] = max(best.get(pair, 0.0), z)
        made = []
        for pair, _z in sorted(best.items(), key=lambda t: -t[1]):
            if obs.adopt_meta(pair):
                self.elem_born[pair] = self.episode
                made.append(pair)
        if made:
            done = set(made)
            self.mcand = {k: v for k, v in self.mcand.items() if k[0] not in done}
        if len(self.mcand) > cfg.md_max_candidates:
            keep = sorted(self.mcand.items(), key=lambda kv: -kv[1][0])[: cfg.md_max_candidates // 2]
            self.mcand = dict(keep)
        return made

    def prune_unit_metas(self) -> list:
        """When the budget is full, the meta molettes whose decision molettes say least give
        their place (after probation)."""
        cfg, obs = self.cfg, self.obs
        if len(obs.emetas) < cfg.max_elem_metas:
            return []
        util = self.unit_utility()
        old = [m for m in obs.emetas if self.episode - self.elem_born.get(m, 0) >= cfg.md_prune_every]
        old.sort(key=lambda m: util.get(m, 0.0))
        dead = old[: int(len(old) * cfg.md_prune_ratio)]
        for m in dead:
            obs.remove_unit(m)
        if dead:
            gone = set(dead)
            self.w = {f: v for f, v in self.w.items() if not (f[0] in ("e", "et", "n", "c") and f[1] in gone)}
        return dead

    def unit_utility(self) -> dict:
        """How much each unit's decision molettes say (sum of |notes|)."""
        util = defaultdict(float)
        b = self.base if self.cfg.backup == "converge" else 0.0
        for f, v in self.w.items():
            if f[0] in ("e", "et", "c"):
                util[f[1]] += abs(v - b)
        return util

    def learn_transitions(self, recs: list, R: float) -> None:
        """Every transition the world brought during the episode tilts toward the result,
        modulated by its belief, like every decision molette (no credit assignment); the
        sets of events it built with what holds can become elements, like Eva's own steps."""
        if self.cfg.backup == "belief_each":
            for rec in recs:
                v = self.value(rec.feats)
                if self.cfg.elem_from_feedback:
                    self._collect_elements(rec, R - v)
                if self.cfg.elem_metas and self.cfg.meta_birth == "feedback":
                    self._collect_metas(rec, R - v)
                self._tilt_by_own_belief(rec.feats, R - v)
            return
        if self.cfg.backup == "converge":
            for rec in recs:
                v = math.tanh(self.value(rec.feats))
                if self.cfg.elem_from_feedback:
                    self._collect_elements(rec, R - v)
                if self.cfg.elem_metas and self.cfg.meta_birth == "feedback":
                    self._collect_metas(rec, R - v)
                self._converge(rec.feats, R)
            return
        if self.cfg.backup == "independent":
            w = self.w
            for rec in recs:
                feats = rec.feats
                believed = sum(w.get(f, 0.0) for f in feats) / len(feats) if feats else 0.0
                if self.cfg.elem_from_feedback:
                    self._collect_elements(rec, R - believed)
                if self.cfg.elem_metas and self.cfg.meta_birth == "feedback":
                    self._collect_metas(rec, R - believed)
                self._tilt_each(feats, R)
            return
        for rec in recs:
            v = self.value(rec.feats)
            if self.cfg.elem_from_feedback:
                self._collect_elements(rec, R - v)  # the world's steps can found elements too
            if self.cfg.elem_metas and self.cfg.meta_birth == "feedback":
                self._collect_metas(rec, R - v)
            belief = max(0.0, 1.0 - min(1.0, v * v)) ** self.cfg.resistance
            self.update(rec.feats, belief * (R - v))

    def _collect_elements(self, rec: Record, err: float) -> None:
        """Sets of events built together at this decision (the step just taken, or a step it
        made impossible, with one or two steps already built) and how far the outcome was from the note: a set the
        outcome keeps judging differently from its parts is a construction element the
        statistics missed (meta decision molette born from feedback)."""
        after = rec.after
        held = self.obs.held_events(after)
        new = [e for e in held if e[0] in rec.changed]
        known = self.obs.elem_set
        cand = self.ecand
        chans = self.obs.channels
        for a in new:
            others = sorted((e for e in held if e is not a), key=repr)
            # the step taken, and the steps it made impossible: the other transitions the
            # watcher's transition molette knew from that value
            w, old, nv = a
            ch = chans.get(w)
            closed = [(w, old, v) for v in (ch.trans.counts.get(old, {}) if ch else {}) if v != nv and v != old]
            sets = []
            for x in [a] + closed:
                sets += [frozenset((x, b)) for b in others]
                sets += [frozenset((x, b, c)) for i, b in enumerate(others) for c in others[i + 1 :]]
            for S in sets:
                if S in known:
                    continue
                st = cand.get(S)
                if st is None:
                    st = cand[S] = [0, 0.0, 0.0]
                st[0] += 1
                st[1] += err
                st[2] += err * err

    def grow_elements(self) -> list:
        cfg, obs = self.cfg, self.obs
        best = []
        for S, (n, s, ss) in self.ecand.items():
            if n < cfg.elem_fb_min_count:
                continue
            mean = s / n
            var = max(ss / n - mean * mean, 1e-9)
            z = abs(mean) / math.sqrt(var / n)
            if abs(mean) >= cfg.md_min_effect and z >= cfg.elem_fb_z:
                best.append((z, S))
        best.sort(key=lambda t: -t[0])
        made = []
        for _z, S in best:
            if obs.adopt_element(S):
                self.elem_born[S] = self.episode
                made.append(S)
                self.ecand.pop(S, None)
        if len(self.ecand) > cfg.md_max_candidates:
            keep = sorted(self.ecand.items(), key=lambda kv: -kv[1][0])[: cfg.md_max_candidates // 2]
            self.ecand = dict(keep)
        return made

    def prune_elements(self) -> list:
        """When the feedback budget is full, the feedback elements whose decision molettes
        say least (sum of |notes|) give their place (``md_prune_ratio`` of them)."""
        cfg, obs = self.cfg, self.obs
        fb = [U for U in obs.elements if obs.elem_parent.get(U) is None]
        if len(fb) < cfg.max_feedback_elements:
            return []
        born = self.elem_born
        fb = [U for U in fb if self.episode - born.get(U, 0) >= cfg.md_prune_every]  # probation
        fbset = set(fb)
        util = defaultdict(float)
        b = self.base if cfg.backup == "converge" else 0.0
        for f, v in self.w.items():
            if f[0] in ("e", "et") and f[1] in fbset:
                util[f[1]] += abs(v - b)
        fb.sort(key=lambda U: util.get(U, 0.0))
        dead = fb[: int(len(fb) * cfg.md_prune_ratio)]
        for U in dead:
            obs.remove_element(U)
        if dead:
            from .construction import members

            gone = set(dead)
            self.w = {f: v for f, v in self.w.items()
                      if not (f[0] in ("e", "et", "n", "c", "mt") and members(f[1]) & gone)}
            self.elements_pruned = getattr(self, "elements_pruned", 0) + len(dead)
        return dead

    def note(self, f) -> float:
        """What one decision molette says. With ``backup="converge"`` a note is its own
        estimate of the outcome; what it says is how far that is from the mean outcome."""
        if self.cfg.backup == "converge":
            b = self.base
            return self.w.get(f, b) - b
        return self.w.get(f, 0.0)

    def combine(self, items) -> float:
        """The net of a decision (``backup="converge"``), from (molette, weight) items:
        - attention: only the molettes with an impact of their own on the result
          (|note - mean| >= ``cfg.attention``);
        - factorisation: a meta molette with an impact replaces its members, and a molette
          read with its time replaces the same one read without it;
        - the net is the sum of what the remaining molettes say."""
        w, b, tau = self.w, self.base, self.cfg.attention
        kept = []
        for f, q in items:
            n = w.get(f, b) - b
            if abs(n) >= tau:
                kept.append((f, q, n))
        if not kept:
            return 0.0
        timed = {(f[1], f[2]) for f, _q, _n in kept if f[0] == "et"}
        factored = set()
        for f, _q, _n in kept:
            k = f[1] if len(f) > 1 else None
            if isinstance(k, tuple) and k and not isinstance(k[0], str):  # a meta molette
                factored.update(k)
        total = 0.0
        for f, q, n in kept:
            if f[0] == "e" and (f[1], f[2]) in timed:
                continue
            if len(f) > 1 and f[1] in factored:
                continue
            total += q * n
        return total

    def value(self, feats: list[Feature]) -> float:
        """The note of a decision: the sum of its molettes' notes, squashed into (-1, 1)
        (``cfg.squash``) so that a belief can be firm without ever freezing."""
        w = self.w
        if self.cfg.backup == "converge":  # the net of the molettes that have an impact
            return self.combine([(f, 1.0) for f in feats])
        agg = getattr(self.cfg, "note_agg", "sum")
        if agg == "min" and feats:  # no molette firmly against it
            return min(w.get(f, 0.0) for f in feats)
        if agg == "cube":  # firm beliefs weigh more than many weak ones
            s = sum(w.get(f, 0.0) ** 3 for f in feats)
        else:
            s = sum(w.get(f, 0.0) for f in feats)
            if agg == "mean" and feats:
                s /= len(feats)
        return math.tanh(s) if self.cfg.squash else s

    def update(self, feats: list[Feature], err: float) -> None:
        if not feats:
            return
        step = self.alpha * err / len(feats)
        w = self.w
        for f in feats:
            w[f] = w.get(f, 0.0) + step

    # ------------------------------------------------------------- learning
    def learn(self, traj: list[Record]) -> float:
        """Lambda-return update of one perspective's decisions. Returns the mean |error|."""
        cfg = self.cfg
        if not traj:
            return 0.0
        g_next = 0.0
        total = 0.0
        for t in range(len(traj) - 1, -1, -1):
            rec = traj[t]
            v = self.value(rec.feats)
            if t == len(traj) - 1:
                g = rec.reward
            else:
                v_next = self.value(traj[t + 1].feats)
                g = rec.reward + cfg.gamma * ((1 - cfg.lam) * v_next + cfg.lam * g_next)
            err = g - v
            total += abs(err)
            if cfg.meta_decisions:
                self._collect(rec, err)
            self.update(rec.feats, err)
            g_next = g
        return total / len(traj)

    def learn_max(self, seq: list[tuple[int, Record]]) -> float:
        """Max backup, for any environment (Q-learning on afterstates).

        Target of a decision = the feedback it received + gamma x the best note available
        at the *next decision of the same perspective* (the options scored then, re-read
        with the current notes), or its feedback alone if it was the last one. Eva's own
        exploration never pollutes the notes. If a decision Eva took for another
        perspective in between was exploratory, the transition does not reflect her
        policy: it is skipped (Watkins cut). Nothing is simulated.
        Returns the mean |error| of the updated decisions."""
        if not seq:
            return 0.0
        gamma = self.cfg.gamma
        total, n = 0.0, 0
        for i in range(len(seq) - 1, -1, -1):
            p, rec = seq[i]
            j = next((k for k in range(i + 1, len(seq)) if seq[k][0] == p), None)
            between = seq[i + 1 : j] if j is not None else seq[i + 1 :]
            if any(r.extra.get("explored") for q, r in between if q != p):
                continue
            g = rec.reward
            if j is not None:
                nxt = seq[j][1]
                g += gamma * max((f if f is not None else self.value(fe)) for fe, f in nxt.extra["alts"])
            err = g - self.value(rec.feats)
            total += abs(err)
            n += 1
            if self.cfg.meta_decisions:
                self._collect(rec, err)
            self.update(rec.feats, err)
        return total / max(1, n)

    def learn_belief(self, traj: list[Record]) -> float:
        """The user's rule: no credit assignment. At the end of the episode every decision
        of this perspective tilts toward what followed it (its feedback from then on; for
        a game, the final result), and the tilt is modulated by the prior belief: the more
        neutral the note of the decision, the more it moves; a decision believed very good
        or very bad moves little (resistance to change, ``cfg.resistance``).

            tilt = alpha * (1 - V^2)^resistance * (R - V),   V = note before this episode

        Returns the mean |R - V|."""
        if not traj:
            return 0.0
        cfg = self.cfg
        returns, g = [], 0.0
        for rec in reversed(traj):
            g = rec.reward + cfg.gamma * g
            returns.append(g)
        returns.reverse()
        prior = [self.value(rec.feats) for rec in traj]  # beliefs before this episode
        total = 0.0
        for rec, r, v in zip(traj, returns, prior):
            err = r - v
            total += abs(err)
            if cfg.meta_decisions:
                self._collect(rec, err)
            if cfg.construction and cfg.elem_from_feedback:
                self._collect_elements(rec, err)
            if cfg.construction and cfg.elem_metas and cfg.meta_birth == "feedback":
                self._collect_metas(rec, err)
            belief = max(0.0, 1.0 - min(1.0, v * v)) ** cfg.resistance  # v in (-1, 1) when squashed
            if getattr(cfg, "trans_symmetric", False) and cfg.construction:
                # the transitions of this step learn like the world's (one group, own belief)
                cf = [f for f in rec.feats if f[0] == "c"]
                self.update([f for f in rec.feats if f[0] != "c"], belief * err)
                if cf:
                    vc = self.value(cf)
                    self.update(cf, max(0.0, 1.0 - min(1.0, vc * vc)) ** cfg.resistance * (r - vc))
                continue
            self.update(rec.feats, belief * err)
        return total / len(traj)

    def _converge(self, feats, r: float) -> None:
        """Each molette of the decision learns on its own: a constant step, never shared
        among the molettes present and never shrinking with data; only its own belief makes
        the change harder."""
        w, n = self.w, self.nupd
        res, a, b = self.cfg.resistance, self.cfg.converge_alpha, self.base
        for f in set(feats):
            v = w.get(f, b)
            n[f] = n.get(f, 0) + 1
            belief = min(1.0, (v - b) * (v - b))  # conviction: how far it stands from "nothing known"
            w[f] = max(-1.0, min(1.0, v + a * (1.0 - belief) ** res * (r - v)))

    def _see_outcome(self, r: float) -> None:
        self.base_n += 1
        self.base += (r - self.base) / self.base_n

    def learn_converge(self, traj: list[Record]) -> float:
        """The user's rule: no credit assignment, no division of the step. At the end of the
        episode every molette of every decision tilts toward what followed, by itself."""
        if not traj:
            return 0.0
        cfg = self.cfg
        returns, g = [], 0.0
        for rec in reversed(traj):
            g = rec.reward + cfg.gamma * g
            returns.append(g)
        returns.reverse()
        prior = [math.tanh(self.value(rec.feats)) for rec in traj]
        total = 0.0
        for rec, r, v in zip(traj, returns, prior):
            err = r - v
            total += abs(err)
            if cfg.construction and cfg.elem_from_feedback:
                self._collect_elements(rec, err)
            if cfg.construction and cfg.elem_metas and cfg.meta_birth == "feedback":
                self._collect_metas(rec, err)
            self._converge(rec.feats, r)
        self._see_outcome(returns[0])
        return total / len(traj)

    def learn_independent(self, traj: list[Record]) -> float:
        """The user's rule, read literally: EACH decision molette tilts toward the result.

        Every entry active in a decision is its own estimate of the outcome when it is
        present (not a share of a sum): at the end of the episode it tilts toward what
        followed, modulated by its own belief,

            note += alpha * (1 - note^2)^resistance * (R - note)

        so a decisive combination converges to its own outcome instead of being diluted
        among the molettes that happened to be there. No credit assignment.
        Returns the mean |R - note| over the entries."""
        if not traj:
            return 0.0
        cfg, w = self.cfg, self.w
        returns, g = [], 0.0
        for rec in reversed(traj):
            g = rec.reward + cfg.gamma * g
            returns.append(g)
        returns.reverse()
        total, n = 0.0, 0
        for rec, r in zip(traj, returns):
            if cfg.meta_decisions:
                self._collect(rec, 0.0, result=r)
            if cfg.construction:
                # "judged apart from what is believed": the outcome minus the mean belief
                feats = rec.feats
                believed = sum(w.get(f, 0.0) for f in feats) / len(feats) if feats else 0.0
                if cfg.elem_from_feedback:
                    self._collect_elements(rec, r - believed)
                if cfg.elem_metas and cfg.meta_birth == "feedback":
                    self._collect_metas(rec, r - believed)
            t, k = self._tilt_each(rec.feats, r)
            total += t
            n += k
        return total / max(1, n)

    def learn_belief_each(self, traj: list[Record]) -> float:
        """Nothing is divided: every decision molette tilts by the whole error of the
        decision (R - V), modulated by its OWN belief:  note += alpha (1 - note^2)^res (R - V)."""
        if not traj:
            return 0.0
        cfg, w = self.cfg, self.w
        returns, g = [], 0.0
        for rec in reversed(traj):
            g = rec.reward + cfg.gamma * g
            returns.append(g)
        returns.reverse()
        prior = [self.value(rec.feats) for rec in traj]
        total = 0.0
        for rec, r, v in zip(traj, returns, prior):
            err = r - v
            total += abs(err)
            if cfg.construction and cfg.elem_from_feedback:
                self._collect_elements(rec, err)
            if cfg.construction and cfg.elem_metas and cfg.meta_birth == "feedback":
                self._collect_metas(rec, err)
            self._tilt_by_own_belief(rec.feats, err)
        return total / len(traj)

    def _tilt_by_own_belief(self, feats, err: float) -> None:
        w, res, a = self.w, self.cfg.resistance, self.alpha
        for f in set(feats):
            x = w.get(f, 0.0)
            w[f] = x + a * max(0.0, 1.0 - min(1.0, x * x)) ** res * err

    def _tilt_each(self, feats, r: float) -> tuple[float, int]:
        """Each decision molette tilts toward the result on its own, modulated by its own
        belief (nothing is divided among them):  note += step * (1 - note^2)^res * (R - note)."""
        cfg, w, seen = self.cfg, self.w, self.seen
        total, n = 0.0, 0
        for f in set(feats):
            v = w.get(f, 0.0)
            err = r - v
            total += abs(err)
            n += 1
            k = seen.get(f, 0) + 1
            seen[f] = k
            # the mean of its outcomes at first, with one neutral prior outcome: a note
            # never reaches +-1 exactly, so (1 - note^2) never freezes it
            step = max(self.alpha, 1.0 / (k + 1))
            w[f] = v + step * max(0.0, 1.0 - v * v) ** cfg.resistance * err
        return total, n

    def parts_note(self, S: tuple[str, ...], after: dict) -> float:
        """What the parts of a combination say: the mean note of the active molettes whose
        watchers are a strict subset of S (the single watchers and the smaller metas)."""
        w = self.w
        notes = [w.get(("p", m, after.get(m)), 0.0) for m in S]
        for T in self.metas:
            if len(T) < len(S) and set(T) <= set(S):
                notes.append(w.get(("m", T, tuple(after.get(m) for m in T)), 0.0))
        return sum(notes) / len(notes)

    @staticmethod
    def level(f: Feature) -> int:
        """Level of a decision molette = number of watchers it looks at."""
        return len(f[1]) if f[0] in ("m", "mt") else 1

    def _context(self) -> tuple[str, ...] | None:
        return self.cfg.md_context

    def _collect(self, rec: Record, err: float, result: float | None = None) -> None:
        """Accumulate, for each combination present, how far the outcome is from what is
        already believed: the error of the decision (summed rules) or, with ``result``
        (independent rule), the outcome minus what the combination's parts say."""
        cfg = self.cfg
        after = rec.after
        ctx = self._context()
        keys = [k for k in after if ctx is None or k in ctx]
        cand = self.cand
        sets: list[tuple[str, ...]] = []
        for a in rec.changed:
            if ctx is not None and a not in ctx:
                continue
            others = [b for b in keys if b != a]
            for b in others:
                sets.append(tuple(sorted((a, b))))
            if cfg.md_max_arity >= 3 and len(keys) <= cfg.md_direct_triples_upto:
                for i, b in enumerate(others):
                    for c in others[i + 1 :]:
                        sets.append(tuple(sorted((a, b, c))))
            if cfg.md_max_union and not cfg.net:
                # correlation between two decision molettes: the union of two metas
                for S1 in self.by_member.get(a, ()):
                    for S2 in self.metas:
                        if S2 is S1 or not set(S1) & set(S2):
                            continue  # only molettes that share a watcher are linked
                        U = tuple(sorted(set(S1) | set(S2)))
                        if len(S1) < len(U) <= cfg.md_max_union:
                            sets.append(U)
            if cfg.md_max_arity >= 3:
                for S in self.by_member.get(a, ()):
                    if len(S) >= cfg.md_max_arity:
                        continue
                    for c in keys:
                        if c not in S:
                            sets.append(tuple(sorted(S + (c,))))
        if cfg.md_max_union and cfg.net:
            # with the net: the union of two of its groups that share a watcher (a compromise
            # of compromises), tried on every decision, whatever was played
            sets.extend(self._net_unions())
        for S in set(sets):
            if S in self.meta_set or self.is_blocked(S):
                continue
            key = (S, tuple(after.get(m) for m in S))
            e = err if result is None else result - self.parts_note(S, after)
            st = cand.get(key)
            if st is None:
                st = cand[key] = [0, 0.0, 0.0]
            st[0] += 1
            st[1] += e
            st[2] += e * e
            self._touched.add(key)

    def _net_unions(self) -> list[tuple[str, ...]]:
        """Unions of two groups of the net that share a watcher (cached per net)."""
        key = tuple(self.obs.metas)
        if getattr(self, "_unions_key", None) != key:
            groups = [g for g in self.obs.net() if isinstance(g, tuple)]
            out = set()
            for i, g1 in enumerate(groups):
                for g2 in groups[i + 1 :]:
                    if set(g1) & set(g2):
                        U = tuple(sorted(set(g1) | set(g2)))
                        if len(U) <= self.cfg.md_max_union:
                            out.add(U)
            self._unions_key, self._unions = key, sorted(out)
        return self._unions

    def grow(self) -> list[tuple[str, ...]]:
        """Create the meta decision molettes whose combination is a real compromise."""
        cfg = self.cfg
        made = []
        best: dict[tuple[str, ...], float] = {}
        for key in self._touched:
            st = self.cand.get(key)
            if st is None:
                continue
            S = key[0]
            if S in self.meta_set:
                continue
            n, s, ss = st
            if n < cfg.md_min_count:
                continue
            mean = s / n
            var = max(ss / n - mean * mean, 1e-9)
            z = abs(mean) / math.sqrt(var / n)
            if abs(mean) >= cfg.md_min_effect and z >= cfg.md_z:
                best[S] = max(best.get(S, 0.0), z)
        self._touched.clear()
        for S, _z in sorted(best.items(), key=lambda t: -t[1]):
            if self.add_meta(S):
                self.created_from_feedback += 1
                made.append(S)
                if cfg.net_from_feedback:
                    self.obs.adopt(S)  # in the net on probation; pruning takes it out
        if made:
            self.cand = {k: v for k, v in self.cand.items() if k[0] not in self.meta_set}
        if len(self.cand) > cfg.md_max_candidates:
            keep = sorted(self.cand.items(), key=lambda kv: -kv[1][0])[: cfg.md_max_candidates // 2]
            self.cand = dict(keep)
        return made

    def utility(self) -> dict[tuple[str, ...], float]:
        """How much each meta decision molette weighs. Summed rules: the largest |note| it
        holds. Independent rule (each molette is its own estimate): the largest gap
        between its note and what its parts say — a combination that says nothing more
        than its parts is useless."""
        util = {S: 0.0 for S in self.metas}
        independent = self.cfg.backup == "independent"
        for f, v in self.w.items():
            if f[0] == "m" and f[1] in util:
                if independent:
                    S, joint = f[1], f[2]
                    v = v - self.parts_note(S, dict(zip(S, joint)))
                util[f[1]] = max(util[f[1]], abs(v))
        return util

    def prune(self) -> list[tuple[str, ...]]:
        """Drop the meta decision molettes born from feedback that turned out useless
        (utility < md_prune_ratio x the best). Old enough ones only; never recreated."""
        cfg = self.cfg
        util = self.utility()
        if not util:
            return []
        top = max(util.values())
        gone = [
            S
            for S, u in util.items()
            if self.origin.get(S) == "feedback"
            and self.episode - self.born.get(S, 0) >= self.probation(S)
            and u < cfg.md_prune_ratio * top
        ]
        if not gone:
            return []
        dead = set(gone)
        self.metas = [S for S in self.metas if S not in dead]
        self.meta_set -= dead
        for S in dead:
            self.blocked[S] = self.episode + cfg.md_block_for
        for S in gone:
            for m in S:
                self.by_member[m] = [x for x in self.by_member[m] if x != S]
        self.w = {f: v for f, v in self.w.items() if not (f[0] in ("m", "mt") and f[1] in dead)}
        self.cand = {k: v for k, v in self.cand.items() if k[0] not in dead}
        self.pruned += len(gone)
        if cfg.net_from_feedback:
            for S in gone:
                self.obs.release(S)
        return gone



    def size(self) -> int:
        return len(self.w)
