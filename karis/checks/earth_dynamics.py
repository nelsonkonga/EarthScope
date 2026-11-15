"""The Earth trend detective at the right level of abstraction (the lesson of the curves, RESULTS § 26).

For every series of the investigations already made (data/earth/investigations and data/earth/sweep,
NASA POWER, 1981–2025, read offline), at the level of the year (the level where a 45-year trend
lives: the seasons and the persistence of a few months are below it):

1. Eva's dynamics (eva/shape.py: levels of meta molettes, transitions proven beyond chance): one
   steady dynamic, or regimes and the years where one gave way to the next — against the single
   Sen slope and Pettitt's « rupture » of RESULTS § 13.
2. The control: a steady trend (the series' Sen slope) plus noise as persistent as the series
   (its lag-1 around that line), no change of regime at all, 40 draws each: how often Eva sees two
   dynamics or more, how often Pettitt's test (p < 0.05) reports a rupture.
3. Where there are no readings: 2016–2025 hidden, predicted from 1981–2015 by Eva (her last
   dynamic carried on, and her own created points) against the fixed norm 1981–2010 (what the
   detective judged against), the straight trend line, and the last five years kept as they are.
   RMS gap over the hidden years, as a share of the series' year-to-year spread over 1981–2010.
4. Transitions shared by several variables of one region (the transitions' own meta molettes):
   the years where several dynamics changed together (within 2 years: where their two lines meet,
   detective/dynamics.py), against chance (each variable's transitions moved at random, 2 000 times).

Usage: earth_dynamics.py [out.json]
"""

from __future__ import annotations

import glob
import json
import math
import random
import statistics
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from detective import dynamics as DYN  # noqa: E402
from detective.stats import pettitt  # noqa: E402
from eva.shape import Shape  # noqa: E402

SPLIT, BASE = 2015, (1981, 2010)


def series():
    """Every (region, variable) annual series once."""
    seen, out = set(), []
    files = sorted(glob.glob(str(ROOT / "data/earth/investigations/*.json"))) + sorted(glob.glob(str(ROOT / "data/earth/sweep/*.json")))
    for f in files:
        d = json.load(open(f))
        if not isinstance(d, dict) or "trends" not in d:
            continue
        regions = {r["key"]: r["name"] for r in d.get("regions", [])}
        for var, tr in d["trends"].items():
            if not isinstance(tr, dict) or "annual" not in tr:
                continue
            v, _, reg = var.partition("@")
            reg = reg or next(iter(regions), "?")
            key = (reg, v)
            if key in seen:
                continue
            seen.add(key)
            ys, vs = tr["annual"]["years"], tr["annual"]["values"]
            out.append({"region": regions.get(reg, reg), "var": v, "years": ys, "values": vs,
                        "sen": tr["per_decade"], "verdict": tr["verdict"].get("label", ""),
                        "pettitt": tr["annual"]["pettitt"].get("year"), "pettitt_p": tr["annual"]["pettitt"].get("p")})
    return out


def dynamics(years, values):
    s = Shape(list(zip(years, values)), degree=1)  # the detective's question: a trend per decade
    ps = [P for P in s.pieces if P.size >= 2]
    return s, [(int(s.xs[P.lo]), int(s.xs[P.hi]), s.slope(P) * 10) for P in ps]


def sen_line(t, y):
    t, y = np.asarray(t, float), np.asarray(y, float)
    sl = [(y[j] - y[i]) / (t[j] - t[i]) for i in range(len(t)) for j in range(i + 1, len(t)) if t[j] > t[i]]
    b = float(np.median(sl))
    return b, float(np.median(y - b * t))


def lag1(x):
    x = np.asarray(x, float) - np.mean(x)
    return float(np.sum(x[1:] * x[:-1]) / np.sum(x * x)) if np.sum(x * x) > 0 else 0.0


def control(years, values, draws=40):
    """A steady trend plus persistent noise, no regime: how often two dynamics or more (Eva), how
    often a significant rupture (Pettitt)."""
    b, a = sen_line(years, values)
    res = np.asarray(values) - (a + b * np.asarray(years))
    phi, sd = max(min(lag1(res), 0.95), 0.0), float(np.std(res, ddof=1))
    eva = pet = 0
    for k in range(draws):
        rng = random.Random(k)
        x, ys = 0.0, []
        for t in years:
            x = phi * x + math.sqrt(1 - phi * phi) * rng.gauss(0, sd)
            ys.append(a + b * t + x)
        eva += len(dynamics(years, ys)[1]) > 1
        pet += pettitt(ys)["p"] < 0.05
    return eva / draws, pet / draws, phi


def hindcast(years, values):
    tr = [(t, v) for t, v in zip(years, values) if t <= SPLIT]
    te = [(t, v) for t, v in zip(years, values) if t > SPLIT]
    if len(tr) < 20 or len(te) < 3:
        return None
    base = [v for t, v in tr if BASE[0] <= t <= BASE[1]]
    spread = statistics.stdev(base)
    s = Shape(tr, degree=1)
    curve = s.read(None, max(t for t, _ in te))
    xs = [p[0] for p in curve]

    def eva(t):
        i = min(range(len(xs)), key=lambda k: abs(xs[k] - t))
        return curve[i][1]

    tt, vv = np.array([t for t, _ in tr]), np.array([v for _, v in tr])
    slope, icpt = np.polyfit(tt, vv, 1)
    P = [P for P in s.pieces if P.size >= 2][-1]
    preds = {
        "eva (dernière dynamique)": lambda t: s.line(P, t),
        "eva (points créés)": eva,
        "norme 1981–2010": lambda t: statistics.fmean(base),
        "droite": lambda t: icpt + slope * t,
        "5 dernières années": lambda t: statistics.fmean(vv[-5:]),
    }
    return {k: math.sqrt(statistics.fmean([(f(t) - v) ** 2 for t, v in te])) / spread for k, f in preds.items()}


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    rows = []
    for sr in series():
        s, dyn = dynamics(sr["years"], sr["values"])
        ev_ctl, pet_ctl, phi = control(sr["years"], sr["values"])
        hc = hindcast(sr["years"], sr["values"])
        turns = DYN.annual({"annual": {"years": sr["years"], "values": sr["values"]}})["transitions"]
        rows.append({**sr, "dynamics": dyn, "transitions": turns, "control_eva": ev_ctl, "control_pettitt": pet_ctl,
                     "phi": phi, "hindcast": hc})
        d = " | ".join(f"{a}–{b} {r:+.3g}/déc." for a, b, r in dyn)
        pt = f"Pettitt {sr['pettitt']} (p {sr['pettitt_p']:.2g})" if sr["pettitt"] else "Pettitt —"
        print(f"{sr['region'][:22]:22s} {sr['var']:17s} Sen {sr['sen']:+.3g} | {pt:22s} | Eva : {d}")
    n = len(rows)
    multi = [r for r in rows if len(r["dynamics"]) > 1]
    pet_sig = [r for r in rows if r["pettitt_p"] is not None and r["pettitt_p"] < 0.05]
    print(f"\n{n} séries ; Eva voit plusieurs dynamiques dans {len(multi)}, Pettitt une rupture (p < 0,05) dans {len(pet_sig)}.")
    print(f"Témoin (tendance régulière + bruit persistant, sans rupture) : Eva voit plusieurs dynamiques "
          f"{statistics.fmean(r['control_eva'] for r in rows):.1%} du temps, Pettitt une rupture "
          f"{statistics.fmean(r['control_pettitt'] for r in rows):.1%} du temps.")
    hcs = [r["hindcast"] for r in rows if r["hindcast"]]
    print(f"\nPrédire 2016–2025 depuis 1981–2015 ({len(hcs)} séries) — écart en part de la variabilité d'une année :")
    for k in hcs[0]:
        vals = [h[k] for h in hcs]
        wins = sum(h["eva (dernière dynamique)"] < h[k] for h in hcs) if not k.startswith("eva (dern") else None
        print(f"  {k:20s} médiane {statistics.median(vals):.2f}  moyenne {statistics.fmean(vals):.2f}"
              + (f"   Eva meilleure dans {wins}/{len(hcs)}" if wins is not None else ""))
    print("\nTransitions partagées par plusieurs variables d'une région (à ± 2 ans), contre le hasard :")
    shared = []
    for reg in sorted({r["region"] for r in rows}):
        rs = [r for r in rows if r["region"] == reg]
        tr = {r["var"]: r["transitions"] for r in rs if r["transitions"]}
        if len(tr) < 2:
            continue
        years = rs[0]["years"]
        lo, hi = years[0] + 1, years[-1] - 1

        def best(t):
            pts = [(y, v) for v, ys in t.items() for y in ys]
            top = (0, None, [])
            for y, _ in pts:
                vs = sorted({v for z, v in pts if abs(z - y) <= 2})  # within 2·RADIUS years
                if len(vs) > top[0]:
                    top = (len(vs), y, vs)
            return top

        k, at, vs = best(tr)
        rng = random.Random(0)
        hits = sum(best({v: [rng.uniform(lo, hi) for _ in ys] for v, ys in tr.items()})[0] >= k for _ in range(2000))
        p = (hits + 1) / 2001
        shared.append({"region": reg, "year": at, "vars": vs, "of": sorted(tr), "n_vars": len(rs), "p": p})
        print(f"  {reg[:30]:30s} {k} variables vers {at:.0f} : {', '.join(vs)} (sur {len(tr)} avec des transitions, {len(rs)} en tout) — p {p:.3g}")
    if out:
        out.write_text(json.dumps({"series": rows, "shared": shared}, ensure_ascii=False, indent=1))
        print(f"→ {out}")


if __name__ == "__main__":
    main()
