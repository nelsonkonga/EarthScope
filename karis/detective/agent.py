"""Ask Eva: an assistant that answers anyone's questions about the land, with Eva's tools.

A person who is not a scientist asks, in their own words, « is the rainy season getting shorter
near Garoua? » or « where is the ground being stripped bare? ». Claude (through the Anthropic API)
answers, but every number it gives comes from a tool that runs HERE, on the tested results of the
land analysis (``data/earth/land/<region>.json``) and on the cached NASA data:

- ``find_place``      a town or village by name -> where it is, and whether the map covers it;
- ``place_report``    everything the analysis knows about the cell under a point: each indicator's
                      trend and how sure it is (Sen, Mann-Kendall, t-test, false discovery rate), Eva's
                      dynamics and her control, the MERRA-2 seams, satellite rain and plants, the
                      forecast for 2026-2035, the land cover;
- ``region_overview`` what holds over a whole region (and what does not);
- ``rank_places``     where an indicator changed the most, for better or worse;
- ``read_series``     a fresh reading of one series at one place: a yearly indicator, or a NASA POWER
                      variable restricted to chosen months (« only July to September »): the classical
                      trend AND Eva's dynamics with her own control;
- ``bare_ground``     where vegetation gave way to bare ground (``detective/scars.py``): the trace of
                      open-pit and artisanal mines, quarries, also of towns and roads; what it cannot
                      see (rare earths, any deposit underground) it says.

The page sends the conversation (text only) and gets back the answer and the places it talked
about, so the map can fly there. Served by ``detective.serve`` (local) or on its own:

    ANTHROPIC_API_KEY=... python -m detective.agent [port]     # POST /api/ask, GET /api/ask/status

Beyond the map, the agent chooses its own data: the variables (NASA POWER, IMERG, MODIS), the place
or places at once (an analysed region, a named region, a box, a point, a town), and lets Eva read them
(``eva_trend``: one variable at up to four places; ``eva_links``: how the chosen variables are linked,
Eva's heatmaps of the detective). Every import goes through ``datastore.STORE``: a data set (a variable
at a grid cell, a satellite pixel, a MODIS window) is downloaded once, never twice, within a budget per
import and per hour. No full land investigation is started from the public page.
"""

from __future__ import annotations

import json
import math
import re
import sys
import threading
import time
import unicodedata
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np

from . import datastore
from . import land
from . import stats

MODEL = "claude-opus-5-5"
EFFORT = "medium"  # answers to the public: careful with numbers, not slow
MAX_TOKENS = 16000
MAX_STEPS = 12  # tool rounds per question (an import, a reading and a comparison take a few)
MAX_QUESTION = 1200  # characters
MAX_TURNS = 12  # earlier turns kept from the conversation the page sends
SCARS = land.OUT  # <region>_scars.json, written by detective/scars.py
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
EVA_KEYS = ("lgp", "aridity", "soil_root", "surface_temp")


def _r(x, sig: int = 3):
    """Round for the model (fewer tokens, no false precision)."""
    if isinstance(x, float):
        if not math.isfinite(x):
            return None
        return float(f"{x:.{sig}g}") if x != 0 else 0.0
    if isinstance(x, dict):  # coordinates keep their 3 decimals (13.75 is not 13.8)
        return {k: (round(v, 3) if k in ("lat", "lon") and isinstance(v, float) else _r(v, sig)) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_r(v, sig) for v in x]
    return x


def _fold(s: str) -> str:
    """Lower case, no accents: « Bétaré-Oya » finds « Betare Oya »."""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def _km(la1, lo1, la2, lo2) -> float:
    p1, p2 = math.radians(la1), math.radians(la2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(min(1.0, a)))


# ------------------------------------------------------------------ the tools
class LandTools:
    """Eva's tools over the analysed regions on disk. Every method returns plain JSON."""

    def __init__(self, folder: Path = land.OUT, store: "datastore.DataStore | None" = None):
        self.folder = folder
        self.store = store or datastore.STORE
        self._regions: dict = {}
        self._mtimes: dict = {}
        self._power: dict = {}

    # -- data on disk
    def regions(self) -> dict:
        files = {f.stem: f for f in self.folder.glob("*.json") if not f.stem.endswith("_scars")}
        for key, f in files.items():
            m = f.stat().st_mtime
            if self._mtimes.get(key) != m:
                self._regions[key] = json.loads(f.read_text())
                self._mtimes[key] = m
        for key in list(self._regions):
            if key not in files:
                del self._regions[key]
        return self._regions

    def _towns(self) -> list:
        from .places import STORE
        try:
            return json.loads(STORE.read_text(encoding="utf-8")).get("towns", [])
        except (OSError, ValueError):
            return []

    def _country_name(self, iso: str) -> str:
        from .places import STORE
        try:
            return json.loads(STORE.read_text(encoding="utf-8"))["countries"].get(iso, {}).get("name", iso)
        except (OSError, ValueError, KeyError):
            return iso

    def _nearest_town(self, lat: float, lon: float) -> dict | None:
        ts = self._towns()
        if not ts:
            return None
        t = min(ts, key=lambda t: _km(lat, lon, t[1], t[2]))
        return {"name": t[0], "km": round(_km(lat, lon, t[1], t[2])), "country": self._country_name(t[4])}

    def _cell(self, lat: float, lon: float, region: str | None = None) -> tuple[str, str, dict] | None:
        """The analysed cell under a point: (region key, cell key, results); the country-wide region
        first when several cover the point."""
        regs = self.regions()
        order = sorted(regs, key=lambda k: (k != region, not regs[k]["region"].get("country"), k))
        for rk in order:
            res = regs[rk]
            g = res["grid"]
            best = min(res["cells"], key=lambda k: abs(res["cells"][k]["lat"] - lat) / g["dlat"]
                       + abs(res["cells"][k]["lon"] - lon) / g["dlon"])
            c = res["cells"][best]
            if abs(c["lat"] - lat) <= g["dlat"] / 2 + 1e-9 and abs(c["lon"] - lon) <= g["dlon"] / 2 + 1e-9:
                return rk, best, res
        return None

    def _region(self, region: str | None) -> tuple[str, dict]:
        regs = self.regions()
        if not regs:
            raise ValueError("no analysed region on disk")
        if region and region in regs:
            return region, regs[region]
        rk = sorted(regs, key=lambda k: (not regs[k]["region"].get("country"), k))[0]
        return rk, regs[rk]

    def _seams(self, years) -> list:
        return [round(t, 1) for t in years if min(abs(t - j) for j in land.STREAM_JOINS) <= 1.0]

    # -- 1
    def find_place(self, name: str) -> dict:
        q = _fold(name)
        if not q:
            return {"error": "empty name"}
        hits = []
        for t in self._towns():
            n = _fold(t[0])
            rank = 0 if n == q else 1 if n.startswith(q) else 2 if q in n else None
            if rank is not None:
                hits.append((rank, -(t[3] or 0), t))
        hits.sort(key=lambda h: (h[0], h[1]))
        out = []
        for _r0, _p, t in hits[:5]:
            cell = self._cell(t[1], t[2])
            out.append({"name": t[0], "lat": round(t[1], 3), "lon": round(t[2], 3), "population": t[3],
                        "country": self._country_name(t[4]),
                        "on_the_map": bool(cell), "region": cell[0] if cell else None})
        if not out:
            return {"found": [], "note": "No town of that name in Natural Earth's populated places (only towns of "
                                         "some size are listed). Ask for a nearby larger town, or coordinates."}
        return {"found": out}

    # -- 2
    def place_report(self, lat: float, lon: float, indicators: list | None = None) -> dict:
        hit = self._cell(lat, lon)
        if not hit:
            return {"error": "outside the analysed regions", "regions": {k: r["region"]["name"]
                                                                          for k, r in self.regions().items()}}
        rk, key, res = hit
        c = res["cells"][key]
        keys = indicators or ["lgp", "rain", "soil_root", "aridity", "surface_temp", "npp"]
        out = {"region": rk, "cell": {"lat": c["lat"], "lon": c["lon"], "size_km2": round(c["area_km2"]),
                                      "size_deg": [res["grid"]["dlat"], res["grid"]["dlon"]]},
               "nearest_town": self._nearest_town(c["lat"], c["lon"]),
               "land_cover_modis": _r({"cropland_share": c.get("cropland"), "forest_share": c.get("forest")}),
               "period": res["period"], "indicators": {}}
        for k in keys:
            ind = res["indicators"].get(k)
            if not ind:
                continue
            d = (res["detect"].get(k) or {}).get("cells", {}).get(key)
            row = {"label": ind["label"], "units": ind["units"], "what": ind["simple"], "source": ind["source"],
                   "higher_is_better": {1: True, -1: False}.get(ind["good"])}
            if d:
                row["classical_trend"] = _r({
                    "per_decade": d["per_decade"], "ci95": d["ci"], "p_mann_kendall": d["p_mk"], "p_t_test": d["p_t"],
                    "level": d["level"], "direction": d["direction"], "detected_after_false_discovery_control": d.get("fdr"),
                    "total_change": d["total"], "baseline_mean": d["base_mean"], "years": [d["from"], d["to"]]})
            e = (res.get("eva", {}).get(k) or {}).get("cells", {}).get(key)
            if e:
                row["eva"] = _r({"reading": e["text"], "dynamics": e["dynamics"], "transitions": e["transitions"],
                                 "transitions_near_merra2_seams": self._seams(e["transitions"]),
                                 "control_false_change_rate": e["control"]})
            f = (res.get("forecast", {}).get(k) or {}).get(key)
            if f:
                row["forecast_2026_2035"] = _r({"mean": f["pred"], "range90": [f["lo90"], f["hi90"]],
                                                "recent_5y": f["recent"], "p_lower_than_recent": f.get("p_down")})
            rep = (res.get("replication", {}).get("per_cell", {}).get(key) or {}).get(k)
            if rep:
                row["satellite_rain_check_since_2001"] = _r({
                    "reanalysis_trend_per_decade": rep.get("merra"), "imerg_trend_per_decade": rep.get("imerg"),
                    "year_to_year_correlation": rep.get("r"), "status": rep.get("status")})
            out["indicators"][k] = row
        dr = res.get("drivers", {}).get(key)
        if dr:
            out["drivers_change_since_1981_pct"] = _r(dr)
        cv = res.get("cover_change", {}).get("per_cell", {}).get(key)
        if cv:
            out["cropland_2001_to_2024"] = _r({"2001": cv.get("cropland_2001"), "2024": cv.get("cropland_2024")})
        sc = self._scars_near(rk, c["lat"], c["lon"], 40)
        if sc is not None:
            out["bare_ground_patches_within_40km"] = len(sc)
        out["notes"] = ("MERRA-2 was produced in four streams joined at 1991/92, 2000/01 and 2010/11: a change of "
                        "dynamic at a join is first a lead on the data. A trend counts as detected only when Mann-"
                        "Kendall and the t-test agree and it survives the false discovery control over the map.")
        return out

    # -- 3
    def region_overview(self, region: str | None = None) -> dict:
        if region == "all":
            return {"regions": [self.region_overview(k) for k in sorted(self.regions())]}
        rk, res = self._region(region)
        out = {"region": rk, "name": res["region"]["name"], "why": res["region"].get("why"), "period": res["period"],
               "cells": len(res["cells"]), "indicators": {}}
        for k, det in res["detect"].items():
            s = det["summary"]
            row = {"label": res["indicators"][k]["label"], "units": res["indicators"][k]["units"],
                   "tested": s["tested"], "detected": s["detected"], "expected_by_chance": s["expected_by_chance"],
                   "worse_cells": s.get("worse"), "better_cells": s.get("better"),
                   "area_worse_km2": s.get("area_worse_km2"), "area_better_km2": s.get("area_better_km2"),
                   "map_wide_significant": s.get("field_significant")}
            e = res.get("eva", {}).get(k)
            if e:
                row["eva"] = {"cells_whose_dynamic_changed": e["changed"], "expected_from_her_control": e["expected_by_control"],
                              "p": e["p_changed"], "transitions_near_merra2_seams": e["stream_joins"],
                              "changes_made_together": [{kk: ch[kk] for kk in ("type", "year", "cells", "of", "p")}
                                                        for ch in (e.get("changes") or {}).get("changes", [])],
                              "borders": len((e.get("borders") or {}).get("borders", [])),
                              "strong_borders": (lambda s: s if isinstance(s, int) else len(s or []))(
                                  (e.get("borders") or {}).get("strong"))}
            h = res.get("hindcast", {}).get(k)
            if h:
                row["forecast_test_2016_2025"] = {"eva_weight": h["weights"].get("eva"), "coverage90": h.get("coverage90")}
            out["indicators"][k] = _r(row)
        out["crosscheck"] = _r(res.get("crosscheck"))
        out["story"] = [s["text"] for s in res.get("story", [])[:10]]
        return out

    # -- 4
    def rank_places(self, indicator: str, which: str, region: str | None = None, n: int = 8) -> dict:
        if region == "all":  # every analysed region; a cell two regions share is kept once
            regs = self.regions()
            order = sorted(regs, key=lambda k: (not regs[k]["region"].get("country"), k))
            got, seen = [], set()
            for k in order:
                r = self.rank_places(indicator, which, k, 20)
                if "error" in r:
                    return r
                for q in r["places"]:
                    if (q["lat"], q["lon"]) not in seen:
                        seen.add((q["lat"], q["lon"]))
                        got.append({**q, "region": k})
            if which != "eva_changed":
                got.sort(key=lambda q: -abs(q.get("per_decade") or 0))
            return {"region": "all", "regions": order, "indicator": indicator, "which": which,
                    "count": len(got), "places": got[:max(1, min(n, 20))]}
        rk, res = self._region(region)
        det = res["detect"].get(indicator)
        if not det:
            return {"error": f"unknown indicator {indicator!r}", "indicators": list(res["detect"])}
        good = res["indicators"][indicator]["good"]
        rows = []
        if which == "eva_changed":
            e = res.get("eva", {}).get(indicator)
            if not e:
                return {"error": "Eva reads only " + ", ".join(EVA_KEYS)}
            for k, c in e["cells"].items():
                if len(c["dynamics"]) > 1:
                    rows.append((-(abs(c["dynamics"][-1]["per_decade"] - c["dynamics"][0]["per_decade"])), k,
                                 {"eva": c["text"], "control": c["control"],
                                  "near_seams": self._seams(c["transitions"])}))
        else:
            for k, d in det["cells"].items():
                if not d.get("fdr"):
                    continue
                worse = (d["per_decade"] * (good or 1)) < 0
                if (which == "worse") == worse:
                    rows.append((-abs(d["per_decade"]), k, {"per_decade": d["per_decade"], "ci95": d["ci"]}))
        rows.sort(key=lambda r: r[0])
        out = []
        for _s, k, info in rows[:max(1, min(n, 20))]:
            c = res["cells"][k]
            out.append(_r({"lat": c["lat"], "lon": c["lon"], "near": self._nearest_town(c["lat"], c["lon"]), **info}))
        return {"region": rk, "indicator": indicator, "units": res["indicators"][indicator]["units"], "which": which,
                "count": len(rows), "places": out}

    # -- 5
    def _power_series(self, rk: str, res: dict, key: str, param: str) -> dict | None:
        """The monthly NASA POWER series of one cell, from the cache (no download)."""
        from . import power
        from .regions import parse_region
        if (rk, param) not in self._power:
            r = res["region"]
            reg = parse_region(f"{r['south']},{r['north']},{r['west']},{r['east']}")
            try:
                cells = power.monthly_cells(param, reg, land.FIRST, land.LAST, offline=True)
            except Exception:  # noqa: BLE001 - not cached: say so
                cells = []
            self._power[(rk, param)] = {land.cell_key(la, lo): s for la, lo, s in cells}
        got = self._power[(rk, param)]
        if key in got:
            return got[key]
        la, lo = land._latlon(key)
        near = min(got, key=lambda k: _km(la, lo, *land._latlon(k)), default=None)
        return got.get(near) if near and _km(la, lo, *land._latlon(near)) < 80 else None

    def read_series(self, lat: float, lon: float, what: str, months: list | None = None) -> dict:
        hit = self._cell(lat, lon)
        if not hit:
            return {"error": "outside the analysed regions"}
        rk, key, res = hit
        if what in res["series"]:
            if months:
                return {"error": f"{what} is a yearly indicator; months apply to the NASA POWER variables "
                                 + ", ".join(land.PARAMS)}
            years, vals = res["years"], res["series"][what][key]
            label = f"{res['indicators'][what]['label']} ({res['indicators'][what]['units']})"
            pairs = [(y, v) for y, v in zip(years, vals) if v is not None]
        elif what in land.PARAMS:
            series = self._power_series(rk, res, key, what)
            if not series:
                return {"error": f"{what} is not cached for this place"}
            ms = sorted({int(m) for m in (months or range(1, 13))})
            if any(m < 1 or m > 12 for m in ms):
                return {"error": "months are 1 to 12"}
            means = stats.seasonal_annual_means(series, ms)
            pairs = sorted((int(y), float(v)) for y, v in means.items())
            label = land.PARAMS[what] + (" averaged over " + "-".join(MONTHS[m - 1] for m in ms) if len(ms) < 12 else "")
        else:
            return {"error": f"unknown series {what!r}", "yearly_indicators": list(res["series"]),
                    "monthly_variables": land.PARAMS}
        if len(pairs) < 10:
            return {"error": "fewer than 10 years of values"}
        ys, vs = [p[0] for p in pairs], [p[1] for p in pairs]
        tr = land.trend(ys, vs)
        from .dynamics import annual as eva_annual
        d = eva_annual({"annual": {"years": ys, "values": vs}})
        ctrl = land._control_rate(ys, vs, 20, seed=int(abs(lat * 1000 + lon * 7))) if d and len(d["dynamics"]) > 1 else None
        out = {"region": rk, "cell": {"lat": res["cells"][key]["lat"], "lon": res["cells"][key]["lon"]},
               "series": label, "years": [ys[0], ys[-1]],
               "values": {str(y): _r(v) for y, v in zip(ys, vs)},
               "classical_trend": _r({k: tr[k] for k in ("per_decade", "ci", "p_mk", "p_t", "level", "direction",
                                                         "total", "base_mean")}) if tr else None}
        if d:
            out["eva"] = _r({"reading": d["text"], "dynamics": d["dynamics"], "transitions": d["transitions"],
                             "transitions_near_merra2_seams": self._seams(d["transitions"]),
                             "control_false_change_rate": ctrl,
                             "how_to_read_control": "share of 20 series with a steady trend and the same noise "
                                                    "where she still reads a change; high = do not trust the change"})
        return out

    # -- 6
    def _scars_near(self, rk: str, lat: float, lon: float, km: float) -> list | None:
        f = SCARS / f"{rk}_scars.json"
        if not f.exists():
            return None
        d = json.loads(f.read_text())
        return [p for p in d.get("patches", []) if _km(lat, lon, p["lat"], p["lon"]) <= km]

    def bare_ground(self, lat: float | None = None, lon: float | None = None, radius_km: float | None = None,
                    region: str | None = None) -> dict:
        rk, res = self._region(region)
        if lat is not None and lon is not None:
            hit = self._cell(lat, lon)
            if hit:
                rk = hit[0]
        f = SCARS / f"{rk}_scars.json"
        if not f.exists():
            return {"error": "the bare-ground reading has not been run for this region (python -m detective.scars)"}
        d = json.loads(f.read_text())
        ps = d.get("patches", [])
        if lat is not None and lon is not None:
            rad = radius_km or 50
            ps = sorted((dict(p, km=round(_km(lat, lon, p["lat"], p["lon"]))) for p in ps
                         if _km(lat, lon, p["lat"], p["lon"]) <= rad), key=lambda p: p["km"])
        else:
            ps = sorted(ps, key=lambda p: -p.get("area_km2", 0))
        for p in ps[:12]:
            p.setdefault("near", self._nearest_town(p["lat"], p["lon"]))
        return {"region": rk, "method": d.get("method"), "validation": d.get("validation"),
                "cannot_see": d.get("cannot_see"), "count": len(ps), "patches": _r(ps[:12])}


    # -- 7: beyond the map: choose the data, import it once, let Eva read it
    def _place(self, text: str) -> dict:
        """A region key, a box 'south,north,west,east', a point 'lat,lon' or a town name."""
        from .regions import REGIONS, Region
        t = (text or "").strip()
        regs = self.regions()
        if t in regs:
            r = regs[t]["region"]
            return {"kind": "box", "name": r["name"], "key": t,
                    "region": Region(t, r["name"], r["south"], r["north"], r["west"], r["east"],
                                     country=r.get("country", ""))}
        if t.lower() in REGIONS:
            r = REGIONS[t.lower()]
            return {"kind": "box", "name": r.name, "key": r.key, "region": r}
        try:
            parts = [float(x) for x in t.replace(";", ",").split(",")]
        except ValueError:
            parts = []
        if len(parts) == 2 and -90 <= parts[0] <= 90 and -180 <= parts[1] <= 180:
            near = self._nearest_town(*parts)
            name = f"{parts[0]:.2f}, {parts[1]:.2f}" + (f" (near {near['name']})" if near and near["km"] < 60 else "")
            return {"kind": "point", "name": name, "key": f"{parts[0]:.3f},{parts[1]:.3f}",
                    "lat": parts[0], "lon": parts[1]}
        if len(parts) == 4:
            s_, n_, w_, e_ = parts
            if not (-90 <= s_ < n_ <= 90 and -180 <= w_ < e_ <= 180):
                raise ValueError("a box is south,north,west,east with south < north and west < east")
            name = f"box {s_:g}..{n_:g}°N, {w_:g}..{e_:g}°E"
            return {"kind": "box", "name": name, "key": name, "region": Region("box", name, s_, n_, w_, e_)}
        f = self.find_place(t)
        if f.get("found"):
            p0 = f["found"][0]
            return {"kind": "point", "name": p0["name"], "key": p0["name"], "lat": p0["lat"], "lon": p0["lon"]}
        raise ValueError(f"unknown place {text!r}: give a region key, 'lat,lon', 'south,north,west,east' or a town")

    @staticmethod
    def _variable(var: str) -> dict:
        from .variables import VARIABLES
        if var == "IMERG_PRECTOT":
            return {"key": var, "label": "Rain seen by satellite (GPM IMERG)", "units": "mm/day", "scale": 1.0,
                    "first_year": 2001, "source": "imerg"}
        if var in VARIABLES:
            v = VARIABLES[var]
            return {"key": var, "label": v.label, "units": v.units, "scale": v.scale, "first_year": v.first_year,
                    "source": "power"}
        if var in land.PARAMS:
            label, _, units = land.PARAMS[var].partition(" (")
            return {"key": var, "label": label, "units": units.split(")")[0] if units else "", "scale": 1.0,
                    "first_year": 2001 if var in land.OTHER_GRID else land.FIRST, "source": "power"}
        raise ValueError(f"unknown variable {var!r}: see data_catalog")

    def _series(self, var: str, place: dict, download: bool = True) -> tuple[dict, dict]:
        """The monthly series of a variable at a place (a box: the area-weighted mean of its cells
        where the variable moves), through the store; and what the store did."""
        from . import power
        v = self._variable(var)
        if v["source"] == "imerg":
            if place["kind"] != "point":
                raise ValueError("satellite rain (IMERG) is read at a point here: give 'lat,lon' or a town")
            return self.store.imerg(place["lat"], place["lon"])
        if place["kind"] == "point":
            cells = [datastore.cell_of(var, place["lat"], place["lon"])]
        else:
            r = place["region"]
            cells = datastore.cells_in_box(var, r.south, r.north, r.west, r.east)
        rows, rep_ = self.store.power(var, cells, download=download)
        if place["kind"] == "box" and place["region"].country and var not in land.OTHER_GRID and rows:
            rows = land.in_country(place["region"], {land.MASK: rows})[land.MASK]
        cs = power.informative([(*land._latlon(k), sr) for k, sr in rows.items()])
        if not cs:
            return {}, {**rep_, "note": "no cell where this variable moves (or none in the store)"}
        series = power.area_mean(cs) if len(cs) > 1 else cs[0][2]
        sc = v["scale"]
        return {k: (x * sc if x is not None else None) for k, x in series.items()}, {**rep_, "cells_used": len(cs)}

    def _focus(self, pl: dict) -> list:
        if pl["kind"] == "point":
            return [{"lat": pl["lat"], "lon": pl["lon"]}]
        r = pl["region"]
        return [{"lat": (r.south + r.north) / 2, "lon": (r.west + r.east) / 2}]

    def data_catalog(self, query: str | None = None) -> dict:
        from .regions import REGIONS
        from .variables import VARIABLES
        q = _fold(query or "")
        vs = {k: f"{v.label} ({v.units}), from {v.first_year}" for k, v in VARIABLES.items()}
        for k, t in land.PARAMS.items():
            vs.setdefault(k, t)
        vs["IMERG_PRECTOT"] = "rain seen by satellite (GPM IMERG, mm/day), from 2001, at a point only"
        if q:
            vs = {k: t for k, t in vs.items() if q in _fold(k + " " + t)} or vs
        return {"sources": {
                    "power": "NASA POWER: MERRA-2 reanalysis (and CERES for sunlight, cloud, albedo), monthly "
                             "1981-2025, grid cells of 0.5 x 0.625 degrees, over a region or at a point",
                    "imerg": "GPM IMERG satellite rain, monthly 2001-2025, at a point (0.1 degree pixel)",
                    "modis_npp": "MODIS plant productivity, yearly 2001-2025, 5 km around a point",
                    "modis_cover": "MODIS land cover (cropland, forest, savanna, water, bare) in 2001 and 2024, "
                                   "5 km around a point"},
                "variables": vs,
                "places": {"analysed_regions": {k: r["region"]["name"] for k, r in self.regions().items()},
                           "named_regions": {k: r.name for k, r in REGIONS.items()},
                           "also": "'lat,lon', 'south,north,west,east' (at most about 20 x 20 degrees) or a town"},
                "store": self.store.summary(),
                "rule": "every data set is downloaded once and kept; asking again reads the store"}

    def import_data(self, source: str, variables: list | None, place: str) -> dict:
        pl = self._place(place)
        out = {"place": pl["name"], "reports": []}
        if source == "power":
            if not variables:
                return {"error": "name the NASA POWER variables to import (see data_catalog)"}
            for var in variables[:4]:
                if self._variable(var)["source"] != "power":
                    out["reports"].append({"variable": var, "error": "not a NASA POWER variable"})
                    continue
                try:
                    _s, r = self._series(var, pl)
                except datastore.GuardError as e:
                    r = {"variable": var, "refused": [str(e)]}
                out["reports"].append(r)
        elif source in ("imerg", "modis_npp", "modis_cover"):
            if pl["kind"] != "point":
                return {"error": f"{source} is read at a point here: give 'lat,lon' or a town"}
            try:
                if source == "imerg":
                    data, r = self.store.imerg(pl["lat"], pl["lon"])
                    r["months"] = sum(v is not None for v in data.values())
                else:
                    data, r = self.store.modis("npp" if source == "modis_npp" else "cover", pl["lat"], pl["lon"])
                    r["values"] = _r(data)
            except datastore.GuardError as e:
                r = {"refused": [str(e)]}
            out["reports"].append(r)
        else:
            return {"error": "source is power, imerg, modis_npp or modis_cover"}
        out["focus"] = self._focus(pl)
        out["downloads_left_this_hour"] = self.store.budget_left()
        return out

    def eva_trend(self, variable: str, places: list, months: list | None = None) -> dict:
        from .dynamics import annual as eva_annual
        if not places:
            return {"error": "give one place or more"}
        ms = sorted({int(m) for m in (months or range(1, 13))})
        if any(m < 1 or m > 12 for m in ms):
            return {"error": "months are 1 to 12"}
        v = self._variable(variable)
        out = {"variable": v["label"], "units": v["units"],
               "months": "all" if len(ms) == 12 else "-".join(MONTHS[m - 1] for m in ms), "places": [], "focus": []}
        for text in list(dict.fromkeys(places))[:4]:
            try:
                pl = self._place(text)
                series, rep_ = self._series(variable, pl)
            except (ValueError, datastore.GuardError) as e:
                out["places"].append({"place": text, "error": str(e)})
                continue
            means = stats.seasonal_annual_means(series, ms)
            pairs = sorted((int(y), float(x)) for y, x in means.items())
            row = {"place": pl["name"], "data": rep_}
            if len(pairs) < 10:
                row["error"] = "fewer than 10 years of values"
                out["places"].append(row)
                continue
            ys, vs = [q[0] for q in pairs], [q[1] for q in pairs]
            tr = land.trend(ys, vs)
            d = eva_annual({"annual": {"years": ys, "values": vs}})
            ctrl = land._control_rate(ys, vs, 20, seed=len(out["places"])) if d and len(d["dynamics"]) > 1 else None
            row.update({"years": [ys[0], ys[-1]],
                        "classical_trend": _r({k: tr[k] for k in ("per_decade", "ci", "p_mk", "p_t", "level",
                                                                  "direction", "total", "base_mean")}) if tr else None})
            if d:
                row["eva"] = _r({"reading": d["text"], "dynamics": d["dynamics"], "transitions": d["transitions"],
                                 "transitions_near_merra2_seams": self._seams(d["transitions"])
                                 if v["source"] == "power" else [],
                                 "control_false_change_rate": ctrl})
            out["places"].append(row)
            out["focus"] += self._focus(pl)
        return out

    def eva_links(self, variables: list, places: list) -> dict:
        """Which of the chosen variables leave their norm together, which way, and which comes first:
        Eva's heatmaps (detective/heat.py) at the extreme grain, the detective's own reading."""
        from .heat import same_process
        from .variables import model_note
        from .watch import EXTREME_CUTS, Watch
        variables, places = list(dict.fromkeys(variables or []))[:6], list(dict.fromkeys(places or []))[:3]
        if len(variables) * len(places) < 2:
            return {"error": "Eva needs two series at least: two variables, or one variable at two places"}
        if len(variables) * len(places) > 8:
            return {"error": "at most 8 series (variables x places) at once"}
        multi = len(places) > 1
        series, labels, units, reports, focus = {}, {}, {}, [], []
        for text in places:
            pl = self._place(text)
            focus += self._focus(pl)
            for var in variables:
                v = self._variable(var)
                if v["first_year"] > 1981:
                    return {"error": f"{var} starts in {v['first_year']}: Eva learns her norm on 1981-2010, "
                                     "choose variables measured since 1981"}
                try:
                    s_, rep_ = self._series(var, pl)
                except datastore.GuardError as e:
                    return {"error": str(e)}
                reports.append(rep_)
                if not s_:
                    return {"error": f"no data for {var} at {pl['name']}", "data": reports}
                u = f"{var}@{pl['key']}" if multi else var
                series[u] = s_
                labels[u] = f"{v['label']} ({pl['name']})" if multi else v["label"]
                units[u] = {"variable": var, "region": pl["key"]}
        res = Watch(series, (1981, 2010), labels=labels, cuts=EXTREME_CUTS).run()
        heat = res.get("couplings") or {"links": []}
        links = []
        for x in heat["links"][:12]:
            a, b = (units[m]["variable"] for m in x["members"])
            links.append(_r({"between": x["labels"], "level": x["level"], "lag_months": x["lag"],
                             "same_or_opposite": "same way" if x["sign"] > 0 else "opposite ways",
                             "one_dynamic_union": x["union"], "p": x["p"],
                             "z_against_moved_years": x["z_persistence"], "text": x["text"],
                             "model_note": model_note(a, b)}))
        out = {"series": [labels[u] for u in series], "tested_pairs_x_transformations": heat.get("readings"),
               "links": links, "no_link_found": not links, "data": reports, "focus": focus,
               "how_to_read": "a link says the same months push both out of their norm (beyond chance at the same "
                              "moment, and against the same reading with one series moved 1-5 years); it is not "
                              "a cause. A union means Eva takes the two for one dynamic."}
        if multi:
            out["same_process_in_several_places"] = [_r(q) for q in same_process(heat["links"], units)][:6]
        return out

    def find_nasa_datasets(self, words: str, place: str | None = None) -> dict:
        from .investigate import discover
        from .mcp import EarthdataMCP
        from .regions import parse_region
        pl = self._place(place) if place else None
        if pl is None:
            region = parse_region("cameroon_full")
        elif pl["kind"] == "point":
            region = parse_region(f"{pl['lat']},{pl['lon']}")
        else:
            region = pl["region"]
        d = discover(EarthdataMCP(), (words or "")[:120], region, 1981, 2025, n_keywords=2, n_collections=5)
        cols = {k: [{f: c.get(f) for f in ("short_name", "title", "platforms", "instruments", "start", "end",
                                             "spatial_resolution")} for c in v] for k, v in d["collections"].items()}
        return {"keywords": d["keywords"], "collections": cols, "errors": d["errors"][:2],
                "importable_here": "only NASA POWER (MERRA-2, CERES, IMERG) and MODIS through the ORNL DAAC: the "
                                   "others need an Earthdata login this server does not have"}

    # -- dispatch
    def run(self, name: str, args: dict) -> dict:
        fn = {"find_place": self.find_place, "place_report": self.place_report,
              "region_overview": self.region_overview, "rank_places": self.rank_places,
              "read_series": self.read_series, "bare_ground": self.bare_ground,
              "data_catalog": self.data_catalog, "import_data": self.import_data, "eva_trend": self.eva_trend,
              "eva_links": self.eva_links, "find_nasa_datasets": self.find_nasa_datasets}.get(name)
        if not fn:
            return {"error": f"unknown tool {name}"}
        args = {k: v for k, v in (args or {}).items() if v is not None}
        return fn(**args)


def _nullable(t: str, **kw) -> dict:
    return {"type": [t, "null"], **kw}


TOOLS = [
    {"name": "find_place", "strict": True,
     "description": "Find a town or village by name (accents and case do not matter). Returns its coordinates, "
                    "country, and whether the land map covers it. Use it before place_report when the person "
                    "names a place.",
     "input_schema": {"type": "object", "additionalProperties": False, "required": ["name"],
                      "properties": {"name": {"type": "string", "description": "the place name as the person wrote it"}}}},
    {"name": "place_report", "strict": True,
     "description": "Everything the land analysis knows about the grid cell (about 55 x 70 km) under a point: for "
                    "each indicator its trend since 1981 and how sure it is, Eva's dynamics (when the trend "
                    "changed) and her control, whether her transitions fall on MERRA-2 production seams, what "
                    "satellite rain (GPM IMERG) and plants (MODIS) say, the forecast for 2026-2035, land cover, "
                    "the main drivers (rain vs evaporation). Indicators: lgp (growing season, days), rain, "
                    "soil_root, soil_top, aridity, surface_temp, pet, erosivity, wind_erosion, albedo, "
                    "evaporation, npp. Default: lgp, rain, soil_root, aridity, surface_temp, npp.",
     "input_schema": {"type": "object", "additionalProperties": False, "required": ["lat", "lon", "indicators"],
                      "properties": {"lat": {"type": "number"}, "lon": {"type": "number"},
                                     "indicators": _nullable("array", items={"type": "string"},
                                                             description="indicator keys, or null for the default set")}}},
    {"name": "region_overview", "strict": True,
     "description": "What holds over a whole analysed region: how many cells changed per indicator against chance, "
                    "the changes many cells made together, Eva's transitions near the MERRA-2 seams, the borders "
                    "where trends reverse, the cross-check with satellite rain and plants, and the forecast test. "
                    "Region null = the main (country) region; 'all' = every analysed region at once.",
     "input_schema": {"type": "object", "additionalProperties": False, "required": ["region"],
                      "properties": {"region": _nullable("string")}}},
    {"name": "rank_places", "strict": True,
     "description": "Where an indicator changed the most: 'worse' or 'better' (only trends that passed the tests), "
                    "or 'eva_changed' (cells where Eva reads a change of dynamic; only lgp, aridity, soil_root, "
                    "surface_temp). Returns places with the nearest town. Region null = the main region, 'all' = "
                    "every analysed region at once (a cell they share is kept once).",
     "input_schema": {"type": "object", "additionalProperties": False, "required": ["indicator", "which", "region", "n"],
                      "properties": {"indicator": {"type": "string"},
                                     "which": {"type": "string", "enum": ["worse", "better", "eva_changed"]},
                                     "region": _nullable("string"), "n": _nullable("integer")}}},
    {"name": "read_series", "strict": True,
     "description": "A fresh reading of one series at one place, with the classical trend AND Eva's dynamics and "
                    "her own control (how often she would see a change in a series that has none). 'what' is a "
                    "yearly indicator key (lgp, rain, soil_root, soil_top, aridity, surface_temp, pet, erosivity, "
                    "wind_erosion, albedo, evaporation, npp) or a monthly NASA POWER variable (PRECTOTCORR rain "
                    "mm/day, GWETROOT root-zone soil wetness, GWETTOP surface soil wetness, TS surface "
                    "temperature, T2M air temperature, T2M_MAX_AVG, T2M_MIN_AVG, WS2M wind, ALLSKY_SRF_ALB albedo, "
                    "EVLAND land evaporation). For a POWER variable, 'months' (1-12) restricts each year to those "
                    "months, e.g. [6,7,8,9] for the June-September rains; [12,1,2] puts December with the next "
                    "year's January-February.",
     "input_schema": {"type": "object", "additionalProperties": False, "required": ["lat", "lon", "what", "months"],
                      "properties": {"lat": {"type": "number"}, "lon": {"type": "number"}, "what": {"type": "string"},
                                     "months": _nullable("array", items={"type": "integer"})}}},
    {"name": "bare_ground", "strict": True,
     "description": "Patches where vegetation gave way to bare ground since 2001 (MODIS land cover and plant "
                    "productivity, 500 m): the trace open-pit and artisanal mines and quarries leave, but also "
                    "towns, roads, burnt or flooded land. Each patch says when it opened and what grew there "
                    "before, and the result says how the method was checked against mapped mines. With lat/lon: "
                    "the patches within radius_km (default 50); without: the largest ones in the region.",
     "input_schema": {"type": "object", "additionalProperties": False, "required": ["lat", "lon", "radius_km", "region"],
                      "properties": {"lat": _nullable("number"), "lon": _nullable("number"),
                                     "radius_km": _nullable("number"), "region": _nullable("string")}}},
    {"name": "data_catalog", "strict": True,
     "description": "What can be used beyond the map: the NASA sources this server can import without a login, the "
                    "variables (keys to pass to the other tools), the places (analysed regions, named regions, "
                    "boxes, points, towns), what is already in the store and how many downloads are left this "
                    "hour. 'query' filters the variables (e.g. 'soil', 'cloud'); null lists them all.",
     "input_schema": {"type": "object", "additionalProperties": False, "required": ["query"],
                      "properties": {"query": _nullable("string")}}},
    {"name": "import_data", "strict": True,
     "description": "Import NASA data the map does not have, into the store. Each data set (a variable at a grid "
                    "cell, a satellite pixel, a MODIS window) is downloaded ONCE: what is already there is read "
                    "from the store, and the result says what was new. Slow (up to a minute per variable and "
                    "area) and limited per hour: import only what the question needs. source 'power' takes up to "
                    "4 variables over a place; 'imerg', 'modis_npp', 'modis_cover' take a point (lat,lon or a "
                    "town). eva_trend and eva_links import by themselves when needed.",
     "input_schema": {"type": "object", "additionalProperties": False, "required": ["source", "variables", "place"],
                      "properties": {"source": {"type": "string", "enum": ["power", "imerg", "modis_npp", "modis_cover"]},
                                     "variables": _nullable("array", items={"type": "string"}),
                                     "place": {"type": "string"}}}},
    {"name": "eva_trend", "strict": True,
     "description": "One variable you choose, at one to four places at once (to compare regions): the classical "
                    "trend since 1981 (or 2001) and Eva's dynamics, when the trend changed, with her own control. "
                    "A place is a region key, 'lat,lon', 'south,north,west,east' or a town; a region is the mean "
                    "of its cells. 'months' (1-12) keeps only those months of each year ([6,7,8,9] = the June-"
                    "September rains; [12,1,2] puts December with the next year). Data come from the store "
                    "(imported once if missing).",
     "input_schema": {"type": "object", "additionalProperties": False, "required": ["variable", "places", "months"],
                      "properties": {"variable": {"type": "string"},
                                     "places": {"type": "array", "items": {"type": "string"}},
                                     "months": _nullable("array", items={"type": "integer"})}}},
    {"name": "eva_links", "strict": True,
     "description": "Let Eva find how the variables you choose are linked: which ones leave their norm in the same "
                    "months, the same or opposite way, which comes first (up to 3 months ahead), and which are so "
                    "often together that she takes them for one dynamic. Several places at once also show the "
                    "same link at work in each (one process). Up to 6 variables and 3 places, 8 series in all, "
                    "variables measured since 1981. Choose variables that could plausibly be linked to the "
                    "question; Eva decides what is linked, not you. Takes some seconds of computing.",
     "input_schema": {"type": "object", "additionalProperties": False, "required": ["variables", "places"],
                      "properties": {"variables": {"type": "array", "items": {"type": "string"}},
                                     "places": {"type": "array", "items": {"type": "string"}}}}},
    {"name": "find_nasa_datasets", "strict": True,
     "description": "Search NASA's catalogue (earthdata-mcp) for the data sets that measure something over a place "
                    "(e.g. 'soil moisture', 'vegetation index'): keywords, missions, instruments, dates. Most need "
                    "a login this server does not have: the result says which ones can be imported here.",
     "input_schema": {"type": "object", "additionalProperties": False, "required": ["words", "place"],
                      "properties": {"words": {"type": "string"}, "place": _nullable("string")}}},
]

SYSTEM = """You are Eva's voice on a public map of how the land is changing (NASA Space Apps 2026). The people asking are farmers, students, officials, investors: not scientists. Answer in the language they write in (French or English most often).

What lies behind the map: monthly NASA data since 1981 (MERRA-2 reanalysis and CERES through NASA POWER; GPM IMERG satellite rain since 2001; MODIS plant productivity and land cover since 2001), turned into yearly indicators per grid cell of about 55 x 70 km (growing season in days, aridity, root-zone soil water, surface temperature, rain, erosion...). Two readers looked at every cell:
- the classical tests: Sen's slope per decade, Mann-Kendall and a t-test corrected for persistence; a trend is "detected" only when both agree and it survives a false discovery control over the whole map;
- Eva, a learning system that reads WHEN a trend changed (her "dynamics" and the "transitions" between them), checked against her own control: how often she would see a change in a series with none.

How to answer:
1. Never give a number, a place or a trend from memory: call the tools, and say only what they return. If the tools do not cover the question, say so plainly.
2. Explain the phenomenon in plain words: what changed, since when, by how much (in days, mm, °C, with a comparison a person feels), how sure the analysis is, and why it may be happening (the drivers: rain against evaporation, heat). Then what it means for someone who farms, builds or invests there.
3. Say how sure: "detected" vs "a lead" vs "could be chance". When Eva's transitions fall on a MERRA-2 seam (1991/92, 2000/01, 2010/11), or the satellite rain disagrees, or the plants do not show it, say it may come from the data, not the land. Her control rate above about 0.3 means her change is not to be trusted at that place.
4. Mines and minerals: the bare_ground tool finds where vegetation gave way to bare ground, which is the trace of open-pit and artisanal mines and quarries, but also of towns, roads, fire or water. Present those patches as candidates to check, never as confirmed mines. Rare earths and any deposit underground cannot be seen in this data (climate, rain, plants, land cover): say so, and that finding them needs geological maps or a mineral-mapping instrument such as NASA EMIT or ASTER.
5. Be short: at most about 180 words unless asked for more, short paragraphs or a few bullet points, no tables, no em dashes. End with one thing to look at on the map when it helps (the page will fly to the places you used).
6. You read the land; you do not give financial, legal or medical advice.

Going beyond the map (data_catalog, import_data, eva_trend, eva_links, find_nasa_datasets):
7. First use what the map already holds. When the question needs another variable, another place, another season or a comparison of regions, choose the data yourself: the variables that could plausibly matter (say briefly why you chose them), the place or places (an analysed region, another named region, a box, a point, a town; several at once to compare). eva_trend reads one variable at up to four places; eva_links lets Eva find how the chosen variables are linked.
8. Imports are slow and limited, and every data set is downloaded only once: the store answers when it already has it. Never import the same thing twice on purpose. Keep areas small (a region of a few degrees, or a point).
9. A link Eva finds is not a cause: say it plainly. When a link joins two variables of the same reanalysis, say the model itself may make it (model_note). A union means she takes two series for one dynamic: count it as one piece of evidence, not two."""


# ------------------------------------------------------------------ the loop
class Agent:
    def __init__(self, tools: LandTools | None = None, client=None):
        self.tools = tools or LandTools()
        self._client = client

    def client(self):
        if self._client is None:
            if not available():
                raise RuntimeError("the assistant is not set up on this server (no API key)")
            import anthropic
            self._client = anthropic.Anthropic()
        return self._client

    def ask(self, question: str, history: list | None = None) -> dict:
        """One question (with the earlier text turns) -> {"text", "focus", "tools"}."""
        import anthropic
        question = (question or "").strip()[:MAX_QUESTION]
        if not question:
            raise ValueError("ask a question")
        messages = []
        for t in (history or [])[-MAX_TURNS:]:
            role, text = t.get("role"), str(t.get("text", ""))[:4000]
            if role in ("user", "assistant") and text and (not messages or messages[-1]["role"] != role):
                messages.append({"role": role, "content": text})
        if messages and messages[0]["role"] != "user":
            messages = messages[1:]
        if messages and messages[-1]["role"] == "user":
            messages = messages[:-1]
        messages.append({"role": "user", "content": question})
        focus, used = [], []
        for _step in range(MAX_STEPS):
            try:
                resp = self.client().beta.messages.create(
                    model=MODEL, max_tokens=MAX_TOKENS, system=SYSTEM, tools=TOOLS, messages=messages,
                    output_config={"effort": EFFORT}, cache_control={"type": "ephemeral"},
                    betas=["server-side-fallback-2026-07-01"], fallbacks="default")
            except anthropic.AuthenticationError as e:
                raise RuntimeError("the assistant has no valid API key on this server") from e
            except anthropic.RateLimitError as e:
                raise RuntimeError("the assistant is busy, try again in a minute") from e
            except anthropic.APIConnectionError as e:
                raise RuntimeError("the assistant cannot reach its model right now") from e
            except anthropic.APIStatusError as e:
                raise RuntimeError(f"the model answered with an error ({e.status_code}), try again later") from e
            except anthropic.AnthropicError as e:  # e.g. no key at all: the client cannot be built
                raise RuntimeError("the assistant is not set up on this server (no API key)") from e
            if resp.stop_reason == "refusal":
                return {"text": "I can't help with that one. Ask me about how the land, the rains or the "
                                "ground cover are changing somewhere on the map.", "focus": focus, "tools": used}
            if resp.stop_reason == "pause_turn":
                messages.append({"role": "assistant", "content": resp.content})
                continue
            calls = [b for b in resp.content if b.type == "tool_use"]
            if resp.stop_reason != "tool_use" or not calls:
                text = "\n".join(b.text for b in resp.content if b.type == "text").strip()
                if resp.stop_reason == "max_tokens":
                    text += "\n\n(answer cut short)"
                return {"text": text, "focus": _dedupe(focus), "tools": used}
            messages.append({"role": "assistant", "content": resp.content})
            results = []
            for b in calls:
                try:
                    out = self.tools.run(b.name, dict(b.input) if isinstance(b.input, dict) else {})
                    err = "error" in out
                except Exception as e:  # noqa: BLE001 - give the model the failure, not a crash
                    out, err = {"error": f"{type(e).__name__}: {e}"}, True
                used.append(b.name)
                focus += _places(b.name, out)
                results.append({"type": "tool_result", "tool_use_id": b.id,
                                "content": json.dumps(out, ensure_ascii=False), **({"is_error": True} if err else {})})
            messages.append({"role": "user", "content": results})
        return {"text": "I needed too many steps for this question; try asking about one place or one thing at a time.",
                "focus": _dedupe(focus), "tools": used}


def _places(tool: str, out: dict) -> list:
    """The places a tool result talks about, for the map to fly to."""
    if not isinstance(out, dict) or "error" in out:
        return []
    if tool in ("place_report", "read_series") and out.get("cell"):
        return [{"lat": out["cell"]["lat"], "lon": out["cell"]["lon"], "region": out.get("region"), "kind": "cell"}]
    if tool == "rank_places":
        return [{"lat": p["lat"], "lon": p["lon"], "region": out.get("region"), "kind": "cell"} for p in out["places"]]
    if tool == "bare_ground":
        return [{"lat": p["lat"], "lon": p["lon"], "region": out.get("region"), "kind": "bare"} for p in out["patches"]]
    if tool in ("import_data", "eva_trend", "eva_links"):
        return [{"lat": q["lat"], "lon": q["lon"], "region": None, "kind": "place"} for q in out.get("focus", [])]
    if tool == "find_place":
        return [{"lat": p["lat"], "lon": p["lon"], "region": p.get("region"), "kind": "town", "name": p["name"]}
                for p in out.get("found", [])[:1] if p.get("on_the_map")]
    return []


def _dedupe(ps: list) -> list:
    seen, out = set(), []
    for p in ps:
        k = (round(p["lat"], 3), round(p["lon"], 3), p["kind"])
        if k not in seen:
            seen.add(k)
            out.append(p)
    return out[:24]


# ------------------------------------------------------------------ the endpoint
class Limiter:
    """A few questions per visitor and per hour: the page is public and every answer costs."""

    def __init__(self, per_hour: int = 30):
        self.per_hour, self.hits, self.lock = per_hour, {}, threading.Lock()

    def allow(self, who: str) -> bool:
        now = time.time()
        with self.lock:
            h = [t for t in self.hits.get(who, []) if now - t < 3600]
            ok = len(h) < self.per_hour
            if ok:
                h.append(now)
            self.hits[who] = h
            return ok


AGENT = Agent()
LIMIT = Limiter()


def available() -> bool:
    import os
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return True
    return (Path.home() / ".config" / "anthropic").exists()


def handle(body: dict, who: str) -> tuple[int, dict]:
    """POST /api/ask: {"question": "...", "history": [{"role": "user"|"assistant", "text": "..."}]}."""
    if not LIMIT.allow(who):
        return 429, {"error": "too many questions for now; come back in a while"}
    try:
        return 200, AGENT.ask(str(body.get("question", "")), body.get("history") or [])
    except ValueError as e:
        return 400, {"error": str(e)}
    except RuntimeError as e:
        return 503, {"error": str(e)}
    except Exception as e:  # noqa: BLE001 - the page always gets an answer
        import traceback
        traceback.print_exc()
        return 500, {"error": f"internal error ({type(e).__name__})"}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, obj: dict) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _who(self) -> str:
        return (self.headers.get("X-Real-IP") or self.client_address[0]).strip()

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/").endswith("/api/ask/status"):
            self._send(200, {"agent": available(), "model": MODEL})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if not self.path.rstrip("/").endswith("/api/ask"):
            self._send(404, {"error": "not found"})
            return
        try:
            n = min(int(self.headers.get("Content-Length", "0")), 64_000)
            body = json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            self._send(400, {"error": "bad request"})
            return
        code, out = handle(body, self._who())
        self._send(code, out)

    def log_message(self, fmt, *args) -> None:
        sys.stderr.write("ask-eva: " + fmt % args + "\n")


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8766
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Ask Eva on http://127.0.0.1:{port}/api/ask  (model {MODEL}; key {'found' if available() else 'MISSING'})")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
