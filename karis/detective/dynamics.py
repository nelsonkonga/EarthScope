"""Eva's dynamics of each trend, at the right level of abstraction (RESULTS.md § 27).

The lesson of the curves (RESULTS.md § 26): Eva reads a series in levels of meta molettes (2, 4, 8…
readings joined), a transition between two dynamics proven only beyond chance, the noise measured
where it is — around her dynamics, persistence included. Read month by month, a climate series
fools any such reading: a month resembles the one before, and the mean of a few months varies far
more than independent readings would (Eva saw 1–5 « regimes » in red noise without any trend). The
level of a 45-year trend is the year: the seasons and the persistence of a few months are below it.

- ``annual``: her dynamics of one series, read on its yearly values: one steady dynamic, or
  regimes and the years where one gave way to the next (each with its rate per decade).
- ``shared``: the transitions several variables of one region make together (the transitions'
  own meta molettes), against chance (each variable's transitions moved at random).

Measured on 68 series (checks/earth_dynamics.py): on a steady trend plus noise as persistent as
the series, Eva reports regimes 5.5 % of the time; Pettitt's test, which the detective used to give
« the year the level jumped », reports a jump 65 % of the time — a trend has no single level, so
the test finds where it crosses its own mean.
"""

from __future__ import annotations

import random

from eva.heatmaps import RADIUS
from eva.shape import Shape

CONTROL = {"eva": 0.055, "pettitt": 0.647, "series": 68}  # checks/earth_dynamics.py


def annual(tr: dict) -> dict | None:
    """Eva's dynamics of one trend report's yearly values."""
    a = tr.get("annual") or {}
    years, values = a.get("years") or [], a.get("values") or []
    if len(years) < 8:
        return None
    s = Shape(list(zip(years, values)), degree=1)  # the question: a trend per decade, and when it changed
    ps = [P for P in s.pieces if P.size >= 2]
    dyn = [{"from": int(s.xs[P.lo]), "to": int(s.xs[P.hi]), "per_decade": s.slope(P) * 10, "years": P.size} for P in ps]
    turns = [_meeting(s, A, B) for A, B in zip(ps, ps[1:])]
    return {"dynamics": dyn, "transitions": turns, "persistence": s.persistence, "text": _text(dyn, turns)}


def _meeting(s: Shape, A, B, steps: int = 400) -> float:
    """When one dynamic gave way to the next: where they meet (two dynamics glued: the union is the
    integral) when it lies inside their two stretches — a change of slope is proven only some years
    after it happened — else the boundary between their readings. A dynamic may carry transitions
    (a curve): of the places where the two cross, the nearest to the boundary between them."""
    lo, hi = s.xs[A.lo], s.xs[B.hi]
    mid = (s.xs[A.hi] + s.xs[B.lo]) / 2

    def diff(t):
        return s.line(A, t) - s.line(B, t)

    ts = [lo + (hi - lo) * k / steps for k in range(steps + 1)]
    ds = [diff(t) for t in ts]
    crossings = []
    for (t0, d0), (t1, d1) in zip(zip(ts, ds), zip(ts[1:], ds[1:])):
        if d0 == 0.0:
            crossings.append(t0)
        elif d0 * d1 < 0:
            for _ in range(60):  # halve the bracket until it is a point
                tm = (t0 + t1) / 2
                dm = diff(tm)
                if (dm < 0) == (d0 < 0):
                    t0, d0 = tm, dm
                else:
                    t1 = tm
            crossings.append((t0 + t1) / 2)
    if ds[-1] == 0.0:
        crossings.append(ts[-1])
    if crossings:
        return round(min(crossings, key=lambda t: abs(t - mid)), 1)
    return mid


def _text(dyn: list, turns: list = ()) -> str:
    if not dyn:
        return ""
    if len(dyn) == 1:
        d = dyn[0]
        return (f"one steady dynamic from {d['from']} to {d['to']} ({d['per_decade']:+.3g} per decade): "
                f"no change of regime stands out from the year-to-year swings")
    parts = "; ".join(f"{d['from']}–{d['to']}: {d['per_decade']:+.3g} per decade" for d in dyn)
    when = ", ".join(f"around {t:.0f}" for t in turns)
    return f"{len(dyn)} dynamics ({parts}); the dynamic changed {when}"


def shared(res: dict, dyns: dict, draws: int = 2000, seed: int = 0) -> list[dict]:
    """Years where several variables of one region changed dynamics together (their transitions
    warm each other: within 2·RADIUS years, as neighbouring cells of a lattice), and how often chance
    would gather as many (each variable's transitions placed at random)."""
    out = []
    by_region: dict = {}
    for u, info in res["units"].items():
        d = dyns.get(u)
        if d and d["transitions"]:
            by_region.setdefault(info["region"], {})[u] = d["transitions"]
    for reg, tr in by_region.items():
        if len(tr) < 2:
            continue
        years = [y for u in tr for y in res["trends"][u]["annual"]["years"]]
        lo, hi = min(years) + 1, max(years) - 1
        k, at, members = _densest(tr)
        if k < 2:
            continue
        rng = random.Random(seed)
        hits = sum(_densest({u: [rng.uniform(lo, hi) for _ in ys] for u, ys in tr.items()})[0] >= k for _ in range(draws))
        p = (hits + 1) / (draws + 1)
        name = next(i["region_name"] for i in res["units"].values() if i["region"] == reg)
        out.append({"region": reg, "region_name": name, "year": round(at), "members": members, "p": p,
                    "of": len([u for u, i in res["units"].items() if i["region"] == reg])})
    return out


def _densest(tr: dict):
    pts = [(y, u) for u, ys in tr.items() for y in ys]
    best = (0, None, [])
    for y, _ in pts:
        us = sorted({u for z, u in pts if abs(z - y) <= 2 * RADIUS})
        if len(us) > best[0]:
            best = (len(us), y, us)
    return best


def read(res: dict) -> dict:
    """Everything above for one investigation."""
    units = {u: annual(tr) for u, tr in res["trends"].items()}
    units = {u: d for u, d in units.items() if d}
    return {"units": units, "shared": shared(res, units), "control": CONTROL}
