"""Where and when the dynamics changed, and of which type — over every grid cell (RESULTS.md § 30).

The user (2026-11-13): « la dynamique est une heatmap ; les endroits de concentration sont les
molettes […] les transitions de dynamiques ont aussi leur heatmap, qui représente la concentration
des transitions : les types de transitions […] les types de types de transition » — applied to the
NASA Space Apps detective: « veille à ce que ça aide pour le NASA space challenge ».

A region's mean blurs what its cells do. Here every grid cell's yearly series is read by Eva at the
level of a trend (eva/shape.py, ``degree=1``: a trend per decade and the transitions between
trends). Each transition is a reading of the heatmap of transitions:

- *when*: the year where the two dynamics meet;
- *which type*: what jumps there (the trend, or the level) and which way.

A concentration — many cells with a transition of the same type within the years that warm each
other (± 2·RADIUS) — is a regional change of dynamic. It is told only against chance: the same
fields with no change of dynamic at all (each cell's steady trend plus its own residuals, the years
of all the cells shuffled together in blocks, which keeps how the cells move together and how a year
resembles the next). How often does chance gather as many cells, anywhere, of any type (the largest
concentration of each shuffled field: the whole search is paid for)?

Types of types: in cells that changed twice, which type followed which (the bridge between two types
of transitions), counted and judged the same way.
"""

from __future__ import annotations

import math
import random

import numpy as np

from eva.heatmaps import CHANCE, RADIUS
from eva.shape import Shape

from . import stats

TYPES = {(1, 1): "trend turned upward", (1, -1): "trend turned downward",
         (0, 1): "level jumped up", (0, -1): "level dropped"}


def _cell_years(cells: list) -> tuple[list[int], list[tuple[float, float, list[float]]]]:
    """Every cell's yearly means over the years all of them have."""
    anns = [(la, lo, stats.annual_means(s)) for la, lo, s in cells]
    anns = [(la, lo, a) for la, lo, a in anns if len(a) >= 10]
    if not anns:
        return [], []
    years = sorted(set.intersection(*(set(a) for _, _, a in anns)))
    return years, [(la, lo, [a[y] for y in years]) for la, lo, a in anns]


def transitions(years: list[int], values: list[float]) -> list[tuple[float, tuple]]:
    """Eva's transitions of one yearly series: (year, type), type = (kind, sign of what jumps)."""
    return _read(years, values)[0]


def _read(years: list[int], values: list[float]) -> tuple[list[tuple], list[float]]:
    """Eva's transitions of one yearly series, and what remains around her dynamics (the noise where
    she measures it)."""
    s = Shape(list(zip(years, values)), degree=1)
    out = []
    for t in s.transitions:
        k = t["kind"]
        if k is None or k > 1:
            continue
        out.append((t["at"], (k, 1 if t["jumps"][k] > 0 else -1)))
    piece = [None] * len(s.xs)
    for P in s.pieces:
        for i in range(P.lo, P.hi + 1):
            piece[i] = P
    order = sorted(range(len(years)), key=lambda i: years[i])  # Shape sorts its readings by place
    res = [0.0] * len(years)
    for j, i in enumerate(order):
        res[i] = values[i] - s.line(piece[j], years[i])
    return out, res


def _concentrations(per_cell: list[list[tuple]], years: list[int]) -> dict:
    """For each (type, year): the cells with a transition of that type within ± 2·RADIUS years."""
    out = {}
    for c, tr in enumerate(per_cell):
        for at, ty in tr:
            for y in years:
                if abs(at - y) <= 2 * RADIUS:
                    out.setdefault((ty, y), set()).add(c)
    return out


def _bridges(per_cell: list[list[tuple]]) -> dict:
    """Types of types: in each cell, every transition type followed by the next one."""
    out = {}
    for c, tr in enumerate(per_cell):
        tr = sorted(tr)
        for (a1, t1), (a2, t2) in zip(tr, tr[1:]):
            out.setdefault((t1, t2), set()).add(c)
    return out


def _shuffled(years: list[int], series: list[list[float]], residuals: list[list[float]], rng: random.Random,
              block: int) -> list[list[float]]:
    """The same fields with no change of dynamic: each cell's steady trend (Sen) plus what remains
    around Eva's dynamics of it, the years of all the cells moved together in blocks (how the cells
    move together and how a year resembles the next are kept; no change of dynamic is left in it)."""
    t = np.asarray(years, float)
    n = len(years)
    starts = list(range(0, n, block))
    rng.shuffle(starts)
    order = [i for s0 in starts for i in range(s0, min(s0 + block, n))]
    out = []
    for v, r in zip(series, residuals):
        v = np.asarray(v, float)
        b = stats.sen_slope(t, v)
        a = float(np.median(v - b * t))
        out.append(list(a + b * t + np.asarray(r, float)[order]))
    return out


def _block(residuals: list[list[float]]) -> int:
    """Blocks as long as what remains stays alike: (1 + φ) / (1 − φ) years, φ its mean lag-1."""
    phis = []
    for r in residuals:
        r = np.asarray(r, float)
        r = r - r.mean()
        ss = float(np.sum(r * r))
        if ss > 0:
            phis.append(float(np.sum(r[1:] * r[:-1]) / ss))
    phi = min(max(float(np.mean(phis)) if phis else 0.0, 0.0), 0.9)
    return max(1, round((1 + phi) / (1 - phi)))


def read_cells(cells: list, draws: int = 99, seed: int = 0, min_share: float = 0.1) -> dict:
    """The changes of dynamic of one variable over a region's grid cells, against chance."""
    years, cs = _cell_years(cells)
    return read_years(years, cs, draws=draws, seed=seed, min_share=min_share)


def read_years(years: list[int], cs: list[tuple[float, float, list[float]]], draws: int = 99, seed: int = 0,
               min_share: float = 0.1) -> dict:
    """The same, from every cell's yearly values already made (``cs``: (lat, lon, values over
    ``years``)): a yearly indicator (detective/land.py) is read like a variable's annual means."""
    if len(cs) < 4 or len(years) < 20:
        return {"cells": len(cs), "changes": [], "bridges": []}
    series = [v for _, _, v in cs]
    reads = [_read(years, v) for v in series]
    per_cell, residuals = [r[0] for r in reads], [r[1] for r in reads]
    seen = _concentrations(per_cell, years)
    links = _bridges(per_cell)
    block = _block(residuals)
    rng = random.Random(seed)
    top, top_b = [], []
    for _ in range(draws):  # the largest concentration chance makes anywhere, of any type, any year
        sh = _shuffled(years, series, residuals, rng, block)
        pc = [transitions(years, v) for v in sh]
        conc = _concentrations(pc, years)
        top.append(max((len(c) for c in conc.values()), default=0))
        top_b.append(max((len(c) for c in _bridges(pc).values()), default=0))

    def p_of(k, tops):
        return (1 + sum(x >= k for x in tops)) / (1 + len(tops))

    changes, used = [], set()
    for (ty, y), cells_in in sorted(seen.items(), key=lambda kv: (-len(kv[1]), kv[0][1])):
        free = cells_in - used
        if len(free) < max(2, min_share * len(cs)):
            continue
        p = p_of(len(cells_in), top)
        if p > CHANCE:
            break  # sorted by size: the next ones are smaller still (99 draws: p = 0.01 = chance never did as much)
        ats = [at for c in cells_in for at, t in per_cell[c] if t == ty and abs(at - y) <= 2 * RADIUS]
        changes.append({"type": TYPES[ty], "kind": ty[0], "sign": ty[1], "year": round(float(np.median(ats)), 1),
                        "cells": len(cells_in), "of": len(cs), "p": p,
                        "where": [[cs[c][0], cs[c][1]] for c in sorted(cells_in)]})
        used |= cells_in
    bridges = []
    for (t1, t2), cells_in in sorted(links.items(), key=lambda kv: -len(kv[1])):
        if len(cells_in) < max(2, min_share * len(cs)):
            continue
        p = p_of(len(cells_in), top_b)
        if p <= CHANCE:
            bridges.append({"from": TYPES[t1], "to": TYPES[t2], "cells": len(cells_in), "of": len(cs), "p": p})
    return {"cells": len(cs), "years": [years[0], years[-1]], "block": block,
            "transitions": sum(len(t) for t in per_cell), "chance_largest": sorted(top)[len(top) // 2],
            "changes": changes, "bridges": bridges}


def read(cells_by_unit: dict, labels: dict | None = None, draws: int = 99, seed: int = 0) -> dict:
    """Every unit (a variable over a region) of an investigation."""
    out = {}
    for u, cells in cells_by_unit.items():
        r = read_cells(cells, draws=draws, seed=seed)
        r["label"] = (labels or {}).get(u, u)
        out[u] = r
    return out


def text(u: str, r: dict) -> list[str]:
    """What to tell: each proven change, in words."""
    lines = []
    for c in r.get("changes", []):
        lines.append(f"{r.get('label', u)}: around {c['year']:.0f}, the {c['type'].split(' ', 1)[0]} "
                     f"{c['type'].split(' ', 1)[1]} in {c['cells']} of {c['of']} grid cells together "
                     f"(chance gathers as many anywhere {100 * c['p']:.0f} % of the time or less)")
    return lines
