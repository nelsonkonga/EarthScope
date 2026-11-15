"""Data for the explainer app (detective/explain): the five investigations, made small.

    python -m detective.explain_data      # writes detective/explain/src/data/cases.json

Reads the saved investigations (data/earth/investigations/*.json) and Eva's year-by-year
dynamics of the 68 series (data/earth/dynamics/years.json); computes nothing new except the
lines of Eva's dynamics (eva/shape.py at degree 1, as detective/dynamics.py does) and the months
each link holds (the cells of detective/heat.py's reading). Values are anomalies: each month minus
the 1981–2010 mean of its calendar month; the seasonal cycle is kept separately (12 values).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from eva.shape import Shape

from .heat import Shift, heatmap
from .stats import climatology

ROOT = Path(__file__).resolve().parent.parent
INV = ROOT / "data" / "earth" / "investigations"
YEARS = ROOT / "data" / "earth" / "dynamics" / "years.json"
OUT = Path(__file__).resolve().parent / "explain" / "src" / "data" / "cases.json"

CASES = [  # order shown in the app
    ("arctic", "Arctique", "La mer de Barents se réchauffe et perd sa glace."),
    ("two_seas", "Deux mers polaires", "Barents perd sa glace, Ross en gagne : le même couplage, des tendances opposées."),
    ("sahel", "Sahel", "La pluie est revenue, le sol et l'air ont suivi."),
    ("europe", "Europe de l'Ouest", "Plus chaud et plus ensoleillé ; la pluie, elle, hésite."),
    ("levels", "Pacifique tropical", "La surface se réchauffe, la tropopause à 17 km ne bouge pas."),
]

LABELS = {
    "T2M": "Température de l'air",
    "TS": "Température de surface",
    "FRSEAICE": "Glace de mer",
    "SNODP": "Épaisseur de neige",
    "PRECTOTCORR": "Pluie",
    "SLP": "Pression au niveau de la mer",
    "GWETROOT": "Humidité du sol",
    "EVLAND": "Évaporation",
    "ALLSKY_SFC_SW_DWN": "Soleil au sol",
    "CLOUD_AMT": "Nuages",
    "TROPT": "Température de la tropopause",
    "TQV": "Vapeur d'eau",
    "RH2M": "Humidité de l'air",
}
SHORT = {  # for the heat rows
    "T2M": "Air", "TS": "Surface", "FRSEAICE": "Glace", "SNODP": "Neige", "PRECTOTCORR": "Pluie",
    "SLP": "Pression", "GWETROOT": "Sol", "EVLAND": "Évaporation", "ALLSKY_SFC_SW_DWN": "Soleil",
    "CLOUD_AMT": "Nuages", "TROPT": "Tropopause", "TQV": "Vapeur", "RH2M": "Humidité",
}
UNITS = {"mm/day": "mm/j", "%": "points", "°C": "°C", "cm": "cm", "hPa": "hPa", "K": "K"}
REGIONS = {
    "Barents Sea & Svalbard": "Mer de Barents",
    "Ross Sea (Antarctica)": "Mer de Ross",
    "Central Sahel": "Sahel central",
    "Western Europe (France)": "France",
    "Western Pacific warm pool": "Pacifique ouest",
    "Central Amazon": "Amazonie centrale",
}


def r(x, nd: int = 3):
    return None if x is None or (isinstance(x, float) and not np.isfinite(x)) else round(float(x), nd)


def eva_lines(years: list, values: list) -> dict:
    """Eva's dynamics of the yearly values, with their lines (eva/shape.py at degree 1)."""
    s = Shape(list(zip(years, values)), degree=1)
    ps = [P for P in s.pieces if P.size >= 2]
    lines = []
    for P in ps:
        a, b = s.xs[P.lo], s.xs[P.hi]
        lines.append({"from": int(a), "to": int(b), "y0": r(s.line(P, a)), "y1": r(s.line(P, b)),
                      "per_decade": r(s.slope(P) * 10)})
    return {"lines": lines}


def unit(inv: dict, key: str) -> dict:
    var, _, region = key.partition("@")
    meta, tr = inv["variables"][var], inv["trends"][key]
    region_name = inv["units"][key]["region_name"]
    ser = inv["series"][key]
    months = [tuple(map(int, m.split("-"))) for m in ser["months"]]
    raw = dict(zip(months, ser["values"]))
    clim = climatology(raw, tuple(inv["baseline"]))
    anom = [None if v is None else v - clim[m[1]] for m, v in zip(months, ser["values"])]
    a = tr["annual"]
    off = tr["baseline_mean"]  # annual raw mean - annual anomaly mean (full years)
    years, ann = [int(y) for y in a["years"]], [v - off for v in a["values"]]
    sen, mk, ols, pt = a["sen"], a["mann_kendall"], a["ols"], a["pettitt"]
    dyn = inv.get("dynamics", {}).get("units", {}).get(key) or {}
    fine = (inv["eva"].get("fine") or {}).get("units", {}).get(key)
    ext = (inv["eva"].get("extreme") or {}).get("units", {}).get(key)
    out = {
        "key": key, "var": var, "region": REGIONS.get(region_name, region_name),
        "label": LABELS.get(var, meta["label"]), "short": SHORT.get(var, var),
        "units": UNITS.get(meta["units"], meta["units"]), "raw_units": meta["units"].replace("mm/day", "mm/j"),
        "source": meta["source"],
        "collection": meta["collection"], "doi": inv["provenance"].get(var, {}).get("doi"),
        "cells": inv["units"][key].get("cells"),
        "start": f"{months[0][0]}-{months[0][1]:02d}",
        "clim": [r(clim.get(m)) for m in range(1, 13)],
        "anom": [r(v) for v in anom],
        "years": years, "annual": [r(v) for v in ann],
        "trend": {
            "per_decade": r(tr["per_decade"]), "ci": [r(c) for c in tr["per_decade_ci"]],
            "slope": r(sen["slope"], 5), "intercept": r(sen["intercept"] - off, 4),
            "mk_p": mk["p"], "mk_S": mk["S"], "t_p": ols["p"], "level": tr["verdict"]["level"],
            "direction": tr["verdict"]["direction"], "years_needed": r(tr["years_needed"], 0),
        },
        "pettitt": {"year": pt.get("year"), "p": pt.get("p"),
                    "before": r(pt["before"] - off) if pt.get("before") is not None else None,
                    "after": r(pt["after"] - off) if pt.get("after") is not None else None},
        "eva": {**eva_lines(years, ann), "steady": len(dyn.get("dynamics", [])) == 1,
                "transitions": dyn.get("transitions", [])},
    }
    if fine:
        rec = fine["recent"]
        out["norm"] = {"from": rec["from"], "above": r(rec["above_expectation"]), "p": rec["above_p"],
                       "level": fine["verdict"]["level"], "direction": fine["verdict"]["direction"],
                       "by_year": {y: r(v) for y, v in fine["departure_by_year"].items()}}
    if ext:
        out["extreme"] = "".join({1: "+", -1: "-"}.get(p, ".") for p in ext["positions"])
    return out


def links(inv: dict) -> list:
    """The links of the heat layer, with the months where each holds."""
    ext = (inv["eva"].get("extreme") or {})
    cp = ext.get("couplings") or {}
    pos = {u: v["positions"] for u, v in ext.get("units", {}).items()}
    out = []
    for L in cp.get("links", []):
        A, B = L["members"]
        T = len(pos[A])
        t = Shift(L["lag"], L["sign"])
        HB = heatmap(pos[B])
        hits = sorted(c[0] for c in heatmap(pos[A]) if 0 <= t(c)[0] < T and t(c) in HB)
        assert len(hits) == L["hits"], (A, B, len(hits), L["hits"])
        out.append({"a": A, "b": B, "lag": L["lag"], "sign": L["sign"], "level": L["level"], "p": L["p"],
                    "hits": L["hits"], "expected": r(L["expected"], 1), "union": L["union"],
                    "model": bool(L.get("model_note")), "at": hits})
    return out


def amazon() -> dict:
    """The contrast case: a series where Eva sees two dynamics (a lead, RESULTS.md § 27)."""
    d = json.loads(YEARS.read_text())
    s = next(x for x in d["series"] if x["region"] == "Central Amazon" and x["var"] == "EVLAND")
    years = [int(y) for y in s["years"]]
    base = [v for y, v in zip(years, s["values"]) if 1981 <= y <= 2010]
    off = float(np.mean(base))
    ann = [v - off for v in s["values"]]
    return {"label": LABELS["EVLAND"], "region": REGIONS["Central Amazon"], "units": "mm/j",
            "years": years, "annual": [r(v) for v in ann], **eva_lines(years, ann),
            "transitions": s["transitions"], "control_eva": s["control_eva"],
            "control_pettitt": s["control_pettitt"], "pettitt": s["pettitt"], "pettitt_p": s["pettitt_p"]}


def main() -> None:
    cases = []
    for key, title, lead in CASES:
        inv = json.loads((INV / f"{key}.json").read_text())
        keys = list(inv["trends"])
        cases.append({
            "key": key, "title": title, "lead": lead,
            "regions": [{"name": REGIONS.get(g["name"], g["name"]), "south": g["south"], "north": g["north"],
                         "west": g["west"], "east": g["east"]} for g in inv["regions"]],
            "units": [unit(inv, k) for k in keys],
            "links": links(inv),
            "same_process": [{"vars": p["variables"], "sign": -1 if "-y" in p["transform"] else 1}
                             for p in ((inv["eva"].get("extreme") or {}).get("couplings") or {}).get("same_process", [])],
        })
    data = {"cases": cases, "amazon": amazon(), "control": {"eva": 0.055, "pettitt": 0.647, "series": 68}}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    print(f"{OUT.relative_to(ROOT)}: {OUT.stat().st_size / 1024:.0f} KB, "
          f"{sum(len(c['units']) for c in cases)} series, {sum(len(c['links']) for c in cases)} links")


if __name__ == "__main__":
    main()
