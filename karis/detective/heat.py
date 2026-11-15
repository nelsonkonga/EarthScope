"""Eva's heatmaps on Earth series: what leaves its norm together, which way, and what comes first.

The user's theory (2026-11-12, ``eva/heatmaps.py``): a dynamic is a heatmap, its concentrations
are the molettes; meta molettes are intersections of heatmaps; transition molettes are unions —
two heatmaps joined by a transformation of their space, proven by enough evidence (« avec assez
de preuve de l'union de 2 heatmaps on les simplifie en une transition »); the transformations'
own heatmap gives the types of transitions, and the degree above compares those types.

On a stream of months (the extreme lens of ``watch.PhaseLens``):

The heatmap of a dynamic
    Mass on the cells ``(t, s)``: the months ``t`` when the dynamic left its norm, ``s = +1``
    above it, ``-1`` below. Its concentrations are its episodes: months joined when their warmth
    meets (``2·RADIUS`` months apart at most).

The transformations
    The space's own: the identity and the mirror of the sign axis ``(x, ±y)``, and the
    translation along time by ``k`` months ``(x+k, ±y)``. Nothing names a variable or a
    process: a lag is a translation, an opposite reaction a mirror.

Meta molettes — intersections through a transformation
    The cells of B that T brings A onto: the months when both left their norm, in the way T
    says. The content of the meta molette is T: the same way, the opposite way, one month
    later. (The birth test of ``eva.dynamics`` weighs only *when* two dynamics move, not which
    way: the Ross Sea's ice and air go opposite ways in 84 % of their joint departures and no
    meta molette was born there.)

Evidence — chance read at the same moment
    A shared trend puts both dynamics out of their norm late in the record without one month
    moving both. So the chance of a hit is read at the moment it lands (the user's « norme au
    même moment », RESULTS.md § 23): B's share of months out of its norm on that side within
    ``WINDOW`` months of the target. A reading holds when chance would give that many hits less
    often than ``CHANCE`` divided by the number of readings made (Bonferroni, as for the places
    of § 22). Transitions are symmetric: A read through T onto B and B through T⁻¹ onto A must
    both hold.

Transition molettes — unions
    When the intersection covers most of both (``HOLD`` both ways, one of them sure: Wilson
    z = 1), the two heatmaps are one dynamic seen through T: the union is simplified into the
    transition, and each implies the other's cells — the months when one left its norm and the
    other, by the transition, should have but did not: where a detective looks next.

Types of transitions — the degree above
    The transformations weighted by the evidence they carried are the investigation's types of
    transitions. Across regions, the same pair of variables carried by the same transformation
    is the same process — even when their trends run opposite ways.
"""

from __future__ import annotations

import math
from itertools import combinations

from eva.heatmaps import CHANCE, HOLD, RADIUS, chance_tail, components, wilson_low

LAGS = 3  # translations along time tried, both ways (months)
WINDOW = 12  # chance of a hit: B's share of departures within this many months of the target
SHIFTS = range(12, 61)  # persistence: the same reading with B moved 1 to 5 years away, both ways


class Shift:
    """A transformation of the (month, sign) plane: translation by ``k`` months, then ``sign``
    on the sign axis — the same interface as ``eva.heatmaps.Transform``."""

    __slots__ = ("k", "sign", "step", "key", "name")

    def __init__(self, k: int, sign: int):
        self.k, self.sign, self.step = k, sign, 0
        self.key = (k, sign)
        x = f"x{k:+d}" if k else "x"
        self.name = f"({x},{'-' if sign < 0 else ''}y)"

    @property
    def identity(self) -> bool:
        return self.k == 0 and self.sign > 0

    def __call__(self, c):
        return (c[0] + self.k, self.sign * c[1])

    def inverse(self) -> "Shift":
        return Shift(-self.k, self.sign)

    def __repr__(self) -> str:
        return self.name


def transforms(lags: int = LAGS) -> list[Shift]:
    """Identity and mirror, at every translation from −lags to +lags (the untranslated first)."""
    return [Shift(k, s) for k in sorted(range(-lags, lags + 1), key=abs) for s in (1, -1)]


def heatmap(positions: list) -> dict:
    """The months a dynamic left its norm, and which way (extreme lens: −1 below, +1 above)."""
    return {(t, 1 if p > 0 else -1): 1.0 for t, p in enumerate(positions) if p}


def episodes(months) -> list[list[int]]:
    """The concentrations along time: months joined when their warmth meets, earliest first."""
    return sorted((sorted(t for (t,) in c) for c in components({(t,) for t in months})), key=lambda e: e[0])


class Reading:
    """A carried onto B by T: ``hits`` of ``tries`` land on B's cells; ``expected`` hits by
    chance at the same moment; ``p`` the chance of that many or more."""

    __slots__ = ("hits", "tries", "expected", "p", "cells")

    def __init__(self, A: dict, B: dict, t: Shift, T: int, window: int = WINDOW):
        side = {s: sorted(x for (x, y) in B if y == s) for s in (-1, 1)}
        self.hits = self.tries = 0
        self.expected = 0.0
        self.cells = []
        for c in A:
            y = t(c)
            if not 0 <= y[0] < T:
                continue
            self.tries += 1
            if y in B:
                self.hits += 1
                self.cells.append(y)
            lo, hi = max(0, y[0] - window), min(T - 1, y[0] + window)
            self.expected += sum(1 for x in side[y[1]] if lo <= x <= hi) / (hi - lo + 1)
        self.p = chance_tail(self.hits, self.tries, self.expected / self.tries) if self.tries else 1.0

    @property
    def share(self) -> float:
        return self.hits / self.tries if self.tries else 0.0


def _rate(A: dict, B: dict, t: Shift, T: int, extra: int = 0) -> float:
    hits = tries = 0
    for c in A:
        y = t(c)
        y = (y[0] + extra, y[1])
        if 0 <= y[0] < T:
            tries += 1
            hits += y in B
    return hits / tries if tries else 0.0


def persistence_test(A: dict, B: dict, t: Shift, T: int, shifts=SHIFTS) -> tuple[float, float]:
    """The reading against itself with B moved 1 to 5 years away (both ways): each dynamic keeps
    its episodes — a month out of its norm is followed by others, so 93 joint months are not 93
    independent events — and most of its trend; only their alignment month by month is broken.
    Returns (z, p): how far the reading stands above the moved ones, in their spreads, and the
    normal tail of that z."""
    rates = [_rate(A, B, t, T, s) for k in shifts for s in (k, -k)]
    rates = [r for r in rates if r == r]
    r0 = _rate(A, B, t, T)
    mu = sum(rates) / len(rates)
    sd = math.sqrt(sum((r - mu) ** 2 for r in rates) / max(1, len(rates) - 1))
    z = (r0 - mu) / sd if sd > 0 else (math.inf if r0 > mu else 0.0)
    return z, 0.5 * math.erfc(z / math.sqrt(2)) if math.isfinite(z) else 0.0


def _months(n: int) -> str:
    return f"{n} month" + ("s" if n != 1 else "")


def describe(t: Shift, a: str, b: str) -> str:
    """What T says of A and B, in words."""
    way = "the same way" if t.sign > 0 else "the opposite way"
    if t.k == 0:
        return (f"{a} and {b} leave their norm in the same months, " +
                ("the same way" if t.sign > 0 else "in opposite directions"))
    first, then = (a, b) if t.k > 0 else (b, a)
    return f"{first} comes first: {_months(abs(t.k))} after it leaves its norm, {then} leaves its own {way}"


def couplings(positions: dict, labels: dict, months: list, lags: int = LAGS, window: int = WINDOW,
              chance: float = CHANCE) -> dict:
    """Every pair of dynamics read through every transformation; the best per pair is kept when
    both of its readings hold against chance at the same moment.

    ``positions``: ``{unit: [-1 | 0 | 1 per month]}`` (extreme lens), ``months``: the labels."""
    T = len(months)
    H = {u: heatmap(p) for u, p in positions.items()}
    tr = transforms(lags)
    names = [u for u in positions if H[u]]
    pairs = list(combinations(names, 2))
    n_tests = max(1, len(pairs) * len(tr))
    alpha = chance / n_tests
    links = []
    for a, b in pairs:
        best = None
        for t in tr:
            ab = Reading(H[a], H[b], t, T, window)
            ba = Reading(H[b], H[a], t.inverse(), T, window)
            p = max(ab.p, ba.p)
            if best is None or p < best[0]:
                best = (p, t, ab, ba)
        p, t, ab, ba = best
        if p >= chance:
            continue
        # persistence: the same reading with the other dynamic moved 1 to 5 years, both ways round
        z1, q1 = persistence_test(H[a], H[b], t, T)
        z2, q2 = persistence_test(H[b], H[a], t.inverse(), T)
        z, q = min(z1, z2), max(q1, q2)
        if q >= chance:
            continue
        la, lb = labels.get(a, a), labels.get(b, b)
        proven = p < alpha and q < alpha
        sure = wilson_low(ab.hits, ab.tries, 1.0) >= HOLD or wilson_low(ba.hits, ba.tries, 1.0) >= HOLD
        union = proven and ab.share >= HOLD and ba.share >= HOLD and sure
        joint = sorted({y[0] for y in ab.cells})
        eps = episodes(joint)
        link = {
            "members": [a, b], "labels": [la, lb], "transform": t.name, "lag": t.k, "sign": t.sign,
            "level": "proven" if proven else "suggestive", "p": p, "alpha": alpha,
            "z_persistence": z, "p_persistence": q,
            "hits": ab.hits, "tries": [ab.tries, ba.tries], "expected": ab.expected, "share": [ab.share, ba.share],
            "union": union, "episodes": len(eps),
            "longest": [months[eps_[0]] + ("" if len(eps_) == 1 else f" to {months[eps_[-1]]}")
                        for eps_ in sorted(eps, key=lambda e: (-len(e), e[0]))[:3]],
        }
        if union:  # each implies the other's cells: where one left its norm and the other did not
            link["implied"] = {
                b: [months[y[0]] for y in sorted(set(map(t, H[a])) - set(H[b])) if 0 <= y[0] < T],
                a: [months[y[0]] for y in sorted(set(map(t.inverse(), H[b])) - set(H[a])) if 0 <= y[0] < T],
            }
        txt = (f"{describe(t, la, lb)}: {ab.hits} times, where chance at the same moment of the record "
               f"would give {ab.expected:.0f} (p = {p:.1g}; z = {z:.1f} against the same reading with one "
               f"of them moved 1 to 5 years"
               + (", beyond the shared trend and the persistence of each" if proven
                  else ", suggestive only: not beyond every pair and lag tried")
               + ").")
        if union:
            n_imp = sum(len(v) for v in link["implied"].values())
            txt += (f" So often, both ways ({100 * ab.share:.0f} % and {100 * ba.share:.0f} %), that Eva takes them for "
                    f"one dynamic seen through {'a mirror' if t.sign < 0 else 'the identity'}"
                    + (f" {_months(abs(t.k))} apart" if t.k else "")
                    + f": in {_months(n_imp)} one left its norm without the other.")
        link["text"] = txt
        links.append(link)
    links.sort(key=lambda x: (x["level"] != "proven", x["p"]))
    types: dict = {}
    for x in links:
        if x["level"] == "proven":
            types[x["transform"]] = types.get(x["transform"], 0) + x["hits"]
    return {"links": links, "types": dict(sorted(types.items(), key=lambda kv: -kv[1])),
            "readings": n_tests, "alpha": alpha,
            "settings": {"lags": lags, "window": window, "chance": chance, "hold": HOLD, "radius": RADIUS,
                         "shifts": [SHIFTS.start, SHIFTS.stop - 1]}}


def same_process(links: list, units: dict) -> list:
    """The degree above, across regions: the same two variables carried by the same transformation
    in several regions (both members in one region each time) — one process, whatever the signs of
    the trends."""
    groups: dict = {}
    for x in links:
        if x["level"] != "proven":
            continue
        a, b = x["members"]
        ua, ub = units.get(a, {}), units.get(b, {})
        if not ua or ua.get("region") != ub.get("region"):
            continue
        key = (frozenset((ua["variable"], ub["variable"])), x["transform"] if ua["variable"] <= ub["variable"]
               else Shift(-x["lag"], x["sign"]).name)
        groups.setdefault(key, []).append((ua["region_name"], x))
    out = []
    for (vars_, tname), lst in groups.items():
        if len(lst) < 2:
            continue
        out.append({"variables": sorted(vars_), "transform": tname, "regions": [r for r, _ in lst],
                    "links": [x["members"] for _, x in lst]})
    return out
