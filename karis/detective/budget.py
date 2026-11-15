"""The application layer: spend a budget where the science of change says the land is losing.

``land.py`` detects, quantifies, tests and predicts the changes; this module only uses its
results. A budget (US$) buys interventions on cropland, cell by cell, to protect the land's
growing potential over 2026-2035. Everything that is not NASA data is an assumption, written
here and editable on the page: what each intervention costs per hectare and how much of each
threat it offsets, and how much of the potential each threat takes.

Threats of a cell (the expected share of a hectare's growing potential at stake by 2026-2035,
from the calibrated forecast: the expected drop below the last ten years, never a point guess):

- ``water``  : the growing season expected to be lost, as a share of the season (FAO: the length
               of the growing period sets which crops a rain-fed field can carry);
- ``erosion``: the expected rise of rain erosivity, as a share, times how much potential a rise
               of erosive rain costs (an assumption);
- ``wind``   : the same for the wind-erosion factor;
- ``heat``   : the expected warming of the surface (°C) times the yield lost per °C
               (about 7 % for maize in the tropics, Zhao et al. 2017, PNAS).

Evidence filters (what the science adds): ``forecast`` uses every forecast as it is;
``detected`` keeps a threat only where its 1981-2025 trend is detected the bad way (both tests,
false discovery rate controlled); ``confirmed`` also drops the rain-made threats the satellite
(GPM IMERG) contradicts.

Allocation: a linear programme (each cell's treatable cropland split between interventions, the
budget spent where a dollar protects the most; a programme reaches at most ``ADOPTION`` of a
cell's cropland in a decade, the absorptive capacity every extension service meets), solved
exactly by the greedy of Sinha & Zoltners (1979)
for the multiple-choice knapsack: each cell's options on their upper convex hull of (cost,
benefit), every step of every hull taken by decreasing benefit per dollar.

``hindcast``: the same decision made in 2015 with what was known then, judged by what really
happened in 2016-2025, against spending evenly and against perfect foresight.
"""

from __future__ import annotations

import math

import numpy as np

from .land import INDICATORS, LEARN_CUTS, benjamini_hochberg, trend

THREATS = {"water": ("lgp", -1), "erosion": ("erosivity", +1), "wind": ("wind_erosion", +1),
           "heat": ("surface_temp", +1)}  # threat: (indicator, the way that hurts)
SENSITIVITY = {"water": 1.0, "erosion": 0.2, "wind": 0.2, "heat": 0.07}  # potential lost per unit of threat
SENS_WHY = {
    "water": "a season 10 % shorter costs about 10 % of a rain-fed field's potential (FAO growing period)",
    "erosion": "a rain 100 % more erosive costs about 20 % of the potential over a decade (assumption)",
    "wind": "a wind-erosion factor 100 % higher costs about 20 % of the potential over a decade (assumption)",
    "heat": "each °C of warming costs about 7 % of the yield of maize in the tropics (Zhao et al. 2017)",
}

INTERVENTIONS = [
    {"key": "zai", "label": "Water harvesting: zaï pits, half-moons, tied ridges", "cost": 220,
     "effects": {"water": 0.5, "erosion": 0.4, "wind": 0.1, "heat": 0.0},
     "ref": "WOCAT SLM database; Zougmoré et al. 2014 (labour 150-300 US$/ha)"},
    {"key": "bunds", "label": "Stone bunds and contour grass strips", "cost": 180,
     "effects": {"water": 0.25, "erosion": 0.6, "wind": 0.05, "heat": 0.0},
     "ref": "WOCAT SLM database (120-300 US$/ha)"},
    {"key": "windbreak", "label": "Windbreaks and crop-residue mulch", "cost": 120,
     "effects": {"water": 0.15, "erosion": 0.3, "wind": 0.6, "heat": 0.05},
     "ref": "FAO conservation agriculture; WOCAT"},
    {"key": "fmnr", "label": "Farmer-managed natural regeneration (trees in fields)", "cost": 40,
     "effects": {"water": 0.15, "erosion": 0.25, "wind": 0.35, "heat": 0.25},
     "ref": "Reij & Garrity 2016, Biotropica (20-40 US$/ha)"},
    {"key": "seeds", "label": "Short-cycle, drought-tolerant seed (ten seasons)", "cost": 150,
     "effects": {"water": 0.35, "erosion": 0.0, "wind": 0.0, "heat": 0.2},
     "ref": "CGIAR drought-tolerant maize for Africa"},
    {"key": "irrigation", "label": "Small-scale supplementary irrigation", "cost": 2000,
     "effects": {"water": 0.85, "erosion": 0.0, "wind": 0.0, "heat": 0.3},
     "ref": "FAO AQUASTAT unit costs (1 500-3 000 US$/ha)"},
]
EVIDENCE = ("forecast", "detected", "confirmed")
ADOPTION = 0.25  # at most this share of a cell's cropland can be treated within the decade (absorptive capacity)


# ------------------------------------------------------------------ threats
def severity(threat: str, recent: float, change: float) -> float:
    """Share of a hectare's potential at stake from an expected change ``change`` (>= 0, the bad
    way) of a threat's indicator whose last ten years averaged ``recent``."""
    if change <= 0:
        return 0.0
    if threat == "heat":
        return SENSITIVITY["heat"] * change
    if not recent or recent <= 0:
        return 0.0
    return min(1.0, SENSITIVITY[threat] * change / recent)


def _bad_change(threat: str, fc: dict) -> float:
    """The expected change the bad way: the expected drop below the last ten years (shortfall) for
    a good that falls, the expected rise above them (excess) for a harm that grows."""
    _ind, way = THREATS[threat]
    return fc["shortfall"] if way < 0 else fc["excess"]


def threats(res: dict, evidence: str = "detected") -> dict:
    """Every cell's threats for 2026-2035 from the calibrated forecast, kept or dropped by the
    evidence filter."""
    out = {}
    rep = (res.get("replication") or {}).get("per_cell") or {}
    for k in res["cells"]:
        t = {}
        for name, (ind, way) in THREATS.items():
            fc = (res["forecast"].get(ind) or {}).get(k)
            if not fc:
                continue
            if evidence in ("detected", "confirmed"):
                d = res["detect"][ind]["cells"].get(k)
                if not d or not d.get("detected") or d["per_decade"] * way <= 0:
                    continue
            if evidence == "confirmed" and ind in ("lgp", "erosivity"):
                if ((rep.get(k) or {}).get(ind) or {}).get("status") == "contradicted":
                    continue
            t[name] = severity(name, fc["recent"], _bad_change(name, fc))
        out[k] = t
    return out


# --------------------------------------------------------------- allocation
def benefit_per_ha(effects: dict, sev: dict) -> float:
    return sum(effects.get(t, 0.0) * s for t, s in sev.items())


def allocate(area: dict, sev: dict, budget: float, interventions: list[dict] = INTERVENTIONS) -> dict:
    """Spend ``budget`` (US$) over the cells' cropland (``area``: ha) to protect the most growing
    potential (hectare-equivalents), given each cell's threats ``sev``. Exact for the linear
    programme (Sinha & Zoltners 1979)."""
    steps = []
    for k, A in area.items():
        if not A or A <= 0 or not sev.get(k):
            continue
        opts = sorted((iv["cost"], benefit_per_ha(iv["effects"], sev[k]), iv["key"]) for iv in interventions)
        hull = [(0.0, 0.0, None)]
        for c, b, j in opts:
            if b <= hull[-1][1]:
                continue  # costs as much or more and protects no more
            while len(hull) >= 2:
                (c1, b1, _), (c2, b2, _) = hull[-2], hull[-1]
                if (b2 - b1) * (c - c1) <= (b - b1) * (c2 - c1):
                    hull.pop()  # under the chord: never the best use of a dollar
                else:
                    break
            hull.append((c, b, j))
        for (c1, b1, j1), (c2, b2, j2) in zip(hull, hull[1:]):
            steps.append(((b2 - b1) / (c2 - c1), k, j1, j2, c2 - c1, b2 - b1))
    steps.sort(key=lambda s: -s[0])
    left, protected = float(budget), 0.0
    plan: dict = {}
    for _ratio, k, j1, j2, dc, db in steps:
        if left <= 0:
            break
        A = area[k]
        f = min(1.0, left / (dc * A))
        x = plan.setdefault(k, {})
        if j1 is not None:
            x[j1] = x.get(j1, 0.0) - f * A
            if x[j1] <= 1e-9:
                del x[j1]
        x[j2] = x.get(j2, 0.0) + f * A
        left -= f * dc * A
        protected += f * db * A
    return {"budget": budget, "spent": budget - max(left, 0.0), "protected_ha": protected,
            "cells": len(plan), "plan": plan}


def realized(plan: dict, sev: dict, interventions: list[dict] = INTERVENTIONS) -> float:
    """The potential a plan protected, judged with the threats that really came (``sev``)."""
    eff = {iv["key"]: iv["effects"] for iv in interventions}
    return sum(ha * benefit_per_ha(eff[j], sev.get(k, {})) for k, x in plan.items() for j, ha in x.items())


def even(area: dict, sev: dict, budget: float, interventions: list[dict] = INTERVENTIONS) -> dict:
    """No targeting: the same share of every cell's cropland treated, with the intervention that
    protects the most per dollar on average."""
    eff = [(iv, np.mean([benefit_per_ha(iv["effects"], sev.get(k, {})) for k in area]) / iv["cost"])
           for iv in interventions]
    iv = max(eff, key=lambda x: x[1])[0]
    total = sum(a for a in area.values() if a)
    share = min(1.0, budget / (iv["cost"] * total)) if total else 0.0
    plan = {k: {iv["key"]: share * a} for k, a in area.items() if a}
    return {"budget": budget, "spent": share * iv["cost"] * total, "cells": len(plan), "plan": plan,
            "intervention": iv["key"]}


def treatable(res: dict, adoption: float = ADOPTION) -> dict:
    """The hectares a programme can reach in each cell within the decade: its cropland (MODIS 2024)
    times the adoption cap."""
    return {k: adoption * (c.get("cropland_ha") or 0.0) for k, c in res["cells"].items()}


# ------------------------------------------------------------------ hindcast
def _detected_at(res: dict, ind: str, cut: int) -> dict:
    """Which cells' trends were detected with the readings up to ``cut`` only (both tests, false
    discovery rate controlled), and which way."""
    years = res["years"]
    per = {}
    for k, row in res["series"][ind].items():
        ys = [y for y, v in zip(years, row) if v is not None and y <= cut]
        vs = [v for y, v in zip(years, row) if v is not None and y <= cut]
        t = trend(ys, vs)
        if t:
            per[k] = t
    ks = list(per)
    flags, _ = benjamini_hochberg([per[k]["p"] for k in ks])
    return {k: (per[k]["per_decade"] if f and per[k]["level"] == "significant" else 0.0) for k, f in zip(ks, flags)}


def hindcast(res: dict, budgets=(5e6, 20e6, 50e6)) -> dict:
    """The decision of 2015, judged by 2016-2025. For each strategy, the threats it believed in 2015
    (from the hindcast's predictions, learned on the decades before), its plan, and the potential
    that plan really protected given what happened; against perfect foresight (the plan made with
    the real threats) and against even spending."""
    area = treatable(res)
    cut = res["hindcast"]["lgp"]["cut"]
    det = {name: _detected_at(res, ind, cut) for name, (ind, _w) in THREATS.items()}
    beliefs = {"forecast": {}, "detected": {}, "eva_alone": {}, "straight_line": {}}
    real: dict = {}
    for k in area:
        for b in beliefs:
            beliefs[b][k] = {}
        real[k] = {}
        for name, (ind, way) in THREATS.items():
            pc = (res["hindcast"][ind].get("per_cell") or {}).get(k)
            if not pc:
                continue
            rec = pc["recent"]

            def bad(mu, sd):
                # the expected change the bad way, X ~ N(mu, sd), against the last ten years known
                from .land import _shortfall
                return _shortfall(rec, mu, sd) if way < 0 else _shortfall(-rec, -mu, sd)

            fc = severity(name, rec, bad(pc["blend"], pc["blend_sd"]))
            beliefs["forecast"][k][name] = fc
            if det[name].get(k, 0.0) * way > 0:
                beliefs["detected"][k][name] = fc
            beliefs["eva_alone"][k][name] = severity(name, rec, bad(pc["eva"], pc["eva_sd"]))
            beliefs["straight_line"][k][name] = severity(name, rec, bad(pc["line"], pc["line_sd"]))
            real[k][name] = severity(name, rec, max(0.0, (pc["obs"] - rec) * way))
    out = {"cut": cut, "window": res["hindcast"]["lgp"]["window"], "learn_cuts": list(LEARN_CUTS), "budgets": {}}
    for B in budgets:
        best = realized(allocate(area, real, B)["plan"], real)
        row = {"oracle_ha": best}
        for name, sev in beliefs.items():
            got = realized(allocate(area, sev, B)["plan"], real)
            row[name] = {"protected_ha": got, "of_oracle": got / best if best else None}
        got = realized(even(area, beliefs["forecast"], B)["plan"], real)
        row["even"] = {"protected_ha": got, "of_oracle": got / best if best else None}
        out["budgets"][str(int(B))] = row
    return out


def plan(res: dict, budget: float = 20e6, evidence: str = "detected") -> dict:
    """The default plan shown on the page (the page recomputes it live for any budget)."""
    area = treatable(res)
    sev = threats(res, evidence)
    a = allocate(area, sev, budget)
    a["evidence"] = evidence
    return a


def summary(res: dict) -> dict:
    """What the page needs: the assumptions, every cell's threats under each evidence filter, the
    default plan, the hindcast of the decision."""
    return {
        "interventions": INTERVENTIONS, "sensitivity": SENSITIVITY, "sensitivity_why": SENS_WHY, "adoption": ADOPTION,
        "threats": {e: threats(res, e) for e in EVIDENCE},
        "plan": plan(res), "hindcast": hindcast(res),
        "indicators": {t: INDICATORS[i].label for t, (i, _w) in THREATS.items()},
    }


def describe(b: dict) -> list[str]:
    """The decision hindcast in words."""
    lines = []
    h = b["hindcast"]
    for B, row in h["budgets"].items():
        parts = [f"{name.replace('_', ' ')} {100 * r['of_oracle']:.0f} %" for name, r in row.items()
                 if name != "oracle_ha" and r.get("of_oracle") is not None]
        lines.append(f"US$ {int(B) / 1e6:.0f} M decided in {h['cut']}, judged by {h['window'][0]}-{h['window'][1]}: "
                     f"share of what perfect foresight would have protected: " + ", ".join(parts))
    return lines
