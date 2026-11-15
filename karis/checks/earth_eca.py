"""Eva's links against event coincidence analysis (ECA), the established method for the same question.

ECA (Donges, Schleussner, Siegmund & Donner 2016, Eur. Phys. J. Special Topics 225, 471–487) asks
whether events of series A are followed by events of series B more often than chance: the
*precursor* coincidence rate (share of A events with a B event τ steps later, within ΔT) and the
*trigger* coincidence rate (share of B events with an A event τ steps before), each tested
analytically against independent Poisson processes (a binomial with
p = 1 − (1 − (ΔT+1)/(T − τ))^N). Here the events are the same as Eva's: the months a dynamic left
its norm (extreme lens, 10th / 90th percentiles of the baseline), split by direction — four event
pairs (A↑B↑, A↑B↓, A↓B↑, A↓B↓) at lags −3..+3, ΔT = 0; a link needs both rates significant after
Bonferroni over every pair, direction pair and lag (the same family size logic as Eva's).

Usage: python checks/earth_eca.py [case ...]   (cases from data/earth/investigations; default all five)
Writes data/earth/eca.json and prints the comparison.
"""

from __future__ import annotations

import json
import sys
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from detective.heat import couplings  # noqa: E402
from eva.heatmaps import CHANCE, chance_tail  # noqa: E402

CASES = ["arctic", "two_seas", "sahel", "europe", "levels"]
LAGS = 3
DT = 0


def eca(a: list, b: list, sa: int, sb: int, tau: int, dt: int = DT) -> dict:
    """Precursor and trigger coincidences of A-events (pos == sa) and B-events (pos == sb), B τ later."""
    T = len(a)
    if tau < 0:  # B first: swap the roles
        r = eca(b, a, sb, sa, -tau, dt)
        return {"precursor": r["trigger"], "trigger": r["precursor"], "p": r["p"], "n": (r["n"][1], r["n"][0])}
    ea = [t for t in range(T - tau) if a[t] == sa]
    eb = [t for t in range(tau, T) if b[t] == sb]
    sb_set, sa_set = set(eb), set(ea)
    kp = sum(1 for t in ea if any((t + tau + d) in sb_set for d in range(-dt, dt + 1)))
    kt = sum(1 for t in eb if any((t - tau + d) in sa_set for d in range(-dt, dt + 1)))
    span, w = T - tau, 2 * dt + 1
    pp = 1 - (1 - w / span) ** len(eb) if span else 1.0
    pt = 1 - (1 - w / span) ** len(ea) if span else 1.0
    p_pre = chance_tail(kp, len(ea), pp) if ea else 1.0
    p_trig = chance_tail(kt, len(eb), pt) if eb else 1.0
    return {"precursor": kp / len(ea) if ea else 0.0, "trigger": kt / len(eb) if eb else 0.0,
            "p": max(p_pre, p_trig), "n": (len(ea), len(eb))}


def compare(case: str) -> dict:
    d = json.load(open(ROOT / "data" / "earth" / "investigations" / f"{case}.json"))
    ex = d["eva"]["extreme"]
    pos = {u: v["positions"] for u, v in ex["units"].items()}
    labels = {u: v["label"] for u, v in ex["units"].items()}
    names = list(pos)
    pairs = list(combinations(names, 2))
    combos = [(sa, sb, tau) for sa in (1, -1) for sb in (1, -1) for tau in range(-LAGS, LAGS + 1)]
    alpha = CHANCE / (len(pairs) * len(combos))
    eva = {tuple(x["members"]): x for x in couplings(pos, labels, ex["months"])["links"]}
    rows = []
    for a, b in pairs:
        found = []
        for sa, sb, tau in combos:
            r = eca(pos[a], pos[b], sa, sb, tau)
            if r["p"] < alpha:
                found.append({"a": sa, "b": sb, "lag": tau, "p": r["p"], "precursor": r["precursor"],
                              "trigger": r["trigger"]})
        found.sort(key=lambda r: r["p"])
        x = eva.get((a, b))
        rows.append({"pair": [labels[a], labels[b]], "units": [a, b],
                     "eva": None if x is None else {"transform": x["transform"], "level": x["level"], "p": x["p"],
                                                    "z_persistence": x["z_persistence"]},
                     "eca": found})
    return {"case": case, "alpha_eca": alpha, "rows": rows}


def relation(sign: int, lag: int) -> str:
    return ("same" if sign > 0 else "opposite") + (f", {lag:+d} mo" if lag else "")


def main(argv: list[str]) -> None:
    cases = argv or CASES
    out = [compare(c) for c in cases]
    (ROOT / "data" / "earth" / "eca.json").write_text(json.dumps(out, indent=1))
    agree = eva_only = eca_only = both_none = 0
    for res in out:
        print(f"=== {res['case']} (ECA alpha {res['alpha_eca']:.1e})")
        for r in res["rows"]:
            e = r["eva"] if r["eva"] and r["eva"]["level"] == "proven" else None
            k = r["eca"][0] if r["eca"] else None
            ev = f"{e['transform']} p {e['p']:.0e}" if e else "—"
            ec = (f"{'↑' if k['a'] > 0 else '↓'}{'↑' if k['b'] > 0 else '↓'} lag {k['lag']:+d} p {k['p']:.0e}"
                  f" ({len(r['eca'])} combos)") if k else "—"
            tag = ("both" if e and k else "Eva only" if e else "ECA only" if k else "")
            agree += bool(e and k)
            eva_only += bool(e and not k)
            eca_only += bool(k and not e)
            both_none += not (e or k)
            if e or k:
                print(f"  {r['pair'][0][:30]:30s} {r['pair'][1][:30]:30s} Eva {ev:22s} ECA {ec:34s} {tag}")
    print(f"\npairs linked by both: {agree}; Eva only: {eva_only}; ECA only: {eca_only}; neither: {both_none}")


if __name__ == "__main__":
    main(sys.argv[1:])
