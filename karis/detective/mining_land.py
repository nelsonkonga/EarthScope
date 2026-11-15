"""Where is mining transforming the land of East Cameroon, how fast, and where will it spread?

The rasters and vectors of ``detective.mining`` (Lom-Kadéï gold belt, 3.9-6.1°N, 13.5-15.3°E)
summed on one grid of 0.01° cells (about 1.1 km, 220 rows x 180 columns): each cell carries its
forest loss year by year (Hansen GFC 2001-2025), the loss within 300 m of water, its water
history (JRC GSW 1984-2021), its relief (SRTM), its people (WorldPop 2000-2020), how far it is
from rivers, roads, villages, and the mapped mines (OpenStreetMap, Maus et al. 2022).

- ``build``: the grid, ``data/earth/mining/cells.npz`` (+ ``cells.json``: what each array is).
- ``where``: what differs where mines are mapped (each variable against the cells far from any),
  the cells whose change looks like it.
- ``speed``: the land cleared each year next to the mapped mines and elsewhere, its trend (Sen,
  Mann-Kendall), its growth rate and doubling time, the break year (Pettitt), how fast the
  cleared footprint moves away from the first sites.
- ``spread``: where the next clearing comes, a logistic model of the state of each cell at year
  T against its new loss over the next 5 years. Learnt on T = 2010 and 2015, judged on 2020
  (2021-2025, never seen: a hindcast), then projected from 2025 to 2026-2030. The mapped mines
  are left out of the hindcast (they were mapped later: the future would leak in).

    python -m detective.mining_land build
    python -m detective.mining_land analyse      # where, speed, spread -> data/earth/mining/land_change.json
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from .mining import AREA, OUT, RAW

STEP = 0.01  # degrees: the cell
NR = round((AREA.north - AREA.south) / STEP)  # 220 rows, north first
NC = round((AREA.east - AREA.west) / STEP)  # 180 columns, west first
YEARS = list(range(2001, 2026))  # Hansen loss years
POP_YEARS = list(range(2000, 2021))
FINE = 0.001  # degrees: the grid the vectors are drawn on before measuring distances
KM_LAT = 110.57
KM_LON = 111.32 * math.cos(math.radians((AREA.south + AREA.north) / 2))
NEAR_WATER_KM = 0.3
NEAR_MINE_KM = 1.0  # a cell « next to a mapped mine »: within 1 km of one
FAR_MINE_KM = 10.0  # « far from any »: beyond 10 km
# the Lom Pangar reservoir (filled 2015-2016): its flooded forest is loss next to new water that no
# mine made; its box (south, north, west, east) is left out of every comparison
RESERVOIR = (5.1, 5.8, 13.5, 14.15)


def centres() -> tuple[np.ndarray, np.ndarray]:
    lat = AREA.north - STEP * (np.arange(NR) + 0.5)
    lon = AREA.west + STEP * (np.arange(NC) + 0.5)
    return lat, lon


def _blocks(a: np.ndarray, k: int, how: str = "mean") -> np.ndarray:
    """Pool each k x k block of pixels (mean, max, min...)."""
    b = a.reshape(a.shape[0] // k, k, a.shape[1] // k, k)
    return getattr(b, how)(axis=(1, 3))


def _read(name: str) -> np.ndarray:
    import rasterio
    with rasterio.open(RAW / name) as ds:
        b = ds.bounds
        assert abs(b.left - AREA.west) < 1e-6 and abs(b.top - AREA.north) < 1e-6, name
        return ds.read(1)


def _fine_transform():
    from rasterio.transform import from_origin
    return from_origin(AREA.west, AREA.north, FINE, FINE)


def _draw(geoms, all_touched: bool = True) -> np.ndarray:
    """Vectors drawn on the 0.001° grid (True where a feature passes)."""
    from rasterio.features import rasterize
    shape = (NR * 10, NC * 10)
    geoms = [g for g in geoms if g is not None]
    if not geoms:
        return np.zeros(shape, bool)
    return rasterize(((g, 1) for g in geoms), out_shape=shape, transform=_fine_transform(),
                     all_touched=all_touched, dtype="uint8").astype(bool)


def _distance_km(mask: np.ndarray) -> np.ndarray:
    """Distance (km) from each 0.001° pixel to the nearest True one; then the nearest within each cell."""
    from scipy import ndimage
    if not mask.any():
        return np.full((NR, NC), np.inf, np.float32)
    d = ndimage.distance_transform_edt(~mask, sampling=(FINE * KM_LAT, FINE * KM_LON)).astype(np.float32)
    return _blocks(d, 10, "min")


def _features(name: str, keep=None) -> list:
    import shapely.geometry as sg
    p = OUT / name
    if not p.exists():
        return []
    out = []
    for f in json.loads(p.read_text())["features"]:
        if keep is None or keep(f["properties"]):
            try:
                out.append(sg.shape(f["geometry"]))
            except Exception:  # noqa: BLE001 — a broken OSM way is skipped
                continue
    return out


# ------------------------------------------------------------------ the grid
def build(log=print) -> Path:
    from scipy import ndimage
    arrays: dict[str, np.ndarray] = {}
    doc: dict[str, str] = {}

    # forest and its loss (30 m: 40 x 40 pixels a cell)
    land = _read("hansen_datamask.tif") == 1
    arrays["land"] = _blocks(land.astype(np.float32), 40)
    doc["land"] = "share of the cell that is land (Hansen data mask)"
    tc = _read("hansen_treecover2000.tif")
    arrays["forest2000"] = _blocks(((tc >= 30) & land).astype(np.float32), 40)
    doc["forest2000"] = "share of the cell under tree cover >= 30 % in 2000"
    arrays["treecover2000"] = _blocks(tc.astype(np.float32), 40)
    doc["treecover2000"] = "mean tree cover in 2000 (%)"
    del tc

    occ = _read("gsw_occurrence.tif")
    water = (occ > 0) & (occ <= 100)
    wf = _blocks(water, 4, "max")  # 0.001°: water anywhere in the 4 x 4 pixels
    dw = ndimage.distance_transform_edt(~wf, sampling=(FINE * KM_LAT, FINE * KM_LON))
    near = np.repeat(np.repeat(dw <= NEAR_WATER_KM, 4, axis=0), 4, axis=1)
    del dw
    arrays["water_occurrence"] = _blocks(np.where(water, occ, 0).astype(np.float32), 40)
    doc["water_occurrence"] = "mean water occurrence 1984-2021 (%, GSW)"
    arrays["near_water"] = _blocks(near.astype(np.float32), 40)
    doc["near_water"] = f"share of the cell within {NEAR_WATER_KM * 1000:.0f} m of water"
    del occ, water

    loss = _read("hansen_lossyear.tif")
    ly = np.zeros((len(YEARS), NR, NC), np.float32)
    lw = np.zeros((len(YEARS), NR, NC), np.float32)
    for i, y in enumerate(YEARS):
        m = loss == (y - 2000)
        ly[i] = _blocks(m.astype(np.float32), 40)
        lw[i] = _blocks((m & near).astype(np.float32), 40)
    arrays["loss"], arrays["loss_near_water"] = ly, lw
    doc["loss"] = "share of the cell whose trees were lost that year (rows = YEARS)"
    doc["loss_near_water"] = f"the same, within {NEAR_WATER_KM * 1000:.0f} m of water"
    del loss, near

    tr = _read("gsw_transitions.tif")
    for code, key in ((2, "new_permanent_water"), (5, "new_seasonal_water"), (3, "lost_permanent_water"),
                      (6, "lost_seasonal_water"), (10, "ephemeral_seasonal_water")):
        arrays[key] = _blocks((tr == code).astype(np.float32), 40)
        doc[key] = f"share of the cell that is « {key.replace('_', ' ')} » (GSW transitions 1984-2021)"
    del tr
    log("  forest, loss and water summed")

    # relief (SRTM 1 arc-second: 36 x 36 pixels a cell)
    dem = _read("srtm_dem.tif").astype(np.float32)
    dem[dem < -1000] = np.nan
    arrays["elevation"] = np.nanmean(dem.reshape(NR, 36, NC, 36), axis=(1, 3))
    doc["elevation"] = "mean elevation (m, SRTM)"
    gy, gx = np.gradient(dem, 30.9, 30.9 * math.cos(math.radians(5.0)))
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    del gx, gy, dem
    arrays["slope"] = np.nanmean(slope.reshape(NR, 36, NC, 36), axis=(1, 3))
    doc["slope"] = "mean slope (degrees, SRTM 30 m)"
    del slope

    # people (WorldPop 1 km, read on the cell grid)
    import rasterio
    from rasterio.transform import from_origin
    from rasterio.warp import Resampling, reproject
    pop = np.zeros((len(POP_YEARS), NR, NC), np.float32)
    with rasterio.open(RAW / "worldpop_2000_2020.tif") as ds:
        for i in range(len(POP_YEARS)):
            reproject(ds.read(i + 1), pop[i], src_transform=ds.transform, src_crs=ds.crs, src_nodata=ds.nodata,
                      dst_transform=from_origin(AREA.west, AREA.north, STEP, STEP), dst_crs=ds.crs,
                      dst_nodata=np.nan, resampling=Resampling.average)
    pop[~np.isfinite(pop)] = 0.0
    arrays["population"] = pop
    doc["population"] = "people in the cell (WorldPop 1 km, rows = POP_YEARS)"

    # distances (km) to what OpenStreetMap maps
    rivers = _features("osm_rivers.geojson")
    big = _features("osm_rivers.geojson", lambda p: p.get("waterway") == "river")
    roads = _features("osm_roads.geojson")
    main = _features("osm_roads.geojson", lambda p: p.get("highway") in ("trunk", "primary", "secondary", "tertiary"))
    villages = _features("osm_places.geojson", lambda p: p.get("place") in ("village", "town", "city"))
    towns = _features("osm_places.geojson", lambda p: p.get("place") in ("town", "city"))
    for key, geoms, what in (("dist_stream", rivers, "any river or stream"), ("dist_river", big, "a river"),
                             ("dist_road", roads, "any road, track or path"),
                             ("dist_main_road", main, "a trunk, primary, secondary or tertiary road"),
                             ("dist_village", villages, "a village, town or city"),
                             ("dist_town", towns, "a town or city")):
        arrays[key] = _distance_km(_draw(geoms))
        doc[key] = f"distance (km) from the cell to {what} (OpenStreetMap)"

    # the mapped mines: the labels, never an input of the hindcast
    mines = _features("osm_mines.geojson")
    maus = _features("mining_polygons_maus2022_cameroon.geojson")
    mm = _draw(mines)
    arrays["mine_mapped"] = _blocks(mm.astype(np.float32), 10)
    doc["mine_mapped"] = "share of the cell under a mine or quarry mapped on OpenStreetMap (0.001° drawing)"
    arrays["dist_mine"] = _distance_km(mm)
    doc["dist_mine"] = "distance (km) to the nearest mine or quarry mapped on OpenStreetMap"
    mp = _draw(maus)
    arrays["maus_mapped"] = _blocks(mp.astype(np.float32), 10)
    doc["maus_mapped"] = "share of the cell under a Maus et al. (2022) mining polygon"
    arrays["dist_maus"] = _distance_km(mp)
    doc["dist_maus"] = "distance (km) to the nearest Maus et al. (2022) mining polygon"
    log("  relief, people, distances and mapped mines on the grid")

    OUT.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(OUT / "cells.npz", **arrays)
    lat, lon = centres()
    meta = {"area": AREA.as_dict(), "step_deg": STEP, "rows": NR, "cols": NC, "years": YEARS, "pop_years": POP_YEARS,
            "lat_first": float(lat[0]), "lon_first": float(lon[0]), "arrays": doc,
            "sources": {"hansen": "Global Forest Change v1.13 (Hansen et al. 2013)",
                        "gsw": "JRC Global Surface Water v1.4 (Pekel et al. 2016)",
                        "srtm": "NASA SRTM GL1 v3", "worldpop": "WorldPop 1 km 2000-2020",
                        "osm": "OpenStreetMap (Overpass, 2026-11-15)",
                        "maus": "Maus et al. 2022, global mining polygons v2 (PANGAEA 942325)"}}
    (OUT / "cells.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False))
    log(f"  {NR} x {NC} cells -> {OUT / 'cells.npz'}")
    return OUT / "cells.npz"


def load() -> dict[str, np.ndarray]:
    with np.load(OUT / "cells.npz") as z:
        return {k: z[k] for k in z.files}


def usable(c: dict) -> np.ndarray:
    """Land cells outside the reservoir box."""
    lat, lon = centres()
    s, n, w, e = RESERVOIR
    box = ((lat >= s) & (lat <= n))[:, None] & ((lon >= w) & (lon <= e))[None, :]
    return (c["land"] > 0.5) & ~box


def cell_km2() -> np.ndarray:
    lat, _ = centres()
    return (STEP * KM_LAT) * (STEP * 111.32 * np.cos(np.radians(lat)))[:, None] * np.ones((1, NC))


# ------------------------------------------------------------------ where
STATIC = ["forest2000", "treecover2000", "water_occurrence", "near_water", "new_permanent_water",
          "new_seasonal_water", "lost_permanent_water", "lost_seasonal_water", "ephemeral_seasonal_water",
          "elevation", "slope", "dist_stream", "dist_river", "dist_road", "dist_main_road", "dist_village",
          "dist_town"]


def _auc(score: np.ndarray, pos: np.ndarray) -> float:
    """Probability that a positive scores above a negative (ties count half)."""
    from scipy.stats import rankdata
    r = rankdata(score)
    n1, n0 = int(pos.sum()), int((~pos).sum())
    return float((r[pos].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)) if n1 and n0 else float("nan")


def derived(c: dict) -> dict[str, np.ndarray]:
    """Variables per cell over the whole record (what « where » compares)."""
    ly, lw = c["loss"], c["loss_near_water"]
    pop = c["population"]
    out = {k: c[k] for k in STATIC}
    out["loss_2001_2025"] = ly.sum(0)
    out["loss_near_water_2001_2025"] = lw.sum(0)
    tot = ly.sum(0)
    out["near_water_share_of_loss"] = np.where(tot > 0.005, lw.sum(0) / np.maximum(tot, 1e-9), np.nan)
    out["loss_2016_2025_vs_2001_2015"] = ly[15:].sum(0) - ly[:15].sum(0)
    out["population_2020"] = pop[-1]
    out["population_growth_2000_2020"] = np.log1p(pop[-1]) - np.log1p(pop[0])
    return out


def where(c: dict) -> dict:
    """Each variable next to the mapped mines (< 1 km) against far from any (> 10 km): medians and
    the AUC (0.5 = no difference). Bootstrapped by 0.2° blocks: neighbouring cells are not
    independent."""
    d = derived(c)
    land = usable(c)
    near = land & (c["dist_mine"] <= NEAR_MINE_KM)
    far = land & (c["dist_mine"] > FAR_MINE_KM)
    rng = np.random.default_rng(0)
    blk = (np.arange(NR)[:, None] // 20) * 100 + (np.arange(NC)[None, :] // 20)
    ids = np.unique(blk[near | far])
    rows = []
    for k, v in d.items():
        ok = np.isfinite(v)
        a, b = v[near & ok], v[far & ok]
        if len(a) < 20 or len(b) < 20:
            continue
        auc = _auc(np.concatenate([a, b]), np.r_[np.ones(len(a), bool), np.zeros(len(b), bool)])
        boots = []
        for _ in range(200):
            pick = rng.choice(ids, len(ids))  # a block drawn twice counts twice
            wa = np.concatenate([v[near & ok & (blk == i)] for i in pick])
            wb = np.concatenate([v[far & ok & (blk == i)] for i in pick])
            if len(wa) > 5 and len(wb) > 5:
                boots.append(_auc(np.concatenate([wa, wb]), np.r_[np.ones(len(wa), bool), np.zeros(len(wb), bool)]))
        lo, hi = (np.quantile(boots, [0.025, 0.975]) if boots else (np.nan, np.nan))
        rows.append({"variable": k, "near_mines_median": float(np.median(a)), "far_median": float(np.median(b)),
                     "near_mines_mean": float(np.mean(a)), "far_mean": float(np.mean(b)),
                     "auc": auc, "auc_lo": float(lo), "auc_hi": float(hi),
                     "differs": bool(lo > 0.5 or hi < 0.5)})
    rows.sort(key=lambda r: -abs(r["auc"] - 0.5))
    return {"near_km": NEAR_MINE_KM, "far_km": FAR_MINE_KM, "cells_near": int(near.sum()), "cells_far": int(far.sum()),
            "variables": rows}


# ------------------------------------------------------------------ speed
def speed(c: dict) -> dict:
    from . import stats
    km2 = cell_km2()
    ly, lw = c["loss"], c["loss_near_water"]
    land = usable(c)
    zones = {"next to mapped mines (< 1 km)": land & (c["dist_mine"] <= NEAR_MINE_KM),
             "1-10 km from mapped mines": land & (c["dist_mine"] > NEAR_MINE_KM) & (c["dist_mine"] <= FAR_MINE_KM),
             "beyond 10 km": land & (c["dist_mine"] > FAR_MINE_KM)}
    out: dict = {"zones": {}}
    for name, z in zones.items():
        area = float((km2 * z).sum())
        series = [float((ly[i] * km2 * z).sum()) for i in range(len(YEARS))]
        wseries = [float((lw[i] * km2 * z).sum()) for i in range(len(YEARS))]
        t = np.array(YEARS, float)
        s = stats.sen(t, series)
        mk = stats.mann_kendall(series)
        pt = stats.pettitt(series)
        lg = np.log(np.maximum(series, 1e-3))
        g = stats.sen(t, lg)
        rate = math.expm1(g["slope"])
        out["zones"][name] = {
            "cells": int(z.sum()), "area_km2": area, "loss_km2_by_year": dict(zip(YEARS, series)),
            "loss_near_water_km2_by_year": dict(zip(YEARS, wseries)),
            "cleared_2001_2025_km2": float(sum(series)), "cleared_share": float(sum(series) / area) if area else None,
            "sen_km2_per_year": s["slope"], "sen_lo": s["ci"][0], "sen_hi": s["ci"][1], "mk_p": mk["p"],
            "growth_per_year": rate, "growth_lo": math.expm1(g["ci"][0]), "growth_hi": math.expm1(g["ci"][1]),
            "doubling_years": math.log(2) / math.log1p(rate) if rate > 0 else None,
            "break_year": YEARS[pt["at"]] if pt["at"] is not None else None, "break_p": pt["p"],
            "share_of_area_per_year_2021_2025": float(np.mean(series[-5:]) / area) if area else None,
        }
    # how far from the first mining sites the clearing goes: the mean distance to the mapped mines of
    # the land cleared each year, inside 20 km of them
    dm = c["dist_mine"]
    zone = land & (dm <= 20)
    out["distance_from_mines_of_cleared_land_km"] = {
        y: float((ly[i] * km2 * zone * dm).sum() / max((ly[i] * km2 * zone).sum(), 1e-9)) for i, y in enumerate(YEARS)}
    dd = list(out["distance_from_mines_of_cleared_land_km"].values())
    s = stats.sen(np.array(YEARS, float), dd)
    out["distance_trend_km_per_year"] = {"slope": s["slope"], "lo": s["ci"][0], "hi": s["ci"][1],
                                         "mk_p": stats.mann_kendall(dd)["p"]}
    # Hansen's loss detection improved in 2013 (Landsat 8): a jump that year is partly the satellite
    out["caveat"] = ("Hansen GFC detects more loss from 2013 on (Landsat 8, algorithm updates): a break near "
                     "2013 is partly the satellite. Shares within a year (near water vs all) are not affected.")
    return out


# ------------------------------------------------------------------ spread
SPREAD_FEATURES = ["log_dist_prior_loss", "loss_around_5y", "loss_around_before", "loss_self_before",
                   "forest_left", "dist_stream", "dist_river", "dist_road", "dist_main_road", "dist_village",
                   "dist_town", "slope", "elevation", "log_population", "new_seasonal_water", "near_water"]
HORIZON = 5
THRESH = 0.02  # a cell « cleared » in a window when >= 2 % of it lost its trees then


def _state(c: dict, T: int, target: str = "loss") -> tuple[dict, np.ndarray | None]:
    """What each cell looks like at the end of year T, and (when known) whether it gets cleared in
    the next HORIZON years (``target``: all loss, or the loss within 300 m of water)."""
    from scipy import ndimage
    ly = c["loss"]
    k = YEARS.index(T) + 1 if T >= YEARS[0] else 0
    before = ly[:k].sum(0)
    recent = ly[max(0, k - 5):k].sum(0)
    prior = before >= THRESH
    if prior.any():
        dprior = ndimage.distance_transform_edt(~prior, sampling=(STEP * KM_LAT, STEP * KM_LON))
    else:
        dprior = np.full((NR, NC), 100.0)
    py = min(T, POP_YEARS[-1])
    f = {"log_dist_prior_loss": np.log1p(dprior), "loss_around_5y": ndimage.uniform_filter(recent, 5, mode="nearest"),
         "loss_around_before": ndimage.uniform_filter(before, 5, mode="nearest"), "loss_self_before": before,
         "forest_left": np.maximum(c["forest2000"] - before, 0), "log_population": np.log1p(c["population"][POP_YEARS.index(py)])}
    for key in SPREAD_FEATURES:
        if key not in f:
            f[key] = c[key]
    y = None
    if k + HORIZON <= len(YEARS):
        y = c[target][k:k + HORIZON].sum(0) >= THRESH
    return f, y


def _matrix(f: dict, keys: list[str]) -> np.ndarray:
    return np.stack([f[k].ravel() for k in keys], axis=1).astype(np.float64)


def logistic(X: np.ndarray, y: np.ndarray, ridge: float = 1.0, iters: int = 50) -> np.ndarray:
    """Logistic regression by Newton steps (a small ridge keeps it stable); X already scaled, with
    a column of ones last."""
    w = np.zeros(X.shape[1])
    R = ridge * np.eye(X.shape[1])
    R[-1, -1] = 0.0
    for _ in range(iters):
        p = 1 / (1 + np.exp(-np.clip(X @ w, -30, 30)))
        g = X.T @ (p - y) + R @ w
        H = (X * (p * (1 - p))[:, None]).T @ X + R
        step = np.linalg.solve(H, g)
        w -= step
        if np.abs(step).max() < 1e-8:
            break
    return w


class Scaler:
    def __init__(self, X):
        self.m, self.s = X.mean(0), X.std(0) + 1e-9

    def __call__(self, X):
        return np.c_[(X - self.m) / self.s, np.ones(len(X))]


def spread(c: dict, target: str = "loss") -> dict:
    """Learn on T = 2010, 2015; judge on 2020 (2021-2025); project from 2025 (2026-2030)."""
    land = usable(c).ravel()
    keys = SPREAD_FEATURES
    trainX, trainy = [], []
    for T in (2010, 2015):
        f, y = _state(c, T, target)
        trainX.append(_matrix(f, keys)[land])
        trainy.append(y.ravel()[land])
    X, y = np.vstack(trainX), np.concatenate(trainy).astype(float)
    sc = Scaler(X)
    w = logistic(sc(X), y)
    f20, y20 = _state(c, 2020, target)
    X20 = _matrix(f20, keys)[land]
    p20 = 1 / (1 + np.exp(-sc(X20) @ w))
    t20 = y20.ravel()[land]
    # the baseline: only how close the cell is to land already cleared
    b = ["log_dist_prior_loss"]
    scb = Scaler(X[:, [keys.index(k) for k in b]])
    wb = logistic(scb(X[:, [keys.index(k) for k in b]]), y)
    pb = 1 / (1 + np.exp(-scb(X20[:, [keys.index(k) for k in b]]) @ wb))

    # a fairer baseline for the loss next to water: where the water is, and how close cleared land is
    b2 = ["log_dist_prior_loss", "near_water"]
    i2 = [keys.index(k) for k in b2]
    sc2 = Scaler(X[:, i2])
    w2 = logistic(sc2(X[:, i2]), y)
    p2 = 1 / (1 + np.exp(-sc2(X20[:, i2]) @ w2))

    def top_of(p, share):
        """Exactly ``share`` of the cells, the highest first (ties broken at random, not all taken)."""
        r = np.random.default_rng(0).random(len(p))
        order = np.lexsort((r, -p))
        top = np.zeros(len(p), bool)
        top[order[:int(round(share * len(p)))]] = True
        return top

    def capture(p, t, share):
        top = top_of(p, share)
        return float(t[top].sum() / max(t.sum(), 1))

    km2 = cell_km2().ravel()[land]
    loss20 = c[target][YEARS.index(2020) + 1:].sum(0).ravel()[land]  # 2021-2025, share of the cell
    def capture_area(p, share):
        top = top_of(p, share)
        return float((loss20 * km2)[top].sum() / max((loss20 * km2).sum(), 1e-9))

    hind = {"auc": _auc(p20, t20.astype(bool)), "auc_baseline_distance_only": _auc(pb, t20.astype(bool)),
            "auc_baseline_distance_and_water": _auc(p2, t20.astype(bool)),
            "cells_cleared_2021_2025": int(t20.sum()), "cells": int(len(t20)),
            "share_cleared_in_top10pc": capture(p20, t20, 0.10), "baseline_top10pc": capture(pb, t20, 0.10),
            "area_lost_in_top10pc": capture_area(p20, 0.10), "area_lost_in_top20pc": capture_area(p20, 0.20),
            "baseline_area_lost_in_top10pc": capture_area(pb, 0.10),
            "predicted_cells": float(p20.sum()), "calibration_ratio": float(p20.sum() / max(t20.sum(), 1))}
    # the weights, on the scaled variables: which ones carry the forecast
    weights = sorted(({"variable": k, "weight": float(w[i])} for i, k in enumerate(keys)),
                     key=lambda r: -abs(r["weight"]))
    # projection: learn again with 2020 (its outcome is known now), apply to the state at 2025
    X3 = np.vstack([X, X20])
    y3 = np.concatenate([y, t20.astype(float)])
    sc3 = Scaler(X3)
    w3 = logistic(sc3(X3), y3)
    f25, _ = _state(c, 2025, target)
    p25 = np.full(NR * NC, np.nan)
    p25[land] = 1 / (1 + np.exp(-sc3(_matrix(f25, keys)[land]) @ w3))
    p25 = p25.reshape(NR, NC)
    return {"target": target, "threshold_share": THRESH, "horizon_years": HORIZON, "features": keys,
            "hindcast_2021_2025": hind, "weights": weights, "risk_2026_2030": p25,
            "risk_2021_2025_hindcast": _unravel(p20, land)}


def _unravel(v: np.ndarray, land: np.ndarray) -> np.ndarray:
    out = np.full(NR * NC, np.nan)
    out[land] = v
    return out.reshape(NR, NC)


def analyse(log=print) -> dict:
    c = load()
    w = where(c)
    log(f"where: {w['cells_near']} cells within {NEAR_MINE_KM} km of a mapped mine, {w['cells_far']} beyond {FAR_MINE_KM} km")
    for r in w["variables"][:12]:
        log(f"  {r['variable']:32s} near {r['near_mines_median']:9.4g}  far {r['far_median']:9.4g}  "
            f"AUC {r['auc']:.2f} [{r['auc_lo']:.2f}, {r['auc_hi']:.2f}]" + ("  *" if r["differs"] else ""))
    s = speed(c)
    for name, z in s["zones"].items():
        log(f"speed {name}: cleared {z['cleared_2001_2025_km2']:.1f} km² ({100 * z['cleared_share']:.1f} %), "
            f"Sen {z['sen_km2_per_year']:+.2f} km²/yr (MK p {z['mk_p']:.2g}), growth {100 * z['growth_per_year']:+.1f} %/yr, "
            f"doubling {z['doubling_years'] and round(z['doubling_years'], 1)} yr, break {z['break_year']} (p {z['break_p']:.2g})")
    dt = s["distance_trend_km_per_year"]
    log(f"  cleared land moves {dt['slope']:+.3f} km/yr from the mapped mines (MK p {dt['mk_p']:.2g})")
    res = {"where": w, "speed": s, "spread": {}}
    maps = {}
    for target in ("loss", "loss_near_water"):
        sp = spread(c, target)
        h = sp["hindcast_2021_2025"]
        log(f"spread ({target}): hindcast AUC {h['auc']:.3f} (distance only {h['auc_baseline_distance_only']:.3f}, "
            f"distance + water {h['auc_baseline_distance_and_water']:.3f}); "
            f"top 10 % of cells hold {100 * h['share_cleared_in_top10pc']:.0f} % of the cleared cells "
            f"({100 * h['area_lost_in_top10pc']:.0f} % of the area lost; distance only {100 * h['baseline_top10pc']:.0f} % / "
            f"{100 * h['baseline_area_lost_in_top10pc']:.0f} %); predicted/observed {h['calibration_ratio']:.2f}")
        log("  weights: " + ", ".join(f"{r['variable']} {r['weight']:+.2f}" for r in sp["weights"][:6]))
        maps[f"risk_{target}_2026_2030"] = sp.pop("risk_2026_2030")
        maps[f"hindcast_{target}_2021_2025"] = sp.pop("risk_2021_2025_hindcast")
        res["spread"][target] = sp
    np.savez_compressed(OUT / "land_change_maps.npz", **maps)
    (OUT / "land_change.json").write_text(json.dumps(res, indent=1, ensure_ascii=False, default=float))
    log(f"-> {OUT / 'land_change.json'}")
    return res


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="detective.mining_land", description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=["build", "analyse"])
    a = ap.parse_args(argv)
    build() if a.cmd == "build" else analyse()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
