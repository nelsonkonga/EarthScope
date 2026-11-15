"""Eva watches Earth series: the molettes of dynamics on monthly NASA data.

The engine is ``eva.dynamics.Dynamics`` — unchanged and domain-agnostic, with Eva's generic
settings. This module is the domain layer: how a monthly series becomes the values of a
watcher, and how the molettes' norms, extremes and meta molettes answer the detective.

The lens
    Each value is placed among the baseline values of the same time of year (its calendar
    month and the two neighbouring ones): ``b`` equal-probability positions ``0 .. b-1``,
    plus ``-1`` below and ``b`` above anything seen at that time of year during the
    baseline. ``b`` is the finest grain at which every degree-2 reading (a transition) is
    crossed often enough to have a distribution (20 times on average) — the evidence rule
    of ``eva.discovery``. A position is a state of the anomaly, not of the season: the
    seasonal cycle is the norm of the time of year, the molettes follow what departs from it.

Pass A — Eva follows the whole record and learns as she goes (as she always does)
    Each transition is read against the norm learned so far, before it is counted: its
    surprise at each degree, whether it is out of norm (an extreme: surprise more than
    ``dyn_extreme_z`` spreads above the typical one), on which side of the norm it falls.
    Meta molettes are born spontaneously when one event — here, a month — moves several
    dynamics together far more often than chance (count, lift, z). A double transition
    (degrees 2 and 3 out of norm at the same tick) is a bend of the dynamic.

Pass B — Eva learns the norm on the baseline, then follows the rest without learning
    (as in her evaluation episodes) and judges each month against that norm: how often it
    falls in her top / bottom positions or beyond anything she saw, how often a transition
    is out of norm, and where the value falls in the distribution her norm predicted from
    the month before (0.5: exactly as expected; above: higher than the norm expected).
"""

from __future__ import annotations

import math
from collections import defaultdict
from itertools import combinations

import numpy as np
from scipy import stats as st

from eva import EvaConfig
from eva.dynamics import WORLD, Dynamics, reading

from .heat import couplings
from .stats import lag1


def eva_config(**over) -> EvaConfig:
    """Eva's generic settings. Off: what has no meaning for a stream of observations —
    construction elements (completions followed by the end of an episode) and the field
    derivatives of a board (no layout is given)."""
    return EvaConfig(model="dynamics", dyn_elements=False, dyn_field=False, **over)


def evidence_bins(n: int, per: int = 20, lo: int = 3, hi: int = 9) -> int:
    """Finest number of positions whose b² transitions are each crossed ``per`` times on average."""
    return max(lo, min(hi, int(math.sqrt(n / per))))


EXTREME_CUTS = (0.1, 0.9)  # the 10th / 90th percentiles of the base period (WMO / ETCCDI extremes indices)


class PhaseLens:
    """How a raw monthly series becomes the positions of a molette (see the module doc).

    Two grains. The *fine* lens (default): ``b`` equal-probability positions ``0 .. b-1``
    (evidence rule), ``-1`` below and ``b`` above anything seen at that time of year in the
    baseline. The *extreme* lens (``cuts=(0.1, 0.9)``): ``-1`` below its norm, ``0`` within
    it, ``1`` above it — at this grain a change of position is the dynamic leaving or
    re-entering its norm, which is what an event is in a stream where everything moves a
    little every month."""

    def __init__(self, series: dict, base: tuple, bins: int | None = None, window: int = 1,
                 cuts: tuple | None = None):
        by_month: dict = defaultdict(list)
        for (y, m), v in series.items():
            if v is not None and base[0] <= y <= base[1]:
                by_month[m].append(v)
        n = sum(len(v) for v in by_month.values())
        if n < 36:
            raise ValueError("the baseline needs at least three years of data")
        self.base = tuple(base)
        self.cuts = tuple(cuts) if cuts else None
        self.bins = len(self.cuts) + 1 if self.cuts else (bins or evidence_bins(n))
        # each calendar month is compared with its own baseline values and with those of its
        # neighbours brought to its level and spread (a steep seasonal cycle would otherwise
        # put every month in the middle of its neighbours' values)
        mean = {m: float(np.mean(v)) for m, v in by_month.items() if v}
        sd = {m: float(np.std(v)) for m, v in by_month.items() if v}
        self.sample = {}
        for m in range(1, 13):
            if m not in mean:
                raise ValueError(f"no baseline value for month {m}")
            s = []
            for d in range(-window, window + 1):
                o = (m - 1 + d) % 12 + 1
                if o not in mean:
                    continue
                k = sd[m] / sd[o] if sd[o] > 0 else 0.0
                s.extend(mean[m] + (v - mean[o]) * k for v in by_month[o])
            self.sample[m] = np.sort(np.asarray(s, float))
        if self.cuts:  # the top / bottom positions and how often the baseline is there
            self.top, self.bottom = len(self.cuts) // 2, -(len(self.cuts) // 2)
            self.expected_top, self.expected_bottom = 1 - self.cuts[-1], self.cuts[0]
        else:
            self.top, self.bottom = self.bins - 1, 0
            self.expected_top = self.expected_bottom = 1 / self.bins

    def quantile(self, month: int, x: float) -> float:
        s = self.sample[month]
        lo, hi = np.searchsorted(s, x, "left"), np.searchsorted(s, x, "right")
        return float((lo + 0.5 * (hi - lo)) / len(s))

    def position(self, month: int, x) -> int | None:
        if x is None:
            return None
        if self.cuts:
            q = self.quantile(month, x)
            return sum(1 for c in self.cuts if q > c) - len(self.cuts) // 2
        s = self.sample[month]
        if x < s[0]:
            return -1
        if x > s[-1]:
            return self.bins
        return min(self.bins - 1, int(self.quantile(month, x) * self.bins))

    def labels(self) -> dict:
        if self.cuts:
            lo, hi = round(100 * self.cuts[0]), round(100 * self.cuts[-1])
            return {self.bottom: f"below its norm (under the {lo}th percentile)", 0: "within its norm",
                    self.top: f"above its norm (over the {hi}th percentile)"}
        b = self.bins
        out = {-1: "below anything seen in the baseline", b: "above anything seen in the baseline"}
        for i in range(b):
            out[i] = f"{i + 1} of {b}" + (" (lowest)" if i == 0 else " (highest)" if i == b - 1 else "")
        return out


def _label(key: tuple) -> str:
    return f"{key[0]}-{key[1]:02d}"


def _binom_p(k: int, n: float) -> float:
    """Two-sided p of k successes out of n (n may be an effective, non-integer count)."""
    if n <= 0:
        return float("nan")
    z = (k - n / 2) / math.sqrt(n / 4)
    return float(2 * st.norm.sf(abs(z)))


class Watch:
    """Eva on a set of monthly series (``{unit: {(year, month): value}}``)."""

    def __init__(self, series: dict, base: tuple = (1981, 2010), cfg: EvaConfig | None = None,
                 bins: int | None = None, labels: dict | None = None, cuts: tuple | None = None):
        self.cfg = cfg or eva_config()
        self.names = list(series)
        self.labels = labels or {u: u for u in self.names}
        common = set.intersection(*[{k for k, v in s.items() if v is not None} for s in series.values()])
        self.months = sorted(common)
        if not self.months or self.months[0][0] > base[0] or self.months[-1][0] <= base[1]:
            raise ValueError("the record must cover the baseline and go beyond it")
        self.base = tuple(base)
        self.grain = "extreme" if cuts else "fine"
        self.split = next(t for t, k in enumerate(self.months) if k[0] > base[1])
        self.lens = {u: PhaseLens(series[u], base, bins, cuts=cuts) for u in self.names}
        self.pos = {u: [self.lens[u].position(k[1], series[u][k]) for k in self.months] for u in self.names}

    def obs(self, t: int) -> dict:
        return {u: self.pos[u][t] for u in self.names}

    # ------------------------------------------------------------ readings
    @staticmethod
    def _read(dyn: Dynamics, hist: list, u, x) -> dict:
        """How the molettes of ``u`` read the transition to ``x``, before counting it:
        ``{degree: (surprise, extreme, where x falls in the predicted distribution, expected)}``."""
        out = {}
        z = dyn.cfg.dyn_extreme_z
        for k in range(1, dyn.D + 1):
            if len(hist) < k:
                break
            before = reading(hist, u, k)
            mol = dyn.mol.get((u, k))
            dist = mol.dist(before, WORLD) if mol is not None else None
            if not dist:  # a reading never seen: the norm says nothing yet
                continue
            s = mol.surprise(before, WORLD, x)
            pit = sum(q for y, q in dist.items() if y < x) + 0.5 * dist.get(x, 0.0)
            exp = sum(y * q for y, q in dist.items())
            out[k] = (s, mol.is_extreme(s, z), pit, exp)
        return out

    def pass_a(self):
        """Eva follows the whole record, learning as she goes."""
        dyn = Dynamics(self.cfg)
        dyn.begin(0, self.obs(0))
        tr = dyn.track[0]
        reads: list = [{} for _ in self.months]
        births = []
        for t in range(1, len(self.months)):
            dyn._flush_all(tr)  # the norms read include the stays not counted yet (as before a decision)
            o = self.obs(t)
            reads[t] = {u: self._read(dyn, tr.hist, u, o[u]) for u in self.names}
            n0 = len(dyn.metas)
            dyn.tick(0, o, learn=True)
            births.extend((m, t) for m in dyn.metas[n0:])
        dyn.end(0)
        return dyn, reads, births

    @staticmethod
    def backwards(mol) -> dict:
        """The molette's transitions read from the other end (the user's rule: a transition is
        not a question of time, and it is symmetric — read along −δ it is the same transition
        read backwards). From the same joint counts: ``{(tail, last): {first: count}}`` for
        the readings ``(first, *tail) -> last``."""
        rev: dict = {}
        for (r, _src), row in mol.forward():  # read forward (eva/dynamics.py reads both ways)
            first, tail = (r, ()) if not isinstance(r, tuple) else (r[0], tuple(r[1:]))
            for nxt, c in row.items():
                d = rev.setdefault((tail, nxt), {})
                d[first] = d.get(first, 0) + c
        return rev

    def pass_b(self):
        """Eva learns the norm on the baseline, then judges every month without learning.
        Each month is read by its transition with the month before and, the same transition
        read from the other end, with the month after (``back``: where the month falls in what
        the norm expects of it from its successor)."""
        dyn = Dynamics(self.cfg)
        dyn.begin(0, self.obs(0))
        for t in range(1, self.split):
            dyn.tick(0, self.obs(t), learn=True)
        dyn.end(0)
        dyn.begin(1, self.obs(0))
        tr = dyn.track[1]
        reads: list = [{} for _ in self.months]
        for t in range(1, len(self.months)):
            o = self.obs(t)
            reads[t] = {u: self._read(dyn, tr.hist, u, o[u]) for u in self.names}
            dyn.tick(1, o, learn=False)
        back: list = [{} for _ in self.months]
        for u in self.names:
            mol = dyn.mol.get((u, 1))
            if mol is None:
                continue
            rev = self.backwards(mol)
            pos = self.pos[u]
            for t in range(len(self.months) - 1):
                dist = rev.get(((), pos[t + 1]))
                if not dist:
                    continue
                tot = sum(dist.values())
                x = pos[t]
                back[t][u] = (sum(c for y, c in dist.items() if y < x) + 0.5 * dist.get(x, 0)) / tot
        return dyn, reads, back

    # ------------------------------------------------------------- reports
    def run(self) -> dict:
        dyn_a, reads_a, births = self.pass_a()
        dyn_b, reads_b, back = self.pass_b()
        units = {u: self._unit(u, dyn_b, reads_a, reads_b, back) for u in self.names}
        pairs = self._pairs(dyn_a)
        # the heatmaps of the departures (extreme grain): intersections and unions through the
        # transformations of (month, sign), with chance read at the same moment (detective/heat.py)
        heat = (couplings(self.pos, self.labels, [_label(k) for k in self.months])
                if self.grain == "extreme" and len(self.names) > 1 else None)
        return {
            "grain": self.grain,
            "months": [_label(k) for k in self.months],
            "baseline": list(self.base),
            "split": _label(self.months[self.split]),
            "settings": {"degrees": self.cfg.dyn_degrees, "extreme_z": self.cfg.dyn_extreme_z,
                         "meta_min": self.cfg.dyn_meta_min, "meta_lift": self.cfg.meta_min_lift,
                         "meta_z": self.cfg.meta_z, "meta_arity": self.cfg.dyn_meta_arity},
            "units": units,
            "metas": self._metas(dyn_a, births, units, pairs),
            "pairs": pairs,
            "couplings": heat,
            "engine": {"pass_a": dyn_a.stats(), "pass_b": dyn_b.stats()},
        }

    def _pairs(self, dyn: Dynamics) -> list:
        """Every pair of dynamics as Eva weighs it: do the same months move both (the timing
        her birth test uses: count, lift, z against independence), and when they do, in which
        directions (which the birth test does not look at)."""
        T = len(self.months)
        moves = {u: [self.pos[u][t] != self.pos[u][t - 1] for t in range(1, T)] for u in self.names}
        born = {frozenset(m[2]) for m in dyn.metas}
        out = []
        for a, b in combinations(self.names, 2):
            c = sum(1 for x, y in zip(moves[a], moves[b]) if x and y)
            e = sum(moves[a]) * sum(moves[b]) / max(1, T - 1)
            same = opp = 0
            for t in range(1, T):
                if moves[a][t - 1] and moves[b][t - 1]:
                    da, db = self.pos[a][t] - self.pos[a][t - 1], self.pos[b][t] - self.pos[b][t - 1]
                    if (da > 0) == (db > 0):
                        same += 1
                    else:
                        opp += 1
            out.append({"members": [a, b], "labels": [self.labels[a], self.labels[b]], "co_changes": c,
                        "expected": e, "lift": c / e if e > 0 else None,
                        "z": (c - e) / math.sqrt(e) if e > 0 else None,
                        "same": same, "opposite": opp, "direction_p": _binom_p(same, same + opp) if same + opp else None,
                        "meta": frozenset((a, b)) in born})
        out.sort(key=lambda p: -(p["z"] or 0))
        return out

    def _unit(self, u, dyn_b: Dynamics, reads_a: list, reads_b: list, back: list) -> dict:
        lens, pos, S, T = self.lens[u], self.pos[u], self.split, len(self.months)
        b = lens.bins
        rec = range(S, T)
        n_rec = len(rec)
        top = sum(1 for t in rec if pos[t] >= lens.top)
        bottom = sum(1 for t in rec if pos[t] <= lens.bottom)
        beyond_hi = [] if lens.cuts else [_label(self.months[t]) for t in rec if pos[t] == b]
        beyond_lo = [] if lens.cuts else [_label(self.months[t]) for t in rec if pos[t] == -1]
        # where each month falls in what the norm (learned on the baseline) expects of it, read
        # from both sides: from the month before, and from the month after (the same
        # transitions read backwards: a transition is symmetric)
        pit = {}
        for t in range(T):
            sides = [reads_b[t][u][1][2]] if 1 in reads_b[t].get(u, {}) else []
            if u in back[t]:
                sides.append(back[t][u])
            if sides:
                pit[t] = sum(sides) / len(sides)
        rec_pit = [pit[t] for t in rec if t in pit]
        above = sum(1 for p in rec_pit if p > 0.5)
        below = sum(1 for p in rec_pit if p < 0.5)
        ind = [1.0 if p > 0.5 else 0.0 for p in rec_pit if p != 0.5]
        r1 = lag1(ind) if len(ind) > 3 else 0.0
        n_eff = (above + below) * (1 - r1) / (1 + r1) if r1 > 0 else float(above + below)
        k_eff = above * n_eff / (above + below) if above + below else 0
        p_above = _binom_p(k_eff, n_eff)
        # out-of-norm transitions (degree 2): while learning the baseline (pass A), then against
        # the frozen baseline norm (pass B)
        def extremes(reads, ts):
            seen = up = down = 0
            for t in ts:
                r = reads[t].get(u, {}).get(2)
                if r is None:
                    continue
                seen += 1
                if r[1]:
                    if self.pos[u][t] > r[3]:
                        up += 1
                    else:
                        down += 1
            return seen, up, down
        warm = next((t for t, k in enumerate(self.months) if k[0] >= self.months[0][0] + 2), 1)
        b_seen, b_up, b_down = extremes(reads_a, range(warm, S))
        r_seen, r_up, r_down = extremes(reads_b, rec)
        # bends: degrees 2 and 3 out of norm at the same tick (pass A)
        bends = [t for t in range(1, T) if all(reads_a[t].get(u, {}).get(k, (0, False))[1] for k in (2, 3))]
        by_year: dict = defaultdict(list)
        for t in range(T):
            if t in pit:
                by_year[self.months[t][0]].append(pit[t] - 0.5)
        # the norm itself: how sticky the anomaly is (degree 1: next position = this one)
        mol = dyn_b.mol.get((u, 1))
        stay = tot = 0
        if mol is not None:
            for (r, _src), row in mol.forward():  # read forward (eva/dynamics.py reads both ways)
                stay += row.get(r, 0)
                tot += sum(row.values())
        frac = above / (above + below) if above + below else float("nan")
        direction = "up" if frac > 0.5 else "down"
        if p_above < 0.05:
            level = "left its norm"
            text = (f"Since {self.months[S][0]}, {100 * max(frac, 1 - frac):.0f} % of months came out "
                    f"{'higher' if direction == 'up' else 'lower'} than Eva's norm expected from their neighbours "
                    f"(50 % if nothing had changed): the dynamic has left the norm she learned in "
                    f"{self.base[0]}–{self.base[1]}.")
        else:
            level = "within its norm"
            text = (f"Since {self.months[S][0]}, months come out above Eva's expectation {100 * frac:.0f} % of the "
                    f"time: not clearly different from her {self.base[0]}–{self.base[1]} norm.")
        return {
            "label": self.labels[u], "bins": b, "position_labels": {str(k): v for k, v in lens.labels().items()},
            "positions": pos,
            "norm": {"persistence": stay / tot if tot else None,
                     "extreme_rate": (b_up + b_down) / b_seen if b_seen else None,
                     "extremes_up": b_up, "extremes_down": b_down, "months": b_seen},
            "recent": {"from": _label(self.months[S]), "months": n_rec,
                       "top_share": top / n_rec, "bottom_share": bottom / n_rec,
                       "expected_share": lens.expected_top, "expected_bottom": lens.expected_bottom,
                       "beyond_high": beyond_hi, "beyond_low": beyond_lo,
                       "above_expectation": frac, "above_p": p_above, "n_eff": n_eff,
                       "extreme_rate": (r_up + r_down) / r_seen if r_seen else None,
                       "extremes_up": r_up, "extremes_down": r_down, "months_read": r_seen},
            "departure_by_year": {str(y): float(np.mean(v)) for y, v in sorted(by_year.items())},
            "bends": [_label(self.months[t]) for t in bends],
            "verdict": {"level": level, "direction": direction, "text": text},
        }

    def _metas(self, dyn: Dynamics, births: list, units: dict, pairs: list | None = None) -> list:
        """Meta molettes: which dynamics one event moves together, and in which direction."""
        origin = dyn.__dict__.get("meta_origin", {})
        groups: dict = {}
        for m, t in births:
            _, k, ms = m
            g = groups.setdefault(ms, {"members": list(ms), "labels": [self.labels[x] for x in ms],
                                       "degrees": [], "born": {}, "z": {}, "same": 0, "opposite": 0,
                                       "patterns": defaultdict(int)})
            g["degrees"].append(k)
            g["born"][str(k)] = _label(self.months[t])
            if m in origin:
                g["z"][str(k)] = dyn._meta_z(origin[m])
            mol = dyn.mol.get((m, k))
            if mol is None:
                continue
            for (before, _src), row in mol.forward():  # read forward (eva/dynamics.py reads both ways)
                last = [r if k == 1 else (r[-1] if r else None) for r in before]
                for nxt, c in row.items():
                    d = [(n - l) if (n is not None and l is not None) else 0 for n, l in zip(nxt, last)]
                    for i, j in combinations(range(len(d)), 2):
                        if d[i] and d[j]:
                            if (d[i] > 0) == (d[j] > 0):
                                g["same"] += c
                            else:
                                g["opposite"] += c
                    if all(d):  # one event moved all its dynamics: which way each one went
                        sg = tuple(1 if x > 0 else -1 for x in d)
                        if sg[0] < 0:  # a pattern and its mirror are the same coupling
                            sg = tuple(-x for x in sg)
                        g["patterns"][sg] += c
        by_pair = {frozenset(p["members"]): p for p in pairs or []}
        out = []
        for g in groups.values():
            pr = by_pair.get(frozenset(g["members"])) if len(g["members"]) == 2 else None
            if pr:  # a pair: the directions of all its joint moves over the record (the pairs table)
                g["same"], g["opposite"] = pr["same"], pr["opposite"]
            n = g["same"] + g["opposite"]
            g["phase"] = (g["same"] - g["opposite"]) / n if n else 0.0
            g["phase_p"] = _binom_p(g["same"], n) if n else float("nan")
            g["first_born"] = min(g["born"].values())
            pats = g.pop("patterns")
            tot = sum(pats.values())
            if tot:
                best, cnt = max(pats.items(), key=lambda kv: kv[1])
                g["pattern"] = {"signs": list(best), "share": cnt / tot, "events": tot}
            names = " & ".join(g["labels"])
            if len(g["members"]) > 2 and tot and g["pattern"]["share"] >= 0.5:
                up = [lab for lab, s in zip(g["labels"], best) if s > 0]
                down = [lab for lab, s in zip(g["labels"], best) if s < 0]
                how = (f"most often ({100 * g['pattern']['share']:.0f} %) {', '.join(up)} one way"
                       + (f" and {', '.join(down)} the other way" if down else ", all together"))
            elif n and g["phase_p"] < 0.05:
                how = (f"in the same direction {100 * g['same'] / n:.0f} % of the time" if g["phase"] > 0 else
                       f"in opposite directions {100 * g['opposite'] / n:.0f} % of the time")
            else:
                how = "with no preferred direction"
            dirs = {units[x]["verdict"]["direction"] for x in g["members"] if x in units}
            what = ("the same months push these dynamics out of their norm (or back into it) together"
                    if self.grain == "extreme" else "the same months move these dynamics together")
            g["grain"] = self.grain
            g["text"] = (f"{names}: {what} far more often than chance "
                         f"(meta molette born {g['first_born']}, degrees {', '.join(map(str, sorted(g['degrees'])))}), {how}.")
            g["trend_directions"] = sorted(dirs)
            out.append(g)
        out.sort(key=lambda g: (-len(g["members"]), -max(g["z"].values(), default=0)))
        return out
