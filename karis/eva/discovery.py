"""Discovery of the base molettes: which dynamics of a raw watcher to follow.

Nobody tells Eva how to look at a raw numeric stream. From the values it has seen, it
chooses on its own:

- the **grain** (width of a position): the finest grain at which a position still lasts
  several ticks (the time molette keeps a resolution: the dwell is what gives the speed,
  i.e. the first derivative) and each position has been crossed often enough to have a
  distribution;
- the **context**: whether a position must remember where it came from (``(bin, came
  from)``) — kept only if it makes the next transition clearly more predictable (e.g. a
  curve going up or down through the same values).

The molette built on that lens then gives the derivatives by itself: its transition molette
the direction, its time molette the dwell (speed), the change of dwell from one position to
the next the second derivative, and its higher levels the rest (checks/curve_derivatives.py).
Nothing here knows what the stream is.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict


def is_raw_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


class Lens:
    """How a raw numeric watcher becomes a molette position."""

    def __init__(self, width: float, origin: float, context: bool):
        self.width, self.origin, self.context = width, origin, context

    def bin(self, x: float) -> int:
        return math.floor((x - self.origin) / self.width)

    def position(self, x: float, state: dict):
        """``state`` keeps, per stream, the current bin and the bin it came from."""
        b = self.bin(x)
        cur = state.get("bin")
        if cur is None:
            state["bin"], state["came"] = b, None
        elif b != cur:
            state["came"], state["bin"] = cur, b
        return (b, state["came"]) if self.context else b

    def __repr__(self) -> str:
        return f"Lens(width={self.width:.4g}, context={self.context})"


def _runs(episodes, width, origin):
    """Runs (bin, came from, dwell, next bin) of the streams at a grain."""
    out = []
    for xs in episodes:
        prev, came, d = None, None, 0
        for x in xs:
            b = math.floor((x - origin) / width)
            if prev is None:
                prev, d = b, 1
            elif b == prev:
                d += 1
            else:
                out.append((prev, came, d, b))
                came, prev, d = prev, b, 1
    return out


def _cond_entropy(pairs) -> float:
    """H(next | key) in bits over (key, next) pairs."""
    by = defaultdict(Counter)
    for k, nxt in pairs:
        by[k][nxt] += 1
    n = sum(sum(c.values()) for c in by.values()) or 1
    h = 0.0
    for c in by.values():
        t = sum(c.values())
        for v in c.values():
            h -= v / n * math.log2(v / t)
    return h


def discover(episodes, min_dwell: float = 8.0, min_runs: int = 20, min_gain: float = 0.1) -> Lens:
    """Choose the lens of a raw numeric watcher from the streams seen (one list per episode)."""
    xs = [x for e in episodes for x in e]
    lo, hi = min(xs), max(xs)
    span = (hi - lo) or 1.0
    best = fallback = None
    for k in range(1, 16):  # from coarse to fine: keep the finest grain that still works
        width = span / 2**k
        runs = _runs(episodes, width, lo)
        if not runs:
            continue
        dwells = sorted(r[2] for r in runs)
        per_pos = Counter((r[0], r[1]) for r in runs)
        median_runs = sorted(per_pos.values())[len(per_pos) // 2]
        long_enough = dwells[len(dwells) // 2] >= min_dwell
        if long_enough:
            fallback = (width, runs)
        if long_enough and median_runs >= min_runs:
            best = (width, runs)
        elif best is not None:
            break
    if best is None:  # too little seen: the finest grain whose positions still last
        best = fallback or (span / 2, _runs(episodes, span / 2, lo))
    width, runs = best
    h_plain = _cond_entropy(((r[0], r[3]) for r in runs))
    h_ctx = _cond_entropy((((r[0], r[1]), r[3]) for r in runs))
    return Lens(width, lo, context=(h_plain - h_ctx) >= min_gain)
