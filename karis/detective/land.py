"""Land intelligence: how the land's capacity to grow food changes, cell by cell.

NASA Space Apps 2026, « Be an Earth System Trend Detective! », applied to the land: where is
the soil getting drier or wetter, the growing season longer or shorter, the surface hotter,
the rain more erosive, the plants more or less productive? Which changes are real (beyond
chance, after testing hundreds of cells at once), how large, and what comes next?

The core is the science of change (detection, quantification, significance, prediction);
``budget.py`` is the application layer that spends a budget on its results.

1. Acquisition, every grid cell of a region (0.5° x 0.625°):
   NASA POWER, monthly 1981-2025 (MERRA-2 reanalysis; CERES for the albedo, from 2001):
   rain, root-zone and surface soil wetness, surface and air temperature, the averages of the
   daily maximum and minimum temperature, wind at 2 m, albedo, evaporation from land;
   MODIS (ORNL DAAC, no login): land cover 2024 at every cell, and on a subgrid the yearly net
   primary productivity 2001-2025 and the land cover of 2001, satellite measurements
   independent of the reanalysis.
2. Indicators, year by year (``indicators``): published definitions, never given to Eva
   (she reads them as numbers): the length of the growing period (FAO), the aridity index
   (UNEP), rainfall erosivity (modified Fournier index), the wind-erosion climatic factor (FAO).
3. Detection, quantification, significance (``detect``): Sen's slope per decade and its
   95 % interval, Mann-Kendall (Hamed-Rao) and the AR(1)-corrected t-test; hundreds of cells
   tested at once, so the false discovery rate is controlled across the map (Benjamini-
   Hochberg as Wilks 2016 recommends for correlated fields); the area that changed.
4. Eva (``eva.shape``, ``eva.dynamics``): her dynamics of every cell, read at the year (one
   steady dynamic, or regimes and when they changed) against her own control (a steady trend
   plus noise as persistent as the cell's), the changes of dynamic many cells make together
   (``changes.read_years``), the borders of the field where the trend reverses.
5. Prediction (``project``): 2026-2035 from her last dynamic, with its interval; checked by a
   hindcast (learn up to 2015, predict 2016-2025) against persistence, the 1981-2010 norm and
   a straight trend line, and the cells it flags against the cells that really lost.
"""

from __future__ import annotations

import argparse
import calendar
import datetime as dt
import json
import math
import random
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from scipy import stats as st

from eva.shape import Shape

from . import changes, modis, power, stats
from .dynamics import annual as eva_annual
from .investigate import clean, field_transitions
from .regions import Region, parse_region

OUT = Path(__file__).resolve().parents[1] / "data" / "earth" / "land"
FIRST, LAST = 1981, 2025
BASE = (1981, 2010)
LEARN_CUTS = (1995, 2000, 2005)  # hindcast: the forecast learns on these (up to the cut -> the ten years after)...
TEST_CUT = 2015  # ... and is tested on this one (up to 2015 -> 2016-2025), which none of them saw
HORIZON = (2026, 2035)
FDR_Q = 0.10  # Wilks (2016): q = 2 x the global level (0.05) for spatially correlated fields
RISK_P = 0.66  # a cell is flagged when its loss is « likely » (IPCC AR6 calibrated language: 66-100 %)
STREAM_JOINS = (1991.5, 2000.5, 2010.5)  # MERRA-2's production streams meet here (the detective's story too)
Z90 = 1.6449

# NASA POWER monthly parameters (MERRA-2 unless said): what each one is for
PARAMS = {
    "PRECTOTCORR": "rain (mm/day): water supply, erosivity",
    "GWETROOT": "root-zone soil wetness (0-1): the water plants drink",
    "GWETTOP": "surface soil wetness (0-1): the top 5 cm",
    "TS": "surface (skin) temperature (°C)",
    "T2M": "air temperature at 2 m (°C)",
    "T2M_MAX_AVG": "average daily maximum of the air temperature (°C): potential evaporation",
    "T2M_MIN_AVG": "average daily minimum of the air temperature (°C): potential evaporation",
    "WS2M": "wind speed at 2 m (m/s): wind erosion",
    "ALLSKY_SRF_ALB": "surface albedo (0-1, CERES, 1° grid): how much sunlight the surface reflects",
    "EVLAND": "evaporation from land (mm/day): soil, lakes and plant transpiration",
}
MASK = "GWETROOT"  # land: the cells where the root-zone wetness moves (the sea has none)
OTHER_GRID = {"ALLSKY_SRF_ALB"}  # served on CERES' 1° grid, not on MERRA-2's


@dataclass(frozen=True)
class Indicator:
    key: str
    label: str
    units: str
    simple: str  # plain-language definition
    method: str  # how it is computed, with its reference
    source: str
    good: int  # +1 more is better for rain-fed farming, -1 less is better, 0 a driver or context.
    #            Used by the story and the budget only: Eva never sees it.
    first_year: int = FIRST
    eva: bool = False  # read by Eva cell by cell (dynamics, changes of dynamic, borders)
    decimals: int = 1

    def as_dict(self) -> dict:
        return asdict(self)


_MERRA = "MERRA-2 reanalysis (NASA GMAO) via NASA POWER"
INDICATORS: dict[str, Indicator] = {i.key: i for i in [
    Indicator("lgp", "Growing season", "days",
              "How many days a year crops can grow on rain alone: days when the rain brings at least half of the "
              "water the air could evaporate, plus the days the soil keeps feeding the plants after the rains, "
              "with the air above 5 °C.",
              "FAO length of growing period (FAO 1978, GAEZ): monthly rain, potential evaporation and temperature "
              "interpolated to days; a day grows when rain >= 0.5 x potential evaporation or a 100 mm soil store "
              "still holds water", _MERRA, +1, eva=True, decimals=0),
    Indicator("aridity", "Aridity index", "",
              "Rain divided by the water the air could evaporate. Below 0.65 the land is a dryland, below 0.5 "
              "semi-arid, below 0.2 arid (UNEP).",
              "P / PET (UNEP 1992); PET by Hargreaves & Samani (1985), FAO-56 eq. 52, from the averages of the "
              "daily maximum and minimum temperature and the sunlight at the top of the atmosphere",
              _MERRA, +1, eva=True, decimals=3),
    Indicator("soil_root", "Root-zone soil wetness", "%",
              "How wet the soil is where roots drink (about the top metre): 0 % bone dry, 100 % soaked.",
              "annual mean of GWETROOT", _MERRA, +1, eva=True),
    Indicator("soil_top", "Surface soil wetness", "%",
              "How wet the top 5 cm of soil are, where seeds germinate.", "annual mean of GWETTOP", _MERRA, +1),
    Indicator("surface_temp", "Surface temperature", "°C",
              "The temperature of the ground itself. In the tropics a hotter surface means more heat stress for "
              "crops and more water lost to the air.", "annual mean of TS (skin temperature)", _MERRA, -1,
              eva=True, decimals=2),
    Indicator("rain", "Rain", "mm/year", "How much rain falls in a year.",
              "sum of the monthly PRECTOTCORR (gauge-corrected)", _MERRA, 0, decimals=0),
    Indicator("pet", "Potential evaporation", "mm/year",
              "How much water the air could pull out of a wet field in a year: the thirst of the air, which "
              "grows with heat.", "Hargreaves & Samani (1985), FAO-56 eq. 52", _MERRA, 0, decimals=0),
    Indicator("erosivity", "Rain erosivity", "mm",
              "How aggressive the rain is for bare soil: the same yearly rain is more erosive when it falls in "
              "a few heavy months.", "modified Fournier index (Arnoldus 1980): sum of monthly rain squared / "
              "annual rain", _MERRA, -1),
    Indicator("wind_erosion", "Wind erosion factor", "",
              "How strongly the climate lets the wind blow dry soil away: strong wind in months when the air "
              "is much thirstier than the rain.", "FAO (1979) climatic factor C = 1/100 x sum of u^3 x "
              "(PET - P) / PET x days, u the wind at 2 m", _MERRA, -1, decimals=2),
    Indicator("albedo", "Surface albedo", "%",
              "The share of sunlight the surface reflects: bare, dry soil is bright, dense plants are dark.",
              "annual mean of ALLSKY_SRF_ALB, nearest 1° cell", "CERES (NASA LaRC) via NASA POWER", 0,
              first_year=2001, decimals=2),
    Indicator("evaporation", "Evaporation from land", "mm/day",
              "Water rising from soil, lakes and plant leaves into the air.", "annual mean of EVLAND", _MERRA, 0,
              decimals=2),
    Indicator("npp", "Plant productivity (MODIS)", "g C/m²/year",
              "How much carbon the plants fixed in a year: how much they actually grew, seen from space.",
              "MOD17A3HGF net primary productivity, mean of the vegetated pixels within 5 km",
              "MODIS Terra (ORNL DAAC)", +1, first_year=2001, decimals=0),
]}
PREDICTED = ["lgp", "aridity", "soil_root", "soil_top", "surface_temp", "erosivity", "wind_erosion", "npp"]


def cell_key(lat: float, lon: float) -> str:
    return f"{lat:.3f},{lon:.3f}"


def _latlon(k: str) -> tuple[float, float]:
    a, b = k.split(",")
    return float(a), float(b)


# ------------------------------------------------------------------ acquisition
def fetch_power(region: Region, offline: bool = False, log=print) -> dict:
    """``{param: {cell_key: {(y, m): v}}}``: the land cells of the region (and every cell of
    the parameters served on another grid)."""
    out: dict = {}
    land = None
    for p in [MASK] + [q for q in PARAMS if q != MASK]:
        log(f"  POWER {p} over {region.name} ...")
        cells = power.monthly_cells(p, region, FIRST, LAST, offline=offline)
        if p == MASK:
            land = {cell_key(la, lo) for la, lo, _s in power.informative(cells)}
        out[p] = {cell_key(la, lo): s for la, lo, s in cells if p in OTHER_GRID or cell_key(la, lo) in land}
    return out


def land_cells(data: dict) -> list[tuple[float, float]]:
    return sorted(_latlon(k) for k in data[MASK])


MIN_SHARE = 0.25  # a region with a country keeps the cells at least this much in it (border cells count)


def in_country(region: Region, data: dict) -> dict:
    """``data`` cut to the cells of the region's country (Natural Earth borders), when it has one."""
    if not region.country:
        return data
    from .places import Places
    pl = Places(region.south, region.north, region.west, region.east)
    keys = [k for k in data[MASK]]
    lats, lons = sorted({_latlon(k)[0] for k in keys}), sorted({_latlon(k)[1] for k in keys})
    from .investigate import _step
    dlat, dlon = _step(lats), _step(lons)
    keep = {k for k in keys if any(iso == region.country and sh >= MIN_SHARE
                                   for iso, _n, sh in pl.country_shares(*_latlon(k), dlat, dlon))}
    return {p: (cells if p in OTHER_GRID else {k: v for k, v in cells.items() if k in keep}) for p, cells in data.items()}


def subgrid(points: list[tuple[float, float]], dlat: float = 0.5, dlon: float = 0.625) -> list[tuple[float, float]]:
    """Every other cell in latitude and longitude (about 1° x 1.25°): the MODIS service answers
    about 8 requests a minute, too slow for every cell; a quarter of them check the reanalysis.
    Counted on the global MERRA-2 grid, so a region and its sub-regions share the same cells."""
    return [p for p in points if round((p[0] + 90) / dlat) % 2 == 0 and round((p[1] + 180) / dlon) % 2 == 1]


def fetch_modis(points: list[tuple[float, float]], offline: bool = False, log=print, workers: int = 4) -> dict:
    """Land cover 2024 at every cell (where the croplands are), then on the subgrid NPP 2001-2025
    and land cover 2001 (how the plants grew, how the croplands spread). Offline, what is not
    cached is simply missing."""
    out: dict = {cell_key(*p): {} for p in points}
    stages = [(points, "cover", (2024,)), (subgrid(points), "npp", ()), (subgrid(points), "cover", (2001, 2024))]
    for pts, what, years in stages:
        for p, r in modis.fetch_points(pts, workers, offline, log, what=what, lc_years=years).items():
            if "error" in r:
                continue
            if what == "cover":
                out[cell_key(*p)].setdefault("cover", {}).update(r.get("cover", {}))
            else:
                out[cell_key(*p)]["npp"] = r.get("npp", {})
    return out


def fetch_imerg(points: list[tuple[float, float]], offline: bool = False, log=print) -> dict:
    """GPM IMERG monthly rain (mm/day) at each point, 2001-2025: NASA's satellite rain record,
    independent of MERRA-2 (NASA POWER serves it point by point, in UTC). ``{cell_key: {(y, m): v}}``."""
    out = {}
    for i, (la, lo) in enumerate(points):
        try:
            d = power._get("temporal/monthly/point", {
                "parameters": "IMERG_PRECTOT,PRECTOTCORR", "community": "AG", "latitude": la, "longitude": lo,
                "start": 2001, "end": LAST, "format": "JSON", "time-standard": "UTC"}, offline=offline)
        except (power.PowerError, OSError):
            continue
        s = power._months(d["properties"]["parameter"].get("IMERG_PRECTOT", {}))
        if sum(v is not None for v in s.values()) >= 12 * 20:
            out[cell_key(la, lo)] = s
        if (i + 1) % 20 == 0:
            log(f"  IMERG {i + 1}/{len(points)} points")
    return out


# ------------------------------------------------------------------- indicators
def _months() -> list[tuple[int, int]]:
    return [(y, m) for y in range(FIRST, LAST + 1) for m in range(1, 13)]


def _matrix(series_by_cell: dict, keys: list[str], months: list) -> np.ndarray:
    a = np.full((len(keys), len(months)), np.nan)
    for i, k in enumerate(keys):
        s = series_by_cell.get(k) or {}
        for j, ym in enumerate(months):
            v = s.get(ym)
            if v is not None:
                a[i, j] = v
    return a


def extraterrestrial_mm(lat, doy):
    """Sunlight at the top of the atmosphere (FAO-56 eq. 21), as mm/day of water it could evaporate."""
    phi = np.radians(lat)
    b = 2 * np.pi * np.asarray(doy, float) / 365
    dr = 1 + 0.033 * np.cos(b)
    delta = 0.409 * np.sin(b - 1.39)
    ws = np.arccos(np.clip(-np.tan(phi) * np.tan(delta), -1, 1))
    ra = 24 * 60 / np.pi * 0.0820 * dr * (ws * np.sin(phi) * np.sin(delta) + np.cos(phi) * np.cos(delta) * np.sin(ws))
    return 0.408 * ra


def growing_period(P: np.ndarray, PET: np.ndarray, T: np.ndarray, months: list, store: float = 100.0) -> np.ndarray:
    """Length of the growing period of every cell and year (FAO): the monthly means (mm/day, °C)
    interpolated to days; a day grows when the air is above 5 °C and either the rain brings at
    least half the potential evaporation or the soil store (filled by rain beyond evaporation, at
    most 100 mm) still holds water."""
    y0, y1 = months[0][0], months[-1][0]
    mid = np.array([dt.date(y, m, 1).toordinal() + (calendar.monthrange(y, m)[1] - 1) / 2 for y, m in months])
    t = np.arange(dt.date(y0, 1, 1).toordinal(), dt.date(y1, 12, 31).toordinal() + 1)
    yi = np.array([dt.date.fromordinal(int(x)).year - y0 for x in t])
    ny = y1 - y0 + 1
    out = np.full((P.shape[0], ny), np.nan)
    for i in range(P.shape[0]):
        if np.isnan(P[i]).any() or np.isnan(PET[i]).any() or np.isnan(T[i]).any():
            continue
        pd_, ed, td = np.interp(t, mid, P[i]), np.interp(t, mid, PET[i]), np.interp(t, mid, T[i])
        wet = (pd_ >= 0.5 * ed).tolist()
        net = (pd_ - ed).tolist()
        s, held = 0.0, []
        for k in range(len(net)):
            s = min(store, max(0.0, s + net[k]))
            held.append(wet[k] or s > 0.0)
        grow = np.array(held) & (td >= 5.0)
        out[i] = np.bincount(yi, weights=grow, minlength=ny)
    return out


def potential_evaporation(T, tx, tn, lat, months) -> np.ndarray:
    """Hargreaves & Samani (1985), FAO-56 eq. 52, mm/day: rows = cells, columns = ``months``."""
    days = np.array([calendar.monthrange(y, m)[1] for y, m in months], float)
    doy = np.array([dt.date(y, m, 1).timetuple().tm_yday - 1 + d / 2 for (y, m), d in zip(months, days)])
    return (0.0023 * (T + 17.8) * np.sqrt(np.clip(tx - tn, 0, None))
            * extraterrestrial_mm(np.asarray(lat)[:, None], doy[None, :]))


def water_indicators(P, PET, T, months, ws=None) -> dict:
    """The indicators made from rain (mm/day), potential evaporation (mm/day) and temperature,
    month by month -> year by year: rain, aridity, erosivity, growing season (and wind erosion
    when the wind is given). Rain from MERRA-2 or from IMERG goes through the same definitions."""
    n = P.shape[0]
    ny = len(months) // 12
    days = np.array([calendar.monthrange(y, m)[1] for y, m in months], float)
    Pm, Em = P * days, PET * days

    def yearly(a):
        return a.reshape(n, ny, 12).sum(axis=2)

    rain = yearly(Pm)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = {"rain": rain, "pet": yearly(Em), "aridity": rain / yearly(Em), "erosivity": yearly(Pm ** 2) / rain,
               "lgp": growing_period(P, PET, T, months)}
        if ws is not None:
            out["wind_erosion"] = yearly(ws ** 3 * np.clip((Em - Pm) / Em, 0, None) * days) / 100
    return out


def indicators(data: dict, keys: list[str], mod: dict | None = None) -> tuple[list[int], dict]:
    """Every indicator, every cell (rows, in ``keys`` order), every year 1981-2025 (columns; NaN
    where it does not exist)."""
    months = _months()
    years = list(range(FIRST, LAST + 1))
    n, ny = len(keys), len(years)
    M = {p: _matrix(data[p], keys, months) for p in PARAMS if p not in OTHER_GRID}
    lat = np.array([_latlon(k)[0] for k in keys])
    PET = potential_evaporation(M["T2M"], M["T2M_MAX_AVG"], M["T2M_MIN_AVG"], lat, months)

    def yearly(a):
        return a.reshape(n, ny, 12).mean(axis=2)

    out = water_indicators(M["PRECTOTCORR"], PET, M["T2M"], months, ws=M["WS2M"])
    out.update({"soil_root": 100 * yearly(M["GWETROOT"]), "soil_top": 100 * yearly(M["GWETTOP"]),
                "surface_temp": yearly(M["TS"]), "evaporation": yearly(M["EVLAND"])})
    # albedo: the nearest cell of CERES' 1° grid
    alb = data.get("ALLSKY_SRF_ALB") or {}
    a = np.full((n, ny), np.nan)
    if alb:
        pts = [(_latlon(k), k) for k in alb]
        for i, k in enumerate(keys):
            la, lo = _latlon(k)
            near = min(pts, key=lambda q: (q[0][0] - la) ** 2 + (q[0][1] - lo) ** 2)[1]
            ann = stats.annual_means(alb[near])
            for y, v in ann.items():
                a[i, y - FIRST] = 100 * v
    out["albedo"] = a
    # MODIS net primary productivity (g C / m² / year) where it was fetched
    npp = np.full((n, ny), np.nan)
    for i, k in enumerate(keys):
        for y, r in ((mod or {}).get(k, {}).get("npp") or {}).items():
            y = int(y)
            if FIRST <= y <= LAST:
                npp[i, y - FIRST] = 1000 * r["npp"]
    out["npp"] = npp
    return years, out


def cell_area_km2(lat: float, dlat: float, dlon: float) -> float:
    r = 6371.0
    return r * r * math.radians(dlon) * (math.sin(math.radians(lat + dlat / 2)) - math.sin(math.radians(lat - dlat / 2)))


# --------------------------------------------- detection, quantification, significance
def trend(years, values, base: tuple = BASE) -> dict | None:
    """One cell's trend: Sen's slope per decade and its 95 % interval, Mann-Kendall (Hamed-Rao)
    and the AR(1)-corrected t-test, how much it changed over the record, against its natural
    year-to-year spread."""
    y, v = np.asarray(years, float), np.asarray(values, float)
    ok = np.isfinite(v)
    y, v = y[ok], v[ok]
    if len(v) < 10:
        return None
    b = base if y[0] <= base[0] else (y[0], y[0] + 14)  # a record from 2001: its first 15 years
    bv = v[(y >= b[0]) & (y <= b[1])]
    out = {"n": int(len(v)), "from": int(y[0]), "to": int(y[-1]), "base_mean": float(bv.mean()),
           "base_sd": float(bv.std(ddof=1)) if len(bv) > 2 else float("nan")}
    if np.ptp(v) == 0:
        return {**out, "per_decade": 0.0, "ci": [0.0, 0.0], "p_mk": 1.0, "p_t": 1.0, "p": 1.0,
                "level": "not significant", "direction": "flat", "total": 0.0, "z": 0.0, "rel": 0.0}
    mk = stats.mann_kendall(v, True)
    o = stats.ols(y, v)
    sn = stats.sen(y, v, var_s=mk["var"])
    p_t = o["p"] if math.isfinite(o.get("p", float("nan"))) else 1.0
    vd = stats.verdict(mk["p"], p_t, sn["slope"])
    total = sn["slope"] * (y[-1] - y[0])
    sd = out["base_sd"]
    return {**out, "per_decade": 10 * sn["slope"], "ci": [10 * sn["ci"][0], 10 * sn["ci"][1]],
            "p_mk": mk["p"], "p_t": p_t, "p": max(mk["p"], p_t), "level": vd["level"], "direction": vd["direction"],
            "total": total, "z": total / sd if sd and sd > 0 else None,
            "rel": total / abs(out["base_mean"]) if out["base_mean"] else None}


def benjamini_hochberg(ps: list[float], q: float = FDR_Q) -> tuple[list[bool], float]:
    """Which of the tests survive a false discovery rate ``q`` (Benjamini & Hochberg 1995), and the
    p-value threshold that came out."""
    m = len(ps)
    if not m:
        return [], 0.0
    order = sorted(range(m), key=lambda i: ps[i])
    k_max = 0
    for rank, i in enumerate(order, 1):
        if ps[i] <= rank / m * q:
            k_max = rank
    thr = ps[order[k_max - 1]] if k_max else 0.0
    return [ps[i] <= thr and k_max > 0 for i in range(m)], thr


def detect(years: list[int], values: np.ndarray, keys: list[str], areas: dict, ind: Indicator,
           base: tuple = BASE) -> dict:
    """Every cell's trend, the false discovery rate across the map, the area that changed."""
    per = {}
    for k, row in zip(keys, values):
        t = trend(years, row, base)
        if t:
            per[k] = t
    ks = list(per)
    flags, thr = benjamini_hochberg([per[k]["p"] for k in ks])
    for k, f in zip(ks, flags):
        per[k]["fdr"] = bool(f)
        per[k]["detected"] = bool(f and per[k]["level"] == "significant")
    det = [k for k in ks if per[k]["detected"]]
    up = [k for k in det if per[k]["per_decade"] > 0]
    down = [k for k in det if per[k]["per_decade"] < 0]
    land = sum(areas[k] for k in ks)

    def worse(k):
        return ind.good != 0 and per[k]["per_decade"] * ind.good < 0

    def area(lst):
        return sum(areas[k] for k in lst)

    rates = [per[k]["per_decade"] for k in det]
    return {
        "cells": per,
        "summary": {
            "tested": len(ks), "local": sum(1 for k in ks if per[k]["level"] == "significant"),
            "expected_by_chance": 0.05 * len(ks), "detected": len(det), "p_threshold": thr, "q": FDR_Q,
            "field_significant": bool(det), "up": len(up), "down": len(down),
            "area_up_km2": area(up), "area_down_km2": area(down), "land_km2": land,
            "worse": sum(1 for k in det if worse(k)), "area_worse_km2": area([k for k in det if worse(k)]),
            "better": sum(1 for k in det if ind.good and not worse(k)),
            "area_better_km2": area([k for k in det if ind.good and not worse(k)]),
            "median_rate_detected": float(np.median(rates)) if rates else None,
            "median_rate_all": float(np.median([per[k]["per_decade"] for k in ks])) if ks else None,
        },
    }


# ---------------------------------------------------------------------- Eva
def _lag1(r) -> float:
    r = np.asarray(r, float) - np.mean(r)
    ss = float(np.sum(r * r))
    return float(np.sum(r[1:] * r[:-1]) / ss) if ss > 0 else 0.0


def _control_rate(years, values, draws: int, seed: int) -> float:
    """Eva's own control on this cell: a steady trend plus noise as persistent as the cell's, no
    change of dynamic in it; how often does she read two dynamics or more?"""
    t = np.asarray(years, float)
    v = np.asarray(values, float)
    b = stats.sen_slope(t, v)
    a = float(np.median(v - b * t))
    res = v - (a + b * t)
    phi, sd = min(max(_lag1(res), 0.0), 0.95), float(np.std(res, ddof=1))
    rng = random.Random(seed)
    hits = 0
    for _ in range(draws):
        x, ys = 0.0, []
        for tt in t:
            x = phi * x + math.sqrt(1 - phi * phi) * rng.gauss(0, sd)
            ys.append(a + b * tt + x)
        s = Shape(list(zip(t.tolist(), ys)), degree=1)
        hits += sum(1 for P in s.pieces if P.size >= 2) > 1
    return hits / draws


def eva_read(years: list[int], values: np.ndarray, keys: list[str], det: dict, draws: int = 99,
             control_draws: int = 5, log=print) -> dict:
    """Her dynamics of every cell (at the year), against her own control; the changes of dynamic
    many cells make together, against chance (``changes.read_years``); the borders of the field."""
    cells, rows, rates = {}, [], []
    for i, (k, row) in enumerate(zip(keys, values)):
        ok = np.isfinite(row)
        ys = [y for y, f in zip(years, ok) if f]
        vs = [float(x) for x, f in zip(row, ok) if f]
        if len(vs) < 15 or np.ptp(vs) == 0:
            continue
        d = eva_annual({"annual": {"years": ys, "values": vs}})
        if not d:
            continue
        rate = _control_rate(ys, vs, control_draws, seed=i) if control_draws else None
        s = Shape(list(zip(ys, vs)), degree=1)  # her lines, to draw them over the curve
        lines = [[s.xs[P.lo], s.line(P, s.xs[P.lo]), s.xs[P.hi], s.line(P, s.xs[P.hi])]
                 for P in s.pieces if P.size >= 2]
        cells[k] = {"dynamics": d["dynamics"], "transitions": d["transitions"], "persistence": d["persistence"],
                    "control": rate, "text": d["text"], "lines": lines}
        if rate is not None:
            rates.append(rate)
        if len(ys) == len(years):
            la, lo = _latlon(k)
            rows.append((la, lo, vs))
    changed = [k for k, c in cells.items() if len(c["dynamics"]) > 1]
    expected = float(sum(c["control"] or 0.0 for c in cells.values()))
    # how surprising that many changed cells would be if none changed (Poisson, cells independent:
    # neighbouring cells are not, so this is generous to the changes)
    p_changed = float(st.poisson.sf(len(changed) - 1, expected)) if expected > 0 else (0.0 if changed else 1.0)
    # MERRA-2 was made in four streams (1980, 1992, 2001, 2011): what the reanalysis assimilates can
    # jump at their joins; Eva's transitions gathered there are leads on the data, not on the land
    ts = [t for k in changed for t in cells[k]["transitions"]]
    near = sum(1 for t in ts if min(abs(t - j) for j in STREAM_JOINS) <= 1.0)
    share = len(STREAM_JOINS) * 2.0 / (years[-1] - years[0])
    out = {"cells": cells, "changed": len(changed), "read": len(cells), "expected_by_control": expected,
           "p_changed": p_changed, "transition_years": sorted(round(t) for t in ts),
           "stream_joins": {"near": near, "of": len(ts), "chance": share,
                            "p": float(st.binom.sf(near - 1, len(ts), share)) if ts else None}}
    if draws and len(rows) >= 4:
        log(f"    changes of dynamic over {len(rows)} cells ({draws} fields without change) ...")
        out["changes"] = changes.read_years(years, rows, draws=draws)
    out["borders"] = field_transitions([{"lat": _latlon(k)[0], "lon": _latlon(k)[1], "per_decade": t["per_decade"],
                                         "p": t["p"]} for k, t in det["cells"].items()])
    return out


# ------------------------------------------------------------------ prediction
def _mean_factor(phi: float, m: int) -> float:
    """Variance of the mean of m AR(1) readings, in units of sigma^2 / m."""
    if phi <= 0 or m < 2:
        return 1.0
    k = np.arange(1, m)
    return float(1 + 2 * np.sum((1 - k / m) * phi ** k))


def _predictive(xs, vs, fit_lo: int, line, tw, sigma: float, phi: float) -> tuple[float, float]:
    """Mean over the window ``tw`` of the dynamic ``line`` fitted on readings ``fit_lo``.., and its
    standard deviation: the noise of a ten-year mean (persistent) plus the uncertainty of the
    dynamic's level and slope carried forward (Santer-style inflation by (1 + phi) / (1 - phi))."""
    xp = np.asarray(xs[fit_lo:], float)
    pred = float(np.mean([line(t) for t in tw]))
    infl = (1 + phi) / (1 - phi)
    sxx = float(np.sum((xp - xp.mean()) ** 2)) or 1.0
    var = sigma ** 2 * (_mean_factor(phi, len(tw)) / len(tw)
                        + infl * (1 / len(xp) + (float(np.mean(tw)) - xp.mean()) ** 2 / sxx))
    return pred, math.sqrt(max(var, 0.0))


def _shortfall(a: float, mu: float, sd: float) -> float:
    """E[max(0, a - X)], X ~ N(mu, sd)."""
    if sd <= 0:
        return max(0.0, a - mu)
    z = (a - mu) / sd
    return (a - mu) * st.norm.cdf(z) + sd * st.norm.pdf(z)


def project(years, values, window: tuple, cut: int | None = None) -> dict | None:
    """The mean of the ``window`` years, predicted from the readings up to ``cut``: Eva's last
    dynamic carried forward (her prediction), and the baselines it must beat: a straight trend
    line over the whole record, the last five years kept as they are (persistence), the
    1981-2010 norm. ``recent`` is the mean of the last ten years known; ``p_down`` the chance the
    window falls below it, ``shortfall`` / ``excess`` the expected drop / rise beyond it."""
    pts = [(int(y), float(v)) for y, v in zip(years, values) if math.isfinite(v) and (cut is None or y <= cut)]
    if len(pts) < 12:
        return None
    xs = np.array([p[0] for p in pts], float)
    vs = np.array([p[1] for p in pts], float)
    tw = np.arange(window[0], window[1] + 1, dtype=float)
    recent = float(vs[-10:].mean())
    base = vs[(xs >= BASE[0]) & (xs <= BASE[1])]
    norm = float(base.mean()) if len(base) >= 10 else float(vs[:15].mean())
    out = {"recent": recent, "persistence": float(vs[-5:].mean()), "norm": norm}
    if np.ptp(vs) == 0:
        c = float(vs[-1])
        return {**out, "pred": c, "sd": 0.0, "line": c, "line_sd": 0.0, "p_down": 0.0, "p_up": 0.0,
                "shortfall": 0.0, "excess": 0.0, "line_p_down": 0.0, "line_p_up": 0.0, "dynamics": 1}
    s = Shape(pts, degree=1)
    ps = [P for P in s.pieces if P.size >= 2]
    last = ps[-1]
    piece_of = [None] * len(xs)
    for P in s.pieces:
        for i in range(P.lo, P.hi + 1):
            piece_of[i] = P
    r = vs - np.array([s.line(piece_of[i], xs[i]) for i in range(len(xs))])
    sigma = float(np.sqrt(np.sum(r ** 2) / max(1, len(xs) - 2 * len(ps))))
    phi = min(max(_lag1(r), 0.0), 0.9)
    pred, sd = _predictive(xs, vs, last.lo, lambda t: s.line(last, t), tw, sigma, phi)
    # the straight line over the whole record, with the same kind of interval
    b, a = np.polyfit(xs, vs, 1)
    rl = vs - (a + b * xs)
    phil = min(max(_lag1(rl), 0.0), 0.9)
    line, line_sd = _predictive(xs, vs, 0, lambda t: a + b * t, tw, float(np.sqrt(np.sum(rl ** 2) / (len(xs) - 2))),
                                phil)

    def p_below(mu, s_):
        return float(st.norm.cdf((recent - mu) / s_)) if s_ > 0 else float(mu < recent)

    return {**out, "pred": pred, "sd": sd, "line": float(line), "line_sd": line_sd,
            "p_down": p_below(pred, sd), "p_up": 1 - p_below(pred, sd),
            "line_p_down": p_below(line, line_sd), "line_p_up": 1 - p_below(line, line_sd),
            "shortfall": _shortfall(recent, pred, sd), "excess": _shortfall(-recent, -pred, sd),
            "dynamics": len(ps), "last_from": int(xs[last.lo]), "last_per_decade": 10 * s.slope(last),
            "sigma": sigma, "phi": phi}


def _rows(years: list[int], values: np.ndarray, keys: list[str], cut: int) -> list[dict]:
    """Every cell: what each method predicted for the ten years after ``cut`` from the readings up
    to it, and what happened (``obs``), with the cell's year-to-year spread up to ``cut``."""
    win = (cut + 1, cut + 10)
    rows = []
    for k, row in zip(keys, values):
        pr = project(years, row, win, cut)
        if not pr:
            continue
        obs = [v for y, v in zip(years, row) if win[0] <= y <= win[1] and math.isfinite(v)]
        known = [v for y, v in zip(years, row) if y <= cut and math.isfinite(v)]
        if len(obs) < 8 or len(known) < 10:
            continue
        sd0 = float(np.std(known, ddof=1))
        if sd0 > 0:
            rows.append({**pr, "key": k, "obs": float(np.mean(obs)), "sd0": sd0})
    return rows


def fit_blend(rows: list[dict]) -> dict:
    """What the ten years after kept of each prediction, learned on past splits: window mean =
    persistence + a (Eva - persistence) + b (norm - persistence), a, b >= 0, a + b <= 1, least
    squares in units of each cell's spread. Its interval: the 90th percentile of what it missed
    there (calibrated, not assumed)."""
    if not rows:
        return {"eva": 0.0, "norm": 0.0, "persistence": 1.0, "q90": Z90, "cells": 0}
    x1 = np.array([(r["pred"] - r["persistence"]) / r["sd0"] for r in rows])
    x2 = np.array([(r["norm"] - r["persistence"]) / r["sd0"] for r in rows])
    y = np.array([(r["obs"] - r["persistence"]) / r["sd0"] for r in rows])
    best = (float("inf"), 0.0, 0.0)
    for a in np.arange(0, 1.0001, 0.05):
        for b in np.arange(0, 1.0001 - a, 0.05):
            sse = float(np.sum((y - a * x1 - b * x2) ** 2))
            if sse < best[0]:
                best = (sse, float(a), float(b))
    _, a, b = best
    q90 = float(np.quantile(np.abs(y - a * x1 - b * x2), 0.9))
    return {"eva": a, "norm": b, "persistence": 1 - a - b, "q90": q90, "cells": len(rows)}


def blend(r: dict, w: dict) -> tuple[float, float]:
    mu = r["persistence"] + w["eva"] * (r["pred"] - r["persistence"]) + w["norm"] * (r["norm"] - r["persistence"])
    return mu, w["q90"] / Z90 * r["sd0"]


def evaluate(rows: list[dict], w: dict) -> dict:
    """Errors of every method on a split it did not learn from (units of each cell's spread), how
    often the intervals hold the truth, and the cells each method flags as going down / up (at
    least RISK_P likely) against the cells that really did (the ten years after below / above the
    ten years before)."""
    if not rows:
        return {"cells": 0}
    errs = {m: [] for m in ("blend", "eva", "line", "persistence", "norm")}
    inside = {"blend": 0, "eva": 0}
    p_bl = []
    for r in rows:
        mu, sd = blend(r, w)
        p_bl.append(float(st.norm.cdf((r["recent"] - mu) / sd)) if sd > 0 else float(mu < r["recent"]))
        for m, v in (("blend", mu), ("eva", r["pred"]), ("line", r["line"]), ("persistence", r["persistence"]),
                     ("norm", r["norm"])):
            errs[m].append(abs(v - r["obs"]) / r["sd0"])
        inside["blend"] += abs(r["obs"] - mu) <= Z90 * sd
        inside["eva"] += abs(r["obs"] - r["pred"]) <= Z90 * r["sd"] if r["sd"] > 0 else r["obs"] == r["pred"]
    n = len(rows)

    def flags(p_down: list[float], sign: int) -> dict:
        real = [(r["obs"] - r["recent"]) * sign > 0 for r in rows]
        flag = [(p if sign < 0 else 1 - p) >= RISK_P for p in p_down]
        hit = sum(1 for f, x in zip(flag, real) if f and x)
        nf, nr = sum(flag), sum(real)
        prec = hit / nf if nf else None
        return {"flagged": nf, "hits": hit, "real": nr, "precision": prec, "recall": hit / nr if nr else None,
                "base_rate": nr / n, "lift": prec / (nr / n) if prec is not None and nr else None,
                # as many cells flagged at random would hit this many or more:
                "p_vs_random": float(st.hypergeom.sf(hit - 1, n, nr, nf)) if nf else None}

    methods = {"blend": p_bl, "eva": [r["p_down"] for r in rows], "line": [r["line_p_down"] for r in rows]}
    return {
        "cells": n, "median_error": {m: float(np.median(v)) for m, v in errs.items()},
        "blend_beats": {m: float(np.mean([a < b for a, b in zip(errs["blend"], errs[m])])) for m in errs if m != "blend"},
        "eva_beats": {m: float(np.mean([a < b for a, b in zip(errs["eva"], errs[m])]))
                      for m in ("line", "persistence", "norm")},
        "coverage90": {m: c / n for m, c in inside.items()},
        "down": {m: flags(p, -1) for m, p in methods.items()},
        "up": {m: flags(p, +1) for m, p in methods.items()},
        "per_cell": {r["key"]: {"blend": mu_sd[0], "blend_sd": mu_sd[1], "eva": r["pred"], "eva_sd": r["sd"],
                                "recent": r["recent"], "obs": r["obs"], "persistence": r["persistence"],
                                "line": r["line"], "line_sd": r["line_sd"]}
                     for r, mu_sd in ((r, blend(r, w)) for r in rows)},
    }


def hindcast(years: list[int], values: np.ndarray, keys: list[str], learn_cuts: tuple = LEARN_CUTS,
             test_cut: int = TEST_CUT) -> dict:
    """Learn the blend on past decades (every cut of ``learn_cuts`` -> the ten years after, all of
    them over before the test begins), test it on ``test_cut`` -> the ten years after, which it
    never saw. All the cells of a region share each decade's swing, so a decade teaches one regional
    surprise: the more decades it learns on, the more honest its interval. The forecast uses the
    blend learned on every decade, the tested one included."""
    learn = [r for c in learn_cuts for r in _rows(years, values, keys, c)]
    test = _rows(years, values, keys, test_cut)
    w = fit_blend(learn)
    every = learn + test + [r for c in range(learn_cuts[-1] + 5, test_cut, 5) for r in _rows(years, values, keys, c)]
    return {"learn": {"cuts": list(learn_cuts), "rows": len(learn)}, "cut": test_cut,
            "window": [test_cut + 1, test_cut + 10], "weights": w, "weights_all": fit_blend(every),
            **evaluate(test, w)}


def forecast(years: list[int], values: np.ndarray, keys: list[str], w: dict, window: tuple = HORIZON) -> dict:
    """Every cell's mean over ``window``: the blend (learned by the hindcast) of Eva's last dynamic,
    persistence and the norm, its calibrated interval, the chance it ends below / above the last ten
    years and the expected drop / rise."""
    out = {}
    for k, row in zip(keys, values):
        pr = project(years, row, window)
        if not pr:
            continue
        known = [v for v in row if math.isfinite(v)]
        sd0 = float(np.std(known, ddof=1))
        mu, sd = blend({**pr, "sd0": sd0}, w) if sd0 > 0 else (pr["pred"], 0.0)
        rec = pr["recent"]
        p_down = float(st.norm.cdf((rec - mu) / sd)) if sd > 0 else float(mu < rec)
        out[k] = {"pred": mu, "sd": sd, "lo90": mu - Z90 * sd, "hi90": mu + Z90 * sd, "recent": rec,
                  "eva": pr["pred"], "eva_last_from": pr.get("last_from"), "eva_per_decade": pr.get("last_per_decade"),
                  "p_down": p_down, "p_up": 1 - p_down,
                  "shortfall": _shortfall(rec, mu, sd), "excess": _shortfall(-rec, -mu, sd)}
    return out


# ------------------------------------------------------------------ validation
def _detrend(y, v):
    b, a = np.polyfit(y, v, 1)
    return v - (a + b * y)


def replicate(keys: list[str], data: dict, im: dict) -> dict:
    """The rain-made indicators remade with the satellite's rain (GPM IMERG) instead of the
    reanalysis' (temperature, hence potential evaporation, still MERRA-2's), 2001-2025, where IMERG
    was fetched: do two NASA records tell the same changes? A cell's change is *confirmed* when both
    show a significant trend the same way, *contradicted* when they disagree on its sign and one of
    them is significant, *not confirmed* when only the reanalysis' is significant. IMERG is read at
    its 0.1° pixel at the cell's centre, MERRA-2 over the whole 0.5° cell: part of the year-to-year
    disagreement is that difference of scale."""
    sub = [k for k in keys if k in im]
    if not sub:
        return {"cells": 0}
    months = [(y, m) for y in range(2001, LAST + 1) for m in range(1, 13)]
    years = list(range(2001, LAST + 1))
    lat = np.array([_latlon(k)[0] for k in sub])
    M = {q: _matrix(data[q], sub, months) for q in ("PRECTOTCORR", "T2M", "T2M_MAX_AVG", "T2M_MIN_AVG")}
    PET = potential_evaporation(M["T2M"], M["T2M_MAX_AVG"], M["T2M_MIN_AVG"], lat, months)
    A = water_indicators(M["PRECTOTCORR"], PET, M["T2M"], months)
    B = water_indicators(_matrix(im, sub, months), PET, M["T2M"], months)
    out: dict = {"cells": len(sub), "years": [2001, LAST], "indicators": {}, "per_cell": {}}
    yr = np.asarray(years, float)
    for name in ("rain", "aridity", "lgp", "erosivity"):
        rs, pairs, status = [], [], {"confirmed": 0, "contradicted": 0, "not confirmed": 0, "satellite only": 0,
                                     "neither": 0}
        for i, k in enumerate(sub):
            a, b = A[name][i], B[name][i]
            ta, tb = trend(years, a), trend(years, b)
            if not ta or not tb:
                continue
            ok = np.isfinite(a) & np.isfinite(b)
            r = None
            if ok.sum() >= 15 and np.ptp(a[ok]) > 0 and np.ptp(b[ok]) > 0:
                r = float(np.corrcoef(_detrend(yr[ok], a[ok]), _detrend(yr[ok], b[ok]))[0, 1])
                rs.append(r)
            sa, sb = ta["level"] == "significant", tb["level"] == "significant"
            same = ta["per_decade"] * tb["per_decade"] > 0
            st_ = ("confirmed" if sa and sb and same else "contradicted" if (sa or sb) and not same
                   else "not confirmed" if sa else "satellite only" if sb else "neither")
            status[st_] += 1
            pairs.append((ta["per_decade"], tb["per_decade"]))
            out["per_cell"].setdefault(k, {})[name] = {"merra": ta["per_decade"], "imerg": tb["per_decade"],
                                                       "r": r, "status": st_}
        if not pairs:
            continue
        pa, pb = np.array([x[0] for x in pairs]), np.array([x[1] for x in pairs])
        out["indicators"][name] = {
            "cells": len(pairs), "median_r": float(np.median(rs)) if rs else None,
            "same_sign": float(np.mean(np.sign(pa) == np.sign(pb))),
            "spearman": float(st.spearmanr(pa, pb)[0]) if np.ptp(pa) > 0 and np.ptp(pb) > 0 else None,
            "median_merra": float(np.median(pa)), "median_imerg": float(np.median(pb)), "status": status}
    return out


def validate_npp(years: list[int], ind: dict, keys: list[str]) -> dict:
    """MODIS (independent of the reanalysis) against the reanalysis' water, where both exist:
    do the plants grow more in the years the soil is wetter (detrended year-to-year correlation),
    and do their trends 2001-2025 go the same way (rank correlation across cells, against the
    cells shuffled)?"""
    yrs = np.array(years)
    sel = (yrs >= 2001) & (yrs <= LAST)
    rs, slopes, n_cells = {}, {"npp": [], "soil_root": [], "lgp": [], "aridity": []}, 0
    for i, k in enumerate(keys):
        npp = ind["npp"][i][sel]
        if np.isfinite(npp).sum() < 15:
            continue
        ok = np.isfinite(npp)
        n_cells += 1
        y = yrs[sel][ok].astype(float)
        dn = _detrend(y, npp[ok])
        for other in ("soil_root", "lgp", "aridity"):
            o = ind[other][i][sel][ok]
            if np.isfinite(o).all() and np.ptp(o) > 0 and np.ptp(dn) > 0:
                rs.setdefault(other, []).append(float(np.corrcoef(dn, _detrend(y, o))[0, 1]))
        if all(np.isfinite(ind[o][i][sel][ok]).all() for o in ("soil_root", "lgp", "aridity")):
            slopes["npp"].append(stats.sen_slope(y, npp[ok]))
            for o in ("soil_root", "lgp", "aridity"):
                slopes[o].append(stats.sen_slope(y, ind[o][i][sel][ok]))
    out = {"cells": n_cells, "years": [2001, LAST], "year_to_year": {}, "trends": {}}
    for o, r in rs.items():
        pos = sum(1 for x in r if x > 0)
        out["year_to_year"][o] = {"median_r": float(np.median(r)), "positive": pos, "of": len(r),
                                  "p_sign": float(st.binomtest(pos, len(r), 0.5, alternative="greater").pvalue)}
    rng = np.random.default_rng(0)
    for o in ("soil_root", "lgp", "aridity"):
        a, b = np.array(slopes["npp"]), np.array(slopes[o])
        if len(a) < 8 or np.ptp(b) == 0:
            continue
        rho = float(st.spearmanr(a, b)[0])
        null = [st.spearmanr(a, rng.permutation(b))[0] for _ in range(999)]
        same = int(np.sum(np.sign(a) == np.sign(b)))
        out["trends"][o] = {"spearman": rho, "p_shuffled": float((1 + sum(x >= rho for x in null)) / 1000),
                            "same_direction": same, "of": len(a)}
    return out


def land_cover_change(keys: list[str], mod: dict, areas: dict) -> dict:
    """Where MODIS saw croplands spread and forests shrink, 2001 -> 2024 (subgrid cells)."""
    rows = []
    for k in keys:
        c = (mod.get(k) or {}).get("cover") or {}
        a, b = c.get(2001) or c.get("2001"), c.get(2024) or c.get("2024")
        if a and b:
            rows.append({"key": k, "cropland": b["cropland"] - a["cropland"], "forest": b["forest"] - a["forest"],
                         "cropland_2001": a["cropland"], "cropland_2024": b["cropland"]})
    if not rows:
        return {"cells": 0}
    crop = [r["cropland"] for r in rows]
    forest = [r["forest"] for r in rows]
    return {"cells": len(rows), "median_cropland_change": float(np.median(crop)),
            "cropland_up": sum(1 for x in crop if x > 0.05), "cropland_down": sum(1 for x in crop if x < -0.05),
            "forest_down": sum(1 for x in forest if x < -0.05), "forest_up": sum(1 for x in forest if x > 0.05),
            "mean_cropland_2001": float(np.mean([r["cropland_2001"] for r in rows])),
            "mean_cropland_2024": float(np.mean([r["cropland_2024"] for r in rows])),
            "per_cell": {r["key"]: r for r in rows}}


def crosscheck(res: dict, ind: str = "lgp", since: int = 2001) -> dict:
    """The cells where ``ind`` was detected changing the bad way since 1981, looked at again over the
    satellite era (``since``-2025): does the reanalysis itself still show it, does the satellite rain
    (IMERG) agree, do the plants (MODIS NPP) show it? And the region's largest 5-year steps, against
    the steps at MERRA-2's stream joins."""
    meta = INDICATORS[ind]
    years = res["years"]
    det = res["detect"][ind]["cells"]
    bad = [k for k, t in det.items() if t["detected"] and meta.good and t["per_decade"] * meta.good < 0]
    late = []
    for k in bad:
        ys = [y for y, v in zip(years, res["series"][ind][k]) if v is not None and y >= since]
        vs = [v for y, v in zip(years, res["series"][ind][k]) if v is not None and y >= since]
        t = trend(ys, vs)
        if t:
            late.append(t)
    way = meta.good or 1
    rep = (res.get("replication") or {}).get("per_cell") or {}
    sat = [rep[k][ind]["imerg"] for k in bad if ind in rep.get(k, {})]
    npp = res["detect"]["npp"]["cells"]
    plants = [npp[k]["per_decade"] for k in bad if k in npp]
    yrs = np.asarray(years)
    reg = np.nanmean(np.array([[np.nan if x is None else x for x in res["series"][ind][k]] for k in res["cells"]]), axis=0)
    steps = {int(y): float(reg[(yrs >= y) & (yrs < y + 5)].mean() - reg[(yrs >= y - 5) & (yrs < y)].mean())
             for y in range(years[0] + 5, years[-1] - 3)}
    worst = sorted(steps, key=lambda y: steps[y] * way)[:5]
    return {"indicator": ind, "since": since, "cells": len(bad),
            "reanalysis_late": {"same_way": sum(1 for t in late if t["per_decade"] * way < 0),
                                "other_way": sum(1 for t in late if t["per_decade"] * way > 0),
                                "significant_same": sum(1 for t in late if t["level"] == "significant" and t["per_decade"] * way < 0),
                                "significant_other": sum(1 for t in late if t["level"] == "significant" and t["per_decade"] * way > 0)},
            "satellite_rain": {"of": len(sat), "same_way": sum(1 for x in sat if x * way < 0),
                               "other_way": sum(1 for x in sat if x * way > 0)},
            "plants": {"of": len(plants), "falling": sum(1 for x in plants if x < 0), "rising": sum(1 for x in plants if x > 0)},
            "worst_steps": [[y, steps[y]] for y in worst],
            "join_steps": [[y, steps.get(y)] for y in (1992, 2001, 2011)]}


# ---------------------------------------------------------------------- drivers
def drivers(years: list[int], ind: dict, keys: list[str]) -> dict:
    """Why the aridity index moves, per cell: d ln(P/PET) = d ln P - d ln PET, the rain's part and
    the evaporative demand's part (heat), in % per decade (Sen's slopes of the logarithms)."""
    y = np.asarray(years, float)
    out = {}
    for i, k in enumerate(keys):
        p, e = ind["rain"][i], ind["pet"][i]
        ok = np.isfinite(p) & np.isfinite(e) & (p > 0) & (e > 0)
        if ok.sum() < 15:
            continue
        rp = 100 * 10 * stats.sen_slope(y[ok], np.log(p[ok]))
        ep = 100 * 10 * stats.sen_slope(y[ok], np.log(e[ok]))
        out[k] = {"rain_pct": rp, "pet_pct": ep, "aridity_pct": rp - ep}
    return out


# ------------------------------------------------------------------------ story
def _km2(x: float) -> str:
    return f"{x:,.0f} km²"


def story(res: dict) -> list[dict]:
    """Plain-language findings, the science first (detected, how much, how sure, what next)."""
    out = []
    det, hc, fc = res["detect"], res["hindcast"], res["forecast"]
    land = det["lgp"]["summary"]["land_km2"]
    for key in ["lgp", "soil_root", "aridity", "surface_temp", "erosivity", "wind_erosion", "npp", "albedo"]:
        if key not in det:
            continue
        ind, sm = INDICATORS[key], det[key]["summary"]
        if not sm["tested"]:
            continue
        txt = (f"{ind.label}: of {sm['tested']} cells, {sm['local']} show a significant trend (both tests at 5 %; "
               f"chance alone would give about {sm['expected_by_chance']:.0f}); {sm['detected']} survive the false "
               f"discovery rate of {int(100 * FDR_Q)} % across the map")
        if sm["detected"]:
            txt += (f": {sm['up']} rising ({_km2(sm['area_up_km2'])}), {sm['down']} falling "
                    f"({_km2(sm['area_down_km2'])}), median {sm['median_rate_detected']:+.{ind.decimals + 1}f} "
                    f"{ind.units} per decade where detected.")
        else:
            txt += ": no change on this map can be told apart from chance."
        if ind.good and sm["detected"]:
            txt += (f" For rain-fed farming that is worse on {_km2(sm['area_worse_km2'])} and better on "
                    f"{_km2(sm['area_better_km2'])} of {_km2(land)}.")
        out.append({"kind": "detect", "key": key, "text": txt, "score": 5 if key == "lgp" else 3 if sm["detected"] else 1})
    for key, e in res["eva"].items():
        ind = INDICATORS[key]
        txt = (f"Eva read the {ind.label.lower()} of {e['read']} cells year by year: {e['changed']} changed dynamic "
               f"(her own control, a steady trend plus noise as persistent as each cell, expects "
               f"{e['expected_by_control']:.0f}; p = {e['p_changed']:.2g}).")
        for c in (e.get("changes") or {}).get("changes", []):
            txt += (f" Around {c['year']:.0f} the {c['type']} in {c['cells']} cells together "
                    f"(chance never gathers as many: p = {c['p']:.2g}).")
        b = e["borders"]
        if b.get("strong"):
            txt += f" {b['strong']} borders where significant trends of opposite signs meet."
        out.append({"kind": "eva", "key": key, "text": txt, "score": 4 if e["changed"] > e["expected_by_control"] * 2 else 2})
    for key, e in res["eva"].items():
        sj = e.get("stream_joins") or {}
        if sj.get("of") and sj.get("p") is not None and sj["p"] < 0.05:
            out.append({"kind": "data", "key": key, "score": 4, "text": (
                f"{INDICATORS[key].label}: {sj['near']} of Eva's {sj['of']} changes of dynamic fall within a year of "
                f"a MERRA-2 stream join (1991/92, 2000/01, 2010/11), where {100 * sj['chance']:.0f} % would by chance "
                f"(p = {sj['p']:.2g}): these changes may be the reanalysis changing what it assimilates, not the "
                f"land changing.")})
    cc = res.get("crosscheck") or {}
    if cc.get("cells"):
        ind = INDICATORS[cc["indicator"]]
        rl, sr, pl = cc["reanalysis_late"], cc["satellite_rain"], cc["plants"]
        out.append({"kind": "data", "key": cc["indicator"], "score": 6, "text": (
            f"The {cc['cells']} cells where the {ind.label.lower()} got significantly worse since {FIRST}, seen again over "
            f"{cc['since']}-{LAST}: the reanalysis still shows it in {rl['same_way']} ({rl['significant_same']} significantly; "
            f"{rl['significant_other']} significantly the other way); where the satellite rain reaches ({sr['of']} cells), "
            f"IMERG agrees in {sr['same_way']} and disagrees in {sr['other_way']}; MODIS plant productivity falls in "
            f"{pl['falling']} and rises in {pl['rising']} of {pl['of']}. A lead the satellite rain leans toward, not yet a "
            f"confirmed loss: the plants do not show it.")})
    rep = res.get("replication") or {}
    for name, r in (rep.get("indicators") or {}).items():
        if name not in ("rain", "lgp"):
            continue
        stt = r["status"]
        out.append({"kind": "data", "key": name, "score": 5, "text": (
            f"Two NASA records, {rep['years'][0]}-{rep['years'][1]}, {r['cells']} cells: {INDICATORS[name].label.lower()} "
            f"made from the satellite rain (GPM IMERG) trends {r['median_imerg']:+.3g} {INDICATORS[name].units} per "
            f"decade (median), from the reanalysis rain (MERRA-2) {r['median_merra']:+.3g}; same direction in "
            f"{100 * r['same_sign']:.0f} % of the cells, year-to-year agreement r = {r['median_r']:.2f}. "
            f"{stt['confirmed']} cells confirmed by both, {stt['contradicted']} contradicted, {stt['not confirmed']} "
            f"seen by the reanalysis only, {stt['satellite only']} by the satellite only.")})
    for key in ["lgp", "soil_root", "aridity", "surface_temp"]:
        h = hc.get(key)
        if not h or not h.get("cells"):
            continue
        ind = INDICATORS[key]
        me, w, cov = h["median_error"], h["weights"], h["coverage90"]
        txt = (f"Hindcast, {ind.label.lower()} ({h['cells']} cells): the forecast learned on the decades after "
               f"{', '.join(map(str, h['learn']['cuts']))} keeps {100 * w['eva']:.0f} % of Eva's last dynamic, {100 * w['norm']:.0f} % "
               f"of the 1981-2010 norm and {100 * w['persistence']:.0f} % of the last five years. Tested on "
               f"{h['window'][0]}-{h['window'][1]}, which it never saw, it misses by {me['blend']:.2f} year-to-year "
               f"spreads (median; Eva's last dynamic alone {me['eva']:.2f}, straight line {me['line']:.2f}, last five "
               f"years {me['persistence']:.2f}, norm {me['norm']:.2f}); its 90 % interval holds the truth in "
               f"{100 * cov['blend']:.0f} % of the cells (Eva's own interval: {100 * cov['eva']:.0f} %).")
        way = "down" if ind.good >= 0 else "up"
        fl = h[way]["blend"]
        if fl["flagged"]:
            txt += (f" Of the {fl['flagged']} cells it flagged as {'losing' if ind.good >= 0 else 'rising'}, "
                    f"{fl['hits']} did ({100 * fl['precision']:.0f} % against {100 * fl['base_rate']:.0f} % of all "
                    f"cells; p = {fl['p_vs_random']:.2g} against as many cells flagged at random).")
        else:
            txt += f" It flagged no cell at {int(100 * RISK_P)} % or more."
        out.append({"kind": "predict", "key": key, "text": txt, "score": 4})
    f = fc.get("lgp") or {}
    risk = [k for k, r in f.items() if r["p_down"] >= RISK_P]
    if f:
        crop = sum(res["cells"][k].get("cropland_ha") or 0 for k in risk)
        loss = [f[k]["recent"] - f[k]["pred"] for k in risk]
        txt = (f"Forecast {HORIZON[0]}-{HORIZON[1]}: {len(risk)} cells are at least {int(100 * RISK_P)} % likely to "
               f"have a shorter growing season than in {LAST - 9}-{LAST}")
        txt += (f" (median {np.median(loss):.0f} days shorter; about {crop:,.0f} ha of cropland in them, MODIS 2024)."
                if risk else ".")
        out.append({"kind": "forecast", "key": "lgp", "text": txt, "score": 5})
    v = res.get("validation") or {}
    yy = (v.get("year_to_year") or {}).get("soil_root")
    if yy:
        out.append({"kind": "validate", "key": "npp", "score": 3, "text": (
            f"Independent check (MODIS, {v['cells']} cells, {v['years'][0]}-{v['years'][1]}): the plants grow more in "
            f"the years the reanalysis' root zone is wetter in {yy['positive']} of {yy['of']} cells (median "
            f"r = {yy['median_r']:.2f}, p = {yy['p_sign']:.2g}).")
            + "".join(f" Trends of plant productivity and {INDICATORS[o].label.lower()} across cells: Spearman "
                      f"{t['spearman']:+.2f} (p = {t['p_shuffled']:.2g} against shuffled cells)."
                      for o, t in (v.get("trends") or {}).items() if o == "soil_root")})
    lc = res.get("cover_change") or {}
    if lc.get("cells"):
        out.append({"kind": "validate", "key": "cover", "score": 2, "text": (
            f"Land cover (MODIS, {lc['cells']} cells, 2001-2024): cropland share {100 * lc['mean_cropland_2001']:.0f} % "
            f"-> {100 * lc['mean_cropland_2024']:.0f} %; croplands spread by more than 5 points in "
            f"{lc['cropland_up']} cells, forests shrank by more than 5 points in {lc['forest_down']}.")})
    out.sort(key=lambda r: -r["score"])
    return out


# ---------------------------------------------------------------------- analysis
def analyse(region: Region, data: dict, mod: dict | None = None, im: dict | None = None, draws: int = 99,
            control_draws: int = 5, log=print) -> dict:
    """The whole land investigation of a region (data already fetched)."""
    mod = mod or {}
    keys = sorted(data[MASK], key=lambda k: _latlon(k))
    lats = [_latlon(k)[0] for k in keys]
    lons = [_latlon(k)[1] for k in keys]
    from .investigate import _step
    dlat, dlon = _step(lats), _step(lons)
    areas = {k: cell_area_km2(_latlon(k)[0], dlat, dlon) for k in keys}
    log("  indicators ...")
    years, ind = indicators(data, keys, mod)
    log("  detection: trends, false discovery rate, areas ...")
    det = {k: detect(years, ind[k], keys, areas, INDICATORS[k]) for k in INDICATORS}
    eva = {}
    for k, i in INDICATORS.items():
        if i.eva:
            log(f"  Eva reads {i.label.lower()} ...")
            eva[k] = eva_read(years, ind[k], keys, det[k], draws=draws, control_draws=control_draws, log=log)
    log("  prediction: hindcast (two splits) and forecast ...")
    hc = {k: hindcast(years, ind[k], keys) for k in PREDICTED}
    fc = {k: forecast(years, ind[k], keys, hc[k]["weights_all"]) for k in PREDICTED}
    log("  replication with GPM IMERG ...")
    rep = replicate(keys, data, im or {})
    cells = {}
    for k in keys:
        la, lo = _latlon(k)
        cover = (mod.get(k) or {}).get("cover") or {}
        c24 = cover.get(2024) or cover.get("2024")
        cells[k] = {"lat": la, "lon": lo, "area_km2": areas[k],
                    "cropland": c24["cropland"] if c24 else None, "forest": c24["forest"] if c24 else None,
                    "cropland_ha": 100 * areas[k] * c24["cropland"] if c24 else None}
    res = {
        "created": dt.date.today().isoformat(), "region": region.as_dict(), "period": [FIRST, LAST],
        "baseline": list(BASE), "learn_cuts": list(LEARN_CUTS), "test_cut": TEST_CUT, "horizon": list(HORIZON), "fdr_q": FDR_Q, "risk_p": RISK_P,
        "grid": {"dlat": dlat, "dlon": dlon}, "indicators": {k: i.as_dict() for k, i in INDICATORS.items()},
        "params": PARAMS, "years": years, "cells": cells,
        "series": {k: {key: [None if not math.isfinite(x) else round(float(x), 4) for x in row]
                       for key, row in zip(keys, ind[k])} for k in INDICATORS},
        "detect": det, "eva": eva, "hindcast": hc, "forecast": fc,
        "drivers": drivers(years, ind, keys),
        "validation": validate_npp(years, ind, keys), "replication": rep,
        "cover_change": land_cover_change(keys, mod, areas),
    }
    res["crosscheck"] = crosscheck(res)
    res["story"] = story(res)
    return clean(res)


def run(region: Region | str, offline: bool = True, draws: int = 99, with_modis: bool = True, log=print) -> dict:
    """Fetch (unless ``offline``: the caches only) and analyse a region. MODIS is only read from its
    cache: the service is too slow to wait for (``fetch`` downloads it)."""
    r = region if isinstance(region, Region) else parse_region(region)
    data = in_country(r, fetch_power(r, offline=offline, log=log))
    pts = land_cells(data)
    mod = fetch_modis(pts, offline=True, log=lambda *_: None) if with_modis else {}
    im = fetch_imerg(subgrid(pts), offline=offline, log=log)
    return analyse(r, data, mod, im, draws=draws, log=log)


# ----------------------------------------------------------------------- CLI
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="detective.land", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch", help="download (and cache) the NASA data of a region")
    f.add_argument("--region", default="cameroon_chad")
    f.add_argument("--no-modis", action="store_true")
    f.add_argument("--workers", type=int, default=4)
    a = sub.add_parser("analyse", help="detect, quantify, test and predict the land's changes (cached data)")
    a.add_argument("--region", default="cameroon_chad")
    a.add_argument("--draws", type=int, default=99, help="fields without change for Eva's changes (0 skips)")
    a.add_argument("--online", action="store_true", help="fetch what is not cached")
    rf = sub.add_parser("refresh", help="recompute the cross-check and the story of a saved analysis")
    rf.add_argument("--region", default="cameroon_chad")
    args = ap.parse_args(argv)
    if args.cmd == "refresh":
        out = OUT / f"{args.region}.json"
        res = json.loads(out.read_text())
        res["crosscheck"] = clean(crosscheck(res))
        res["story"] = clean(story(res))
        out.write_text(json.dumps(res))
        for line in res["story"][:4]:
            print(" -", line["text"])
        return 0
    if args.cmd == "fetch":
        r = parse_region(args.region)
        data = in_country(r, fetch_power(r))
        pts = land_cells(data)
        print(f"{len(pts)} land cells")
        print(f"IMERG at {len(fetch_imerg(subgrid(pts)))} subgrid cells")
        if not args.no_modis:
            got = fetch_modis(pts, workers=args.workers)
            print(f"MODIS: cover at {sum(1 for v in got.values() if v.get('cover'))} cells, "
                  f"NPP at {sum(1 for v in got.values() if v.get('npp'))}")
        return 0
    if args.cmd == "analyse":
        res = run(args.region, offline=not args.online, draws=args.draws)
        OUT.mkdir(parents=True, exist_ok=True)
        out = OUT / f"{args.region}.json"
        out.write_text(json.dumps(res))
        for line in res["story"]:
            print(" -", line["text"])
        print(f"Saved {out}")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
