"""The detective's investigation: from a question (what? where?) to a verdict.

1. Discovery (earthdata-mcp): the user's words -> GCMD science keywords and their
   definitions -> the NASA datasets that measure it over the region and period (MODIS, GPM,
   AIRS, OMI, MERRA-2, GLDAS...) ; and the provenance of every suspect investigated (its CMR
   collection, variable, DOI).
2. Acquisition (NASA POWER): the monthly series of each variable over the region (the
   area-weighted mean of its grid cells), and every cell for the map.
3. Classical statistics (``stats.trend_report``): rate of change, t-test, Mann-Kendall,
   Sen's slope, confidence intervals, change point, years needed.
4. Eva (``watch.Watch``): her norm of each dynamic and how far the recent years left it
   (fine grain); which dynamics leave their norm together (extreme grain: meta molettes).
5. The story: plain-language findings for students.
"""

from __future__ import annotations

import datetime as dt
import math

import numpy as np

from . import changes, dynamics, power, stats
from .heat import same_process
from .mcp import EarthdataMCP, MCPError
from .regions import Region
from .variables import VARIABLES, Variable, model_note
from .watch import EXTREME_CUTS, Watch


def clean(x):
    """JSON-safe: tuples -> lists, numpy -> Python, NaN / inf -> None."""
    if isinstance(x, dict):
        return {str(k): clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    if isinstance(x, (np.floating, float)):
        f = float(x)
        return f if math.isfinite(f) else None
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, np.ndarray):
        return clean(x.tolist())
    return x


def _label(k) -> str:
    return f"{k[0]}-{k[1]:02d}"


# ------------------------------------------------------------- discovery
def discover(mcp: EarthdataMCP, words: str, region: Region, start: int, end: int, n_keywords: int = 3,
             n_collections: int = 8) -> dict:
    """The user's words -> GCMD keywords -> NASA collections over the region and period."""
    out = {"query": words, "keywords": [], "collections": {}, "errors": []}
    try:
        seen = []
        for k in mcp.keywords(words, "sciencekeywords", limit=10):
            if k["prefLabel"] not in [s["prefLabel"] for s in seen]:
                seen.append({"prefLabel": k["prefLabel"], "definition": k.get("definition")})
            if len(seen) >= n_keywords:
                break
        out["keywords"] = seen
        for k in seen:
            cols = mcp.collections(keyword=k["prefLabel"], has_granules=True, spatial_wkt_geometry=region.wkt(),
                                   temporal_start_date=f"{start}-01-01T00:00:00Z",
                                   temporal_end_date=f"{end}-12-31T23:59:59Z", limit=n_collections)
            out["collections"][k["prefLabel"]] = [{
                "concept_id": c.get("concept_id"), "short_name": c.get("short_name"), "version": c.get("version"),
                "title": c.get("entry_title"), "platforms": c.get("platforms"), "instruments": c.get("instruments"),
                "level": c.get("processing_level_id"), "start": c.get("time_start"), "end": c.get("time_end"),
                "doi": c.get("doi"), "provider": c.get("provider_id"),
                "temporal_resolution": c.get("temporal_resolution"), "spatial_resolution": c.get("spatial_resolution"),
            } for c in cols]
    except (MCPError, OSError) as e:  # discovery is a help, never a blocker
        out["errors"].append(str(e))
    return out


def provenance(mcp: EarthdataMCP, variables: list[Variable]) -> dict:
    """Where each suspect comes from, as the CMR describes it (collection, variable, DOI)."""
    out, cols = {}, {}
    for v in variables:
        rec = {"source": v.source, "collection": v.collection, "variable": v.variable, "served_by": "NASA POWER"}
        try:
            if v.collection not in cols:
                found = mcp.collections(short_name=v.collection, limit=3)
                cols[v.collection] = found[0] if found else None
            c = cols[v.collection]
            if c:
                rec.update(concept_id=c.get("concept_id"), title=c.get("entry_title"), doi=c.get("doi"),
                           collection_start=c.get("time_start"),
                           landing=next((u["url"] for u in c.get("related_urls", [])
                                         if u.get("type") == "DATA SET LANDING PAGE"), None))
                hit = [x for x in mcp.variables(collection_concept_id=c["concept_id"], keyword=v.variable, limit=10)
                       if x.get("name") == v.variable]
                if hit:
                    rec.update(long_name=hit[0].get("long_name"), native_units=hit[0].get("units"),
                               definition=hit[0].get("definition"))
        except (MCPError, OSError) as e:
            rec["error"] = str(e)
        out[v.key] = rec
    return out


# ----------------------------------------------------------------- maps
def map_trends(cells: list, base: tuple) -> list[dict]:
    """Trend of every grid cell: Sen's slope of its annual means and the Mann-Kendall p."""
    out = []
    for la, lo, s in cells:
        ann = stats.annual_means(s)
        if len(ann) < 10:
            continue
        y = np.array(list(ann), float)
        v = np.array(list(ann.values()), float)
        mk = stats.mann_kendall(v, autocorr=True)
        clim = [x for (yy, _m), x in s.items() if x is not None and base[0] <= yy <= base[1]]
        out.append({"lat": la, "lon": lo, "per_decade": 10 * stats.sen_slope(y, v), "p": mk["p"],
                    "mean": float(np.mean(clim)) if clim else None})
    return out


def _step(values) -> float:
    """The grid spacing: the smallest gap between distinct coordinates."""
    v = sorted(set(round(x, 4) for x in values))
    gaps = [b - a for a, b in zip(v, v[1:]) if b - a > 1e-6]
    return min(gaps) if gaps else 1.0


def field_transitions(cells: list[dict], dlat: float | None = None, dlon: float | None = None,
                      z: float = 2.0) -> dict:
    """Where the trend dynamic changes across the region.

    The trend of each cell is one dynamic (its class: significantly falling −2, falling −1,
    rising +1, significantly rising +2). A transition is not a question of time (the user's
    rule): stepping from a cell to its neighbour is a transition of the field, read along →
    and ↑ and — the same transition read backwards — along ← and ↓. An ``eva.dynamics.Molette``
    learns the norm of these transitions over the region; a transition out of that norm where
    the trend changes sign is a border: the dynamic reverses there."""
    from eva.dynamics import WORLD, Molette

    def cls(c):
        v, p = c.get("per_decade") or 0.0, c.get("p")
        s = 1 if v > 0 else -1 if v < 0 else 0
        return 2 * s if (p is not None and p < 0.05 and s) else s

    dlat = dlat or _step(c["lat"] for c in cells)
    dlon = dlon or _step(c["lon"] for c in cells)
    grid = {(round(c["lat"] / dlat), round(c["lon"] / dlon)): c for c in cells}
    mol = Molette()
    pairs = []
    for (i, j), a in grid.items():
        for d in ((0, 1), (1, 0)):  # east, north; west and south are the same transitions read backwards
            b = grid.get((i + d[0], j + d[1]))
            if b is None:
                continue
            ca, cb = cls(a), cls(b)
            mol.record((d, ca), WORLD, cb, z)
            mol.record(((-d[0], -d[1]), cb), WORLD, ca, z)
            pairs.append((a, b, d, ca, cb))
    borders, changes = [], 0
    for a, b, d, ca, cb in pairs:
        if ca * cb >= 0:
            continue
        changes += 1
        s = (mol.surprise((d, ca), WORLD, cb) + mol.surprise(((-d[0], -d[1]), cb), WORLD, ca)) / 2
        if mol.is_extreme(s, z) or (abs(ca) == 2 and abs(cb) == 2):
            borders.append({"a": [a["lat"], a["lon"]], "b": [b["lat"], b["lon"]], "classes": [ca, cb],
                            "strong": abs(ca) == 2 and abs(cb) == 2, "surprise": s})
    counts: dict = {}
    for c in grid.values():
        counts[cls(c)] = counts.get(cls(c), 0) + 1
    return {"dlat": dlat, "dlon": dlon, "pairs": len(pairs), "sign_changes": changes, "borders": borders,
            "strong": sum(1 for b in borders if b["strong"]), "classes": counts,
            "typical_surprise": mol.s_mean, "spread": mol.spread()}


# ---------------------------------------------------------------- story
def _fmt(x: float, units: str) -> str:
    a = abs(x)
    d = 3 if a < 0.01 else 2 if a < 1 else 1 if a < 100 else 0
    return f"{x:+.{d}f} {units}".strip()


def story(res: dict) -> list[dict]:
    """Plain-language findings, most important first."""
    lines = []
    units = res["units"]
    for u, info in units.items():
        tr = res["trends"].get(u)
        if not tr:
            continue
        var = VARIABLES[info["variable"]]
        v = tr["verdict"]
        eva = res["eva"]["fine"]["units"].get(u) if res["eva"].get("fine") else None
        rate = _fmt(tr["per_decade"], var.units + " per decade")
        ci = tr["per_decade_ci"]
        what = f"{var.label} — {info['region_name']}"
        txt = (f"{what}: {rate} (95 % range {ci[0]:+.3g} to {ci[1]:+.3g}). {v['text']} "
               f"Mann-Kendall p = {tr['annual']['mann_kendall']['p']:.2g}, t-test p = {tr['annual']['ols']['p']:.2g}.")
        if v["level"] != "significant" and math.isfinite(tr["years_needed"]):
            have = tr["years"]
            txt += (f" With this much natural variability, a trend of this size needs about "
                    f"{tr['years_needed']:.0f} years of data to stand out ({have:.0f} so far).")
        dyn = (res.get("dynamics") or {}).get("units", {}).get(u)
        if dyn:
            txt += f" Eva's dynamics, read year by year: {dyn['text']}."
        if eva:
            txt += " Eva: " + eva["verdict"]["text"]
        lines.append({"kind": "trend", "unit": u, "level": v["level"], "direction": v["direction"], "text": txt,
                      "score": (2 if v["level"] == "significant" else 1 if v["level"] == "suggestive" else 0)
                      + (1 if eva and eva["verdict"]["level"] == "left its norm" else 0)})
    # changes of dynamics that several variables make together (the transitions' meta molettes)
    for sh in (res.get("dynamics") or {}).get("shared", []):
        if sh["p"] >= 0.01:
            continue
        names = [VARIABLES[units[m]["variable"]].label.lower() if m in units else m for m in sh["members"]]
        lines.append({"kind": "shared", "score": 4, "text": (
            f"In {sh['region_name']}, {len(names)} variables change their dynamic together around {sh['year']}: "
            f"{', '.join(names)} (chance would gather as many {sh['p']:.1g} of the time). A real change of regime, "
            f"or a change in what the reanalysis assimilates: MERRA-2's known breaks are its stream joins "
            f"(1990–91, 2000–01, 2010–11); anything else must be checked against an independent dataset.")})
    # changes of dynamic over many grid cells together (the heatmap of transitions: their types)
    for u, ch in (res.get("changes") or {}).items():
        for c in ch.get("changes", []):
            joins = [y for y in (1990.5, 2000.5, 2010.5) if abs(c["year"] - y) <= 2]
            caveat = (f" It falls on one of MERRA-2's stream joins ({int(joins[0] - 0.5)}–{int(joins[0] + 0.5)}): "
                      f"check it against an independent dataset before believing it." if joins else
                      " Not on one of MERRA-2's stream joins; still a reanalysis, to be checked against "
                      "independent data.")
            lines.append({"kind": "change", "unit": u, "score": 3, "text": (
                f"{ch.get('label', u)}: around {c['year']:.0f} the {c['type'].split(' ', 1)[0]} "
                f"{c['type'].split(' ', 1)[1]} in {c['cells']} of {c['of']} grid cells at once "
                f"(chance gathers as many cells, anywhere, of any type, {c['p']:.1g} of the time or less)." + caveat)})
    # types of types: one type of change followed by another in many cells (proven the same way)
    for u, ch in (res.get("changes") or {}).items():
        for b in ch.get("bridges", []):
            lines.append({"kind": "change", "unit": u, "score": 2, "text": (
                f"{ch.get('label', u)}: in {b['cells']} of {b['of']} grid cells, the {b['from']} and then "
                f"the {b['to']} (chance gives that sequence in as many cells, anywhere, {b['p']:.1g} of the "
                f"time or less). A sequence of changes of dynamic, cell by cell; a reanalysis still, to be "
                f"checked against independent data.")})
    # opposite trends of one variable in two regions
    by_var: dict = {}
    for u, info in units.items():
        tr = res["trends"].get(u)
        if tr and tr["verdict"]["level"] in ("significant", "suggestive"):
            by_var.setdefault(info["variable"], []).append((u, info, tr))
    for key, lst in by_var.items():
        ups = [x for x in lst if x[2]["per_decade"] > 0]
        downs = [x for x in lst if x[2]["per_decade"] < 0]
        if ups and downs:
            var = VARIABLES[key]
            lines.append({"kind": "opposite", "score": 4, "text": (
                f"Opposite trends: {var.label.lower()} is rising in {', '.join(x[1]['region_name'] for x in ups)} "
                f"and falling in {', '.join(x[1]['region_name'] for x in downs)}. One process can push the same "
                f"variable in opposite directions in two places — look at the links below to see whether the same "
                f"months move both.")})
    for u, f in res.get("fields", {}).items():
        if not f.get("borders"):
            continue
        info, var = units[u], VARIABLES[units[u]["variable"]]
        up = f["classes"].get("2", f["classes"].get(2, 0)) + f["classes"].get("1", f["classes"].get(1, 0))
        down = f["classes"].get("-2", f["classes"].get(-2, 0)) + f["classes"].get("-1", f["classes"].get(-1, 0))
        if not f["strong"] and min(up, down) < 0.15 * max(1, up + down):
            continue  # a few isolated cells of the other sign: no border worth telling
        lines.append({"kind": "border", "unit": u, "score": 3 if f["strong"] else 1, "text": (
            f"Inside {info['region_name']}, {var.label.lower()} rises in {up} grid cells and falls in {down}: "
            f"reading the field from cell to cell, Eva found {len(f['borders'])} out-of-norm transitions where the "
            f"trend reverses" + (f", {f['strong']} of them between significant opposite trends." if f["strong"] else "."))})
    # the heatmaps of the departures: what leaves its norm together, which way, what comes first
    heat = (res["eva"].get("extreme") or {}).get("couplings") or {}
    for p in heat.get("same_process", []):
        vs = [VARIABLES[k].label.lower() for k in p["variables"]]
        turns = []
        for members in p["links"]:
            dirs = [res["trends"].get(m, {}).get("verdict", {}) for m in members]
            ups = [VARIABLES[units[m]["variable"]].label.lower() + (" rises" if d.get("direction") == "rising" else " falls")
                   for m, d in zip(members, dirs) if d.get("level") in ("significant", "suggestive")]
            if ups:
                turns.append(f"in {units[members[0]]['region_name']}, {' and '.join(ups)}")
        lines.append({"kind": "process", "score": 5, "text": (
            f"One process in {' and '.join(p['regions'])}: in each, {vs[0]} and {vs[1]} leave their norm "
            + ("in the same months" if p["transform"].startswith("(x,") else "with the same delay")
            + (" in opposite directions" if p["transform"].endswith("-y)") else " the same way")
            + " — the same transformation carries one onto the other in every region"
            + (f", although the trends differ ({'; '.join(turns)})." if len(turns) > 1 else "."))})
    told = set()
    for x in heat.get("links", []):
        told.add(tuple(sorted(x["members"])))
        note = model_note(*(units[m]["variable"] for m in x["members"])) if all(m in units for m in x["members"]) else None
        x["model_note"] = note  # shown on the page too
        lines.append({"kind": "link", "score": (3 + (1 if x["union"] else 0)) if x["level"] == "proven" else 1,
                      "text": x["text"] + (f" Model note: {note}." if note else ""), "members": x["members"],
                      "phase": x["sign"], "lag": x["lag"], "evidence": x["level"], "grain": "extreme",
                      "model_note": note})
    for g in res["eva"].get("extreme", {}).get("metas", []) + res["eva"].get("fine", {}).get("metas", []):
        key = tuple(sorted(g["members"]))
        if len(key) < 2 or key in told:  # the same link seen at both grains is told once
            continue
        told.add(key)
        lines.append({"kind": "link", "score": 2 + (1 if g.get("phase_p", 1) < 0.05 else 0), "text": g["text"],
                      "members": g["members"], "phase": g["phase"], "grain": g.get("grain")})
    lines.sort(key=lambda r: -r["score"])
    return lines


# ---------------------------------------------------------- investigation
def investigate(regions: list[Region], variables: list[str], words: str | None = None, base: tuple = (1981, 2010),
                start: int = 1981, end: int = 2025, with_mcp: bool = True, offline: bool = False,
                log=print, change_draws: int = 99) -> dict:
    """The whole investigation; every series is a unit ``VAR`` (one region) or ``VAR@region``.
    ``change_draws``: the shuffled fields chance is read on for the map of changes of dynamic
    (detective/changes.py; 0 skips it — minutes of computing)."""
    vars_ = [VARIABLES[k] for k in variables]
    multi = len(regions) > 1
    series, cells, units = {}, {}, {}
    for r in regions:
        for v in vars_:
            u = f"{v.key}@{r.key}" if multi else v.key
            log(f"  fetching {v.label} over {r.name} ({max(start, v.first_year)}–{end}) ...")
            s, cs = power.region_series(v.key, r, max(start, v.first_year), end, offline=offline)
            if v.scale != 1.0:  # display units (fractions in %, pressure in hPa)
                s = {k: (x * v.scale if x is not None else None) for k, x in s.items()}
                cs = [(la, lo, {k: (x * v.scale if x is not None else None) for k, x in c.items()}) for la, lo, c in cs]
            series[u], cells[u] = s, cs
            units[u] = {"variable": v.key, "region": r.key, "region_name": r.name,
                        "label": f"{v.label} ({r.name})" if multi else v.label, "cells": len(cs)}
    log("  classical statistics ...")
    trends = {u: stats.trend_report(s, base) for u, s in series.items()}
    # Eva watches the units that share the full period together (a shorter record is watched alone)
    full = [u for u in series if VARIABLES[units[u]["variable"]].first_year <= base[0]]
    labels = {u: units[u]["label"] for u in series}
    eva = {}
    if full:
        log(f"  Eva watches {len(full)} dynamics (fine grain, then extreme grain) ...")
        eva["fine"] = Watch({u: series[u] for u in full}, base, labels=labels).run()
        eva["extreme"] = Watch({u: series[u] for u in full}, base, labels=labels, cuts=EXTREME_CUTS).run()
        if eva["extreme"].get("couplings"):  # the degree above: the same transformation in several regions
            eva["extreme"]["couplings"]["same_process"] = same_process(eva["extreme"]["couplings"]["links"], units)
    late = [u for u in series if u not in full]
    if late:
        eva["alone"] = {}
        for u in late:
            first = min(k[0] for k, v in series[u].items() if v is not None)
            b = (first, first + (base[1] - base[0]) // 2)
            try:
                eva["alone"][u] = Watch({u: series[u]}, b, labels=labels).run()
            except ValueError as e:
                eva["alone"][u] = {"error": str(e)}
    log("  maps ...")
    maps = {u: map_trends(cells[u], base) for u in series}
    fields = {u: field_transitions(m) for u, m in maps.items()}
    res = {
        "created": dt.date.today().isoformat(),
        "regions": [r.as_dict() for r in regions],
        "period": [start, end], "baseline": list(base),
        "variables": {v.key: v.as_dict() for v in vars_},
        "units": units,
        "series": {u: {"months": [_label(k) for k, x in sorted(s.items()) if x is not None],
                       "values": [x for _k, x in sorted(s.items()) if x is not None]} for u, s in series.items()},
        "trends": trends, "eva": eva, "maps": maps, "fields": fields,
    }
    if with_mcp:
        log("  earthdata-mcp: provenance and discovery ...")
        mcp = EarthdataMCP(offline=offline)
        res["provenance"] = provenance(mcp, vars_)
        res["discovery"] = discover(mcp, words or " ".join(v.keywords[0].lower() for v in vars_[:1]),
                                    regions[0], start, end)
    res["dynamics"] = dynamics.read(res)  # Eva's dynamics of each trend, read at the year
    if change_draws:
        log("  where and when the dynamics changed, cell by cell ...")
        res["changes"] = changes.read(cells, {u: units[u]["label"] for u in units}, draws=change_draws)
    res["story"] = story(res)
    return clean(res)
