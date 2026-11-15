"""Chain molettes: the time axis of the net (meta molettes over successive transitions).

An *event* is the transition of a watcher at a tick, ``(watcher, old, new)``. The tracker
counts, per perspective, how often an event B follows an event A within ``seq_window``
ticks, compared with chance. A significant succession becomes a *chain* ``A -> B``; a chain
followed significantly by another event grows (``A -> B -> C``), up to ``seq_max_len``.

A chain is a molette like the others: its value is its *progress* (how many of its events
happened in order, each within the window of the previous one); it gets a statistical
channel (its own transitions and time molette) and a decision molette. Successions that are
no longer significant dissolve. Nothing here knows what the events mean: only when they
happen.
"""

from __future__ import annotations

import math
from collections import defaultdict, deque

Event = tuple  # (watcher, old, new)


class SequenceTracker:
    def __init__(self, cfg):
        self.cfg = cfg
        self.ticks = 0.0
        self.n: dict = defaultdict(float)  # event or chain -> occurrences (completions)
        self.co: dict = defaultdict(float)  # (event-or-chain, event) -> "followed within window"
        self.recent: dict[int, deque] = {}  # perspective -> deque of (tick, [events and completed chains])

    def observe(self, p: int, t: int, items: list) -> None:
        """``items``: the events of this tick and the chains completed at this tick."""
        self.ticks += 1
        for x in items:
            self.n[x] += 1
        rec = self.recent.get(p)
        if rec is None:
            rec = self.recent[p] = deque()
        W = self.cfg.seq_window
        while rec and t - rec[0][0] > W:
            rec.popleft()
        events = [x for x in items if _is_event(x)]
        for t0, prev in rec:
            if 0 < t - t0 <= W:
                for a in prev:
                    for b in events:
                        if not _shares_watcher(a, b):
                            self.co[(a, b)] += 1
        if items:
            rec.append((t, items))

    def forget(self, p: int) -> None:
        self.recent.pop(p, None)

    def decay(self, factor: float) -> None:
        if factor >= 1.0:
            return
        self.ticks *= factor
        for d in (self.n, self.co):
            for k in list(d):
                d[k] *= factor
                if d[k] < 0.5:
                    del d[k]

    def stats(self, a, b) -> tuple[float, float, float]:
        """(count, lift, z) of "b follows a within the window" against independence."""
        W = self.cfg.seq_window
        na, nb = self.n.get(a, 0.0), self.n.get(b, 0.0)
        expected = na * min(1.0, W * nb / max(1.0, self.ticks))
        c = self.co.get((a, b), 0.0)
        if expected <= 0:
            return c, 0.0, 0.0
        return c, c / expected, (c - expected) / math.sqrt(expected)

    def candidates(self, existing: set) -> list:
        """Significant successions not yet chains, best first: (z, chain)."""
        cfg = self.cfg
        out = []
        for (a, b), c in self.co.items():
            if c < cfg.meta_min_count:
                continue
            chain = (_as_chain(a)) + (b,)
            if len(chain) > cfg.seq_max_len or chain in existing:
                continue
            _, lift, z = self.stats(a, b)
            if lift >= cfg.meta_min_lift and z >= cfg.meta_z:
                out.append((z, chain))
        out.sort(key=lambda r: -r[0])
        return out

    def size(self) -> int:
        return len(self.n) + len(self.co)


def _is_event(x) -> bool:
    return isinstance(x, tuple) and len(x) == 3 and isinstance(x[0], str)


def _as_chain(x) -> tuple:
    return (x,) if _is_event(x) else x


def _watchers(x) -> set:
    return {e[0] for e in _as_chain(x)}


def _shares_watcher(a, b) -> bool:
    return bool(_watchers(a) & _watchers(b))


def advance(chain: tuple, prog: int, last: int, events: set, t: int, window: int) -> tuple[int, int]:
    """Progress of a chain after the events of tick ``t``. A completed chain restarts."""
    if prog >= len(chain) or (prog > 0 and t - last > window):
        prog = 0
    if chain[prog] in events:
        return prog + 1, t
    if prog > 0 and chain[0] in events:
        return 1, t
    return prog, last
