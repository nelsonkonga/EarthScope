"""Molettes standard (n6), molettes de temps (n7) et N-molettes de temps (n13).

A ``Channel`` watches one stream of hashable values (a watcher, or a tuple of watchers
for a meta channel). It keeps, with sparse counts only:

- the standard molette ``P(next value | position)``;
- the time molette, as a hazard ``h(d | position)`` = probability to change at the d-th
  tick spent in a position, given it lasted d-1 ticks;
- a lazily grown hierarchy of ``Rhythm`` levels: level k+1 watches the stream of
  transitions of level k (symbols ``(position, log2 duration)``).

Counts are shared by every perspective; the current positions live in a ``Cursor`` per
perspective, so an Eva holding several perspectives feeds the same molettes from each.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Hashable

LN2 = math.log(2.0)


def bucket(d: int) -> int:
    """Log-scale duration bucket: 1,2,3,4 exact, then 5-8 -> 5, 9-16 -> 6, 17-32 -> 7..."""
    if d <= 4:
        return d
    return (d - 1).bit_length() + 2


class Hazard:
    """Discrete-time survival counts by position, durations capped at ``cap``.

    Sparse: ``ev[pos][d]`` = runs that ended (changed) after exactly d ticks,
    ``cen[pos][d]`` = runs cut by the end of an episode after d ticks. The survival
    ``surv(pos, d)`` (runs that lasted at least d ticks) is summed on demand: a position
    only ever sees a handful of distinct durations.
    """

    __slots__ = ("cap", "ev", "cen", "n", "prior", "ticks", "ended")

    def __init__(self, cap: int, prior: str = "half"):
        self.cap = cap
        self.ev: dict[Hashable, dict[int, int]] = {}
        self.cen: dict[Hashable, dict[int, int]] = {}
        self.n = 0  # records received: the molette moved n times
        # smoothing of h: toward 1/2 ("half"), or toward the position's own mean rate of
        # change, ended runs / ticks spent there ("mean": unbiased for slow dynamics)
        self.prior = prior
        self.ticks: dict[Hashable, int] = {}
        self.ended: dict[Hashable, int] = {}

    def record(self, pos, d: int, ended: bool) -> None:
        if d <= 0:
            return
        self.n += 1
        d = min(d, self.cap)
        table = self.ev if ended else self.cen
        row = table.get(pos)
        if row is None:
            row = table[pos] = {}
        row[d] = row.get(d, 0) + 1
        try:
            ticks, done = self.ticks, self.ended
        except AttributeError:  # molette saved before these counters existed
            ticks, done = self.ticks, self.ended = {}, {}
            self.prior = "half"
        ticks[pos] = ticks.get(pos, 0) + d
        if ended:
            done[pos] = done.get(pos, 0) + 1
        if ended:
            self.cen.setdefault(pos, {})
        else:
            self.ev.setdefault(pos, {})

    def support(self, pos, d: int) -> int:
        """Runs in ``pos`` that lasted at least ``d`` ticks."""
        d = min(d, self.cap)
        n = 0
        for row in (self.ev.get(pos), self.cen.get(pos)):
            if row:
                for k, c in row.items():
                    if k >= d:
                        n += c
        return n

    def h(self, pos, d: int) -> float:
        """Hazard of changing at tick ``d`` (Laplace-smoothed toward 1/2)."""
        d = max(1, min(d, self.cap))
        ev = self.ev.get(pos)
        if ev is None:
            return 0.5
        if getattr(self, "prior", "half") == "mean":
            h0 = (self.ended.get(pos, 0) + 0.5) / (self.ticks.get(pos, 0) + 1.0)
            return (ev.get(d, 0) + h0) / (self.support(pos, d) + 1.0)
        return (ev.get(d, 0) + 0.5) / (self.support(pos, d) + 1.0)

    def size(self) -> int:
        return sum(len(r) for r in self.ev.values()) + sum(len(r) for r in self.cen.values())


class Transitions:
    """Standard molette: ``P(next | position)`` with Laplace smoothing over the alphabet."""

    __slots__ = ("counts", "totals", "alphabet", "n")

    def __init__(self):
        self.counts: dict[Hashable, dict[Hashable, int]] = defaultdict(dict)
        self.totals: dict[Hashable, int] = defaultdict(int)
        self.alphabet: set = set()
        self.n = 0  # records received: the molette moved n times

    def record(self, pos, nxt) -> None:
        self.n += 1
        row = self.counts[pos]
        row[nxt] = row.get(nxt, 0) + 1
        self.totals[pos] += 1
        self.alphabet.add(nxt)
        self.alphabet.add(pos)

    def p(self, pos, nxt) -> float:
        # Values other than ``pos`` it could move to: alphabet minus itself, plus one unseen.
        k = max(1, len(self.alphabet) - (1 if pos in self.alphabet else 0)) + 1
        row = self.counts.get(pos)
        n = row.get(nxt, 0) if row else 0
        return (n + 1.0 / k) / (self.totals.get(pos, 0) + 1.0)

    def distribution(self, pos) -> dict[Hashable, float]:
        return {v: self.p(pos, v) for v in self.alphabet if v != pos}

    def size(self) -> int:
        return sum(len(r) for r in self.counts.values())


class Rhythm:
    """One level of the N-time hierarchy (level >= 2).

    It watches the stream of symbols emitted by the transitions of the level below, with
    its own transitions, its own run-length hazard, and possibly a next level.
    """

    def __init__(self, level: int, cfg):
        self.level = level
        self.cfg = cfg
        self.trans = Transitions()
        self.runs = Hazard(cfg.run_cap, cfg.hazard_prior)
        self.events = 0
        self.child: Rhythm | None = None

    def size(self) -> int:
        return self.trans.size() + self.runs.size() + (self.child.size() if self.child else 0)

    def depth(self) -> int:
        return 1 + (self.child.depth() if self.child else 0)


@dataclass
class LevelCursor:
    pos: Hashable = None
    run: int = 0


@dataclass
class Cursor:
    """Per-perspective state of one channel: position, ticks spent there, upper levels."""

    pos: Hashable = None
    dwell: int = 0
    started: bool = False
    levels: list[LevelCursor] = field(default_factory=list)
    last_run: dict = field(default_factory=dict)  # position -> bucket of its previous run


class Channel:
    """A watcher (or a meta combination) with its standard, time and N-time molettes."""

    def __init__(self, name, cfg, members: tuple[str, ...] | None = None):
        self.name = name
        self.cfg = cfg
        self.members = members  # None for a base watcher, the watcher names for a meta
        self.trans = Transitions()  # n6
        self.trans_d: Transitions | None = Transitions() if cfg.trans_by_dwell else None  # P(next | pos, time)
        self.time = Hazard(cfg.dwell_cap, cfg.hazard_prior)  # n7
        self.time_ctx = Hazard(cfg.dwell_cap, cfg.hazard_prior)  # n7 conditioned by the level-2 position
        self.rhythm: Rhythm | None = None  # n13, created lazily
        self.events = 0
        self.changes_seen = 0

    # ------------------------------------------------------------------ learning
    def tick(self, cur: Cursor, value) -> bool:
        """Feed the value observed at this tick. Returns True if the channel changed."""
        if not cur.started:
            cur.started, cur.pos, cur.dwell = True, value, 0
            return False
        cur.dwell += 1
        if value == cur.pos:
            return False
        self.trans.record(cur.pos, value)
        if getattr(self, "trans_d", None) is not None:
            self.trans_d.record((cur.pos, bucket(cur.dwell)), value)
        self.time.record(cur.pos, cur.dwell, ended=True)
        ctx = self._ctx(cur)
        if ctx is not None:
            self.time_ctx.record((cur.pos, ctx), cur.dwell, ended=True)
        self.events += 1
        self._emit(cur, 0, (cur.pos, bucket(cur.dwell)))
        cur.last_run[cur.pos] = bucket(cur.dwell)
        cur.pos, cur.dwell = value, 0
        return True

    def end(self, cur: Cursor) -> None:
        """Episode over: censor the open runs, reset the cursor."""
        if cur.started and cur.dwell > 0:
            self.time.record(cur.pos, cur.dwell, ended=False)
            ctx = self._ctx(cur)
            if ctx is not None:
                self.time_ctx.record((cur.pos, ctx), cur.dwell, ended=False)
        node, i = self.rhythm, 0
        while node is not None and i < len(cur.levels):
            lc = cur.levels[i]
            if lc.pos is not None and lc.run > 0:
                node.runs.record(lc.pos, lc.run, ended=False)
            node, i = node.child, i + 1
        cur.pos, cur.dwell, cur.started, cur.levels, cur.last_run = None, 0, False, [], {}

    def _level(self, idx: int) -> Rhythm | None:
        node = self.rhythm
        for _ in range(idx):
            if node is None:
                return None
            node = node.child
        return node

    def _emit(self, cur: Cursor, idx: int, symbol) -> None:
        """Push a transition symbol into level ``idx + 2`` of the hierarchy.

        The level only comes to life when its own stream actually transitions within an
        episode (and the level below has seen ``min_level_events`` transitions): a stream
        that never moves twice in an episode (a cell of a board filled once) gets no
        molette that would never move."""
        cfg = self.cfg
        if idx + 2 > cfg.max_time_depth:
            return
        while len(cur.levels) <= idx:
            cur.levels.append(LevelCursor())
        lc = cur.levels[idx]
        if lc.pos is None:
            lc.pos, lc.run = symbol, 1
            return
        if symbol == lc.pos:
            lc.run += 1
            return
        if idx == 0:
            if self.rhythm is None:
                if self.events < cfg.min_level_events:
                    lc.pos, lc.run = symbol, 1
                    return
                self.rhythm = Rhythm(2, cfg)
            node = self.rhythm
        else:
            parent = self._level(idx - 1)
            if parent is None:
                return
            if parent.child is None:
                if parent.events < cfg.min_level_events:
                    lc.pos, lc.run = symbol, 1
                    return
                parent.child = Rhythm(idx + 2, cfg)
            node = parent.child
        node.trans.record(lc.pos, symbol)
        node.runs.record(lc.pos, lc.run, ended=True)
        node.events += 1
        self._emit(cur, idx + 1, (lc.pos, bucket(lc.run)))
        lc.pos, lc.run = symbol, 1

    # ---------------------------------------------------------------- prediction
    @staticmethod
    def _ctx(cur: Cursor):
        """Context the 2-molette gives the time molette: how long the previous run in
        the same position lasted (the rhythm of this position)."""
        return cur.last_run.get(cur.pos)

    def hazard(self, cur: Cursor) -> float:
        """Probability to change at the next tick, given the cursor."""
        d = cur.dwell + 1
        ctx = self._ctx(cur)
        if ctx is not None and self.time_ctx.support((cur.pos, ctx), d) >= self.cfg.ctx_min_support:
            return self.time_ctx.h((cur.pos, ctx), d)
        return self.time.h(cur.pos, d)

    def p_next(self, cur: Cursor, value) -> float:
        """Probability that the next tick shows ``value`` (standard x time molettes)."""
        if not cur.started:
            return 1.0
        h = self.hazard(cur)
        if value == cur.pos:
            return 1.0 - h
        return h * self.trans.p(cur.pos, value)

    def surprise(self, cur: Cursor, value) -> float:
        """Bits the molettes 'move' if the next tick shows ``value`` (n11): the standard
        x time molettes, plus every higher time derivative the transition would reach."""
        bits = -math.log(max(self.p_next(cur, value), 1e-12)) / LN2
        if cur.started and value != cur.pos:
            bits += self.levels_surprise(cur)
        return bits

    def levels_surprise(self, cur: Cursor) -> float:
        """Movement of the N-time molettes (n13) if the channel changes at the next tick:
        the transition emits (position, duration) into level 2; if that changes level 2's
        position, level 2 emits into level 3, and so on."""
        symbol = (cur.pos, bucket(cur.dwell + 1))
        node, i, bits = self.rhythm, 0, 0.0
        while node is not None and i < len(cur.levels):
            lc = cur.levels[i]
            if lc.pos is None:
                break
            # the run of lc.pos has lasted lc.run symbols: does it end with this one?
            h = node.runs.h(lc.pos, lc.run) if node.runs.ev.get(lc.pos) else 0.5
            if symbol == lc.pos:  # the run of this level just goes on
                bits += -math.log(max(1.0 - h, 1e-12)) / LN2
                break
            bits += -math.log(max(h * node.trans.p(lc.pos, symbol), 1e-12)) / LN2
            symbol = (lc.pos, bucket(lc.run))
            node, i = node.child, i + 1
        return bits

    def shift(self, cur: Cursor, value) -> float:
        """L1 displacement of the standard + time distributions if ``value`` is observed."""
        if not cur.started:
            return 0.0
        h = self.hazard(cur)
        n_t = self.time.support(cur.pos, cur.dwell + 1) + 1.0
        if value == cur.pos:
            return 2.0 * h / (n_t + 1.0)
        n = self.trans.totals.get(cur.pos, 0) + 1.0
        p = self.trans.p(cur.pos, value)
        return 2.0 * (1.0 - h) / (n_t + 1.0) + 2.0 * (1.0 - p) / (n + 1.0)

    def project(self, states: dict, prune: float = 1e-3) -> dict:
        """Energy profile, one tick ahead: from a distribution over ``(position, dwell)``
        return the distribution the standard x time molettes expect at the next tick.
        Nothing is simulated: this is only the molettes' own prediction."""
        out: dict = defaultdict(float)
        cap = self.cfg.dwell_cap
        for (v, d), p in states.items():
            h = self.time.h(v, d + 1) if self.time.ev.get(v) else 0.0
            if h < 1.0:
                out[(v, min(d + 1, cap))] += p * (1.0 - h)
            if h <= 0.0:
                continue
            row = None
            if getattr(self, "trans_d", None) is not None:  # the standard transition at this time in the position
                key = (v, bucket(d + 1))
                n = self.trans_d.totals.get(key, 0)
                if n >= self.cfg.trans_by_dwell_min:
                    row = self.trans_d.counts[key]
            if row is None:
                row = self.trans.counts.get(v)
                if not row:
                    continue
                n = self.trans.totals[v]
            for x, c in row.items():
                q = p * h * c / n
                if q >= prune:
                    out[(x, 0)] += q
        z = sum(out.values()) or 1.0
        return {k: q / z for k, q in out.items() if q / z >= prune}

    @staticmethod
    def marginal(states: dict) -> dict:
        m: dict = defaultdict(float)
        for (v, _d), p in states.items():
            m[v] += p
        return m

    @staticmethod
    def entropy(dist: dict) -> float:
        return -sum(p * math.log2(p) for p in dist.values() if p > 0)

    def depth(self) -> int:
        """Number of time levels in use (1 = only the time molette)."""
        return 1 + (self.rhythm.depth() if self.rhythm else 0)

    def size(self) -> int:
        return (
            self.trans.size()
            + self.time.size()
            + self.time_ctx.size()
            + (self.rhythm.size() if self.rhythm else 0)
        )
