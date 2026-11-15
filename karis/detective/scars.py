"""Where vegetation gave way to bare ground: the trace mines and quarries leave on the land.

What the data at hand can and cannot say. MERRA-2, CERES, IMERG and MODIS plant productivity see
the climate and the plants; none of them sees a mineral. A deposit underground, rare earths
included, leaves no mark in them: finding one needs geological maps or a mineral-mapping instrument
(NASA EMIT, ASTER). What they can see is the scar a mine leaves once it is dug: open-pit and
artisanal mines, quarries and dredged river beds strip the vegetation and leave bare ground. So
this module reads MODIS land cover (MCD12Q1, 500 m, yearly IGBP classes, ORNL DAAC web service, no
login) over the whole region and keeps the pixels that were vegetated in 2001 and are bare ground
(class 16) at every later reading once they turned bare. Neighbouring pixels form a patch; each patch
says when it opened (between two readings), what grew there before, and how large it is.

A patch is a candidate, not a mine: towns, roads, burnt or flooded land and the dry northern edge
(where grass and bare ground swap with the rains) can open bare ground too. How often the patches
fall near mines that people have mapped (OpenStreetMap: quarries, mines, mine shafts) compared with
random places of the same region measures what the method is worth; both numbers travel with the
result.

    python -m detective.scars --region cameroon_full          # fetch (cached) and read
    python -m detective.scars --region cameroon_full --offline

Writes ``data/earth/land/<region>_scars.json``.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from scipy import ndimage
from scipy import stats as st

from . import land, modis

YEARS = (2001, 2008, 2016, 2023)  # MCD12Q1 readings: first, two between (when it opened), last
WINDOW_KM = 100  # the web service's largest window: 401 x 401 pixels of 463 m around a point
STEP_DEG = 1.75  # window centres: 200 km windows, a little overlap
VEG = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 14}  # forests, shrubs, savannas, grass, crops, crop mosaics
BARE = 16
MIN_PIXELS = 2  # a patch of one pixel (21 ha) is too often a classification flicker
NAMES = {1: "evergreen needleleaf forest", 2: "evergreen broadleaf forest", 3: "deciduous needleleaf forest",
         4: "deciduous broadleaf forest", 5: "mixed forest", 6: "closed shrubland", 7: "open shrubland",
         8: "woody savanna", 9: "savanna", 10: "grassland", 11: "wetland", 12: "cropland", 13: "urban",
         14: "cropland and natural vegetation", 15: "snow and ice", 16: "bare ground", 17: "water"}
R_SIN = 6371007.181  # the MODIS sinusoidal sphere
NEAR_KM = 5.0  # a mapped mine "has" a patch when one lies this close
OVERPASS = "https://overpass-api.de/api/interpreter"
CACHE = Path(__file__).resolve().parents[1] / "data" / "earth" / "cache" / "osm"


def _latlon_of(x: float, y: float) -> tuple[float, float]:
    lat = y / R_SIN
    return math.degrees(lat), math.degrees(x / (R_SIN * math.cos(lat)))


def _km(la1, lo1, la2, lo2) -> float:
    p1, p2 = math.radians(la1), math.radians(la2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(min(1.0, a)))


def windows(cells: dict, grid: dict) -> list[tuple[float, float]]:
    """Window centres covering the region's cells (only windows that hold some of them)."""
    lats = [c["lat"] for c in cells.values()]
    lons = [c["lon"] for c in cells.values()]
    s, n = min(lats) - grid["dlat"] / 2, max(lats) + grid["dlat"] / 2
    w, e = min(lons) - grid["dlon"] / 2, max(lons) + grid["dlon"] / 2
    out = []
    la = s + 0.85
    while la - 0.9 < n:
        lo = w + 0.85
        while lo - 0.9 < e:
            if any(abs(c["lat"] - la) <= 0.9 + grid["dlat"] / 2 and abs(c["lon"] - lo) <= 0.9 + grid["dlon"] / 2
                   for c in cells.values()):
                out.append((round(la, 3), round(lo, 3)))
            lo += STEP_DEG
        la += STEP_DEG
    return out


def fetch(centre: tuple[float, float], year: int, offline: bool = False) -> dict:
    la, lo = centre
    return modis._get("MCD12Q1/subset", {"latitude": la, "longitude": lo, "band": "LC_Type1",
                                         "startDate": f"A{year}001", "endDate": f"A{year}365",
                                         "kmAboveBelow": WINDOW_KM, "kmLeftRight": WINDOW_KM}, offline=offline)


def fetch_all(centres: list, offline: bool = False, workers: int = 2, log=print) -> dict:
    """``{(centre, year): response}``, a few requests at a time (the service is slow, ~1 min each)."""
    jobs = [(c, y) for c in centres for y in YEARS]
    out, done, t0 = {}, 0, time.time()

    def one(job):
        try:
            return job, fetch(job[0], job[1], offline)
        except Exception as e:  # noqa: BLE001 - a window that fails is reported, the rest goes on
            return job, {"error": str(e)}

    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        for job, r in ex.map(one, jobs):
            out[job] = r
            done += 1
            if done % 5 == 0 or done == len(jobs):
                log(f"  MCD12Q1 {done}/{len(jobs)} ({time.time() - t0:.0f} s)")
    return out


def grid_of(resp: dict) -> tuple[np.ndarray, float, float, float]:
    """The window as rows (north first) x columns, and its lower-left corner and pixel size (m)."""
    nr, nc = int(resp["nrows"]), int(resp["ncols"])
    a = np.asarray(resp["subset"][0]["data"], dtype=np.int16).reshape(nr, nc)
    return a, float(resp["xllcorner"]), float(resp["yllcorner"]), float(resp["cellsize"])


def opened(stack: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Pixels vegetated at the first reading and bare at every reading from the one where they turned
    bare to the last: (mask, index of the first bare reading)."""
    veg0 = np.isin(stack[0], list(VEG))
    bare = stack == BARE
    k = stack.shape[0]
    first = np.full(stack.shape[1:], -1, dtype=np.int8)
    ok = np.zeros(stack.shape[1:], dtype=bool)
    for i in range(1, k):  # the earliest reading from which it stays bare
        stays = bare[i:].all(axis=0)
        new = stays & ~ok
        first[new] = i
        ok |= stays
    return veg0 & ok, first


def read_patches(resps: dict, centres: list, cells: dict, grid: dict, log=print) -> list[dict]:
    """Patches of opened bare ground over all windows (a pixel seen by two windows counts once)."""
    seen: set = set()
    patches = []
    for c in centres:
        rs = [resps.get((c, y)) for y in YEARS]
        if any(r is None or "error" in r or not r.get("subset") for r in rs):
            log(f"  window {c}: missing data, skipped")
            continue
        grids = [grid_of(r) for r in rs]
        a0, xll, yll, cs = grids[0]
        if any(g[0].shape != a0.shape or abs(g[1] - xll) > 1 or abs(g[2] - yll) > 1 for g in grids):
            log(f"  window {c}: the readings do not share a grid, skipped")
            continue
        stack = np.stack([g[0] for g in grids])
        mask, first = opened(stack)
        lab, n = ndimage.label(mask, structure=np.ones((3, 3), int))
        nr = a0.shape[0]
        for i in range(1, n + 1):
            rr, cc = np.nonzero(lab == i)
            if len(rr) < MIN_PIXELS:
                continue
            gx = np.round((xll + (cc + 0.5) * cs) / cs).astype(np.int64)  # global pixel ids: no double count
            gy = np.round((yll + (nr - rr - 0.5) * cs) / cs).astype(np.int64)
            ids = set(zip(gx.tolist(), gy.tolist()))
            if ids & seen:
                ids -= seen
                if len(ids) < MIN_PIXELS:
                    continue
            seen |= ids
            x = xll + (cc.mean() + 0.5) * cs
            y = yll + (nr - rr.mean() - 0.5) * cs
            la, lo = _latlon_of(x, y)
            if not _in_region(la, lo, cells, grid):
                continue
            before = np.bincount(stack[0][rr, cc], minlength=18)
            fi = int(np.bincount(first[rr, cc][first[rr, cc] > 0]).argmax())
            patches.append({"lat": round(la, 4), "lon": round(lo, 4), "pixels": int(len(ids)),
                            "area_km2": round(len(ids) * cs * cs / 1e6, 2),
                            "opened": [YEARS[fi - 1], YEARS[fi]],
                            "before": NAMES.get(int(before.argmax()), str(int(before.argmax())))})
    patches.sort(key=lambda p: -p["area_km2"])
    return patches


def _in_region(la: float, lo: float, cells: dict, grid: dict) -> bool:
    k = land.cell_key(round(round(la / grid["dlat"]) * grid["dlat"], 3), round(round(lo / grid["dlon"]) * grid["dlon"], 3))
    if k in cells:
        return True
    return any(abs(c["lat"] - la) <= grid["dlat"] / 2 and abs(c["lon"] - lo) <= grid["dlon"] / 2 for c in cells.values())


# ------------------------------------------------------------------ the check against mapped mines
def mapped_mines(cells: dict, grid: dict, offline: bool = False) -> list[dict]:
    """Mines, quarries and mine shafts mapped in OpenStreetMap inside the region's box (cached)."""
    lats = [c["lat"] for c in cells.values()]
    lons = [c["lon"] for c in cells.values()]
    s, n = min(lats) - grid["dlat"] / 2, max(lats) + grid["dlat"] / 2
    w, e = min(lons) - grid["dlon"] / 2, max(lons) + grid["dlon"] / 2
    box = f"{s:.3f},{w:.3f},{n:.3f},{e:.3f}"
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"mines_{box.replace(',', '_')}.json"
    if f.exists():
        d = json.loads(f.read_text())
    elif offline:
        return []
    else:
        q = (f'[out:json][timeout:180];(nwr["landuse"="quarry"]({box});nwr["man_made"="mineshaft"]({box});'
             f'nwr["industrial"="mine"]({box});nwr["landuse"="mining"]({box});nwr["historic"="mine"]({box}););out center tags;')
        req = urllib.request.Request(OVERPASS, data=urllib.parse.urlencode({"data": q}).encode(),
                                     headers={"User-Agent": "eva-land-detective/1.0"})
        d = json.load(urllib.request.urlopen(req, timeout=300))
        f.write_text(json.dumps(d))
    out = []
    for el in d.get("elements", []):
        la = el.get("lat", (el.get("center") or {}).get("lat"))
        lo = el.get("lon", (el.get("center") or {}).get("lon"))
        if la is None or not _in_region(la, lo, cells, grid):
            continue
        t = el.get("tags", {})
        out.append({"lat": la, "lon": lo, "name": t.get("name"),
                    "kind": t.get("landuse") or t.get("man_made") or t.get("industrial") or t.get("historic"),
                    "resource": t.get("resource")})
    return out


def validate(patches: list[dict], mines: list[dict], cells: dict, grid: dict, seed: int = 0) -> dict:
    """How much more often a mapped mine has a patch within NEAR_KM than a random place of the region."""
    if not mines:
        return {"mapped_mines": 0, "note": "no mine or quarry mapped in OpenStreetMap here: the patches cannot be checked"}
    pts = np.array([[p["lat"], p["lon"]] for p in patches]) if patches else np.zeros((0, 2))

    def near(la, lo):
        if not len(pts):
            return False
        d = np.abs(pts[:, 0] - la) < NEAR_KM / 100 + 0.01
        return any(_km(la, lo, a, b) <= NEAR_KM for a, b in pts[d & (np.abs(pts[:, 1] - lo) < NEAR_KM / 100 + 0.01)])

    hit = sum(near(m["lat"], m["lon"]) for m in mines)
    rng = random.Random(seed)
    keys = list(cells)
    rand = []
    while len(rand) < 2000:
        c = cells[rng.choice(keys)]
        rand.append((c["lat"] + (rng.random() - .5) * grid["dlat"], c["lon"] + (rng.random() - .5) * grid["dlon"]))
    base = sum(near(a, b) for a, b in rand) / len(rand)
    p = float(st.binom.sf(hit - 1, len(mines), base)) if base > 0 else (0.0 if hit else 1.0)
    return {"mapped_mines": len(mines), "with_patch_within_km": NEAR_KM, "mapped_with_patch": hit,
            "share_mapped": hit / len(mines), "share_random_places": base,
            "enrichment": (hit / len(mines)) / base if base > 0 else None, "p": p,
            "kinds": _count(m["kind"] for m in mines)}


def _count(xs) -> dict:
    out: dict = {}
    for x in xs:
        out[x or "?"] = out.get(x or "?", 0) + 1
    return out


def run(region_key: str, offline: bool = False, workers: int = 2, log=print) -> dict:
    res = json.loads((land.OUT / f"{region_key}.json").read_text())
    cells, grid = res["cells"], res["grid"]
    centres = windows(cells, grid)
    log(f"{region_key}: {len(centres)} windows of {2 * WINDOW_KM} km x {len(YEARS)} readings of MCD12Q1")
    resps = fetch_all(centres, offline=offline, workers=workers, log=log)
    patches = read_patches(resps, centres, cells, grid, log=log)
    log(f"  {len(patches)} patches of opened bare ground ({sum(p['area_km2'] for p in patches):.0f} km2)")
    try:
        mines = mapped_mines(cells, grid, offline=offline)
    except Exception as e:  # noqa: BLE001 - the check is optional
        log(f"  OpenStreetMap not reached: {e}")
        mines = []
    val = validate(patches, mines, cells, grid)
    log(f"  check: {json.dumps(val)}")
    missing = sum(1 for r in resps.values() if "error" in r)
    return {"region": region_key, "years": list(YEARS), "windows": len(centres), "missing_readings": missing,
            "method": ("MODIS MCD12Q1 land cover (500 m, IGBP classes), read in 2001, 2008, 2016 and 2023: pixels "
                       "vegetated in 2001 that turned to bare ground and stayed bare at every later reading; "
                       f"neighbouring pixels form a patch, patches of fewer than {MIN_PIXELS} pixels are dropped."),
            "cannot_see": ("Minerals themselves: rare earths or any deposit underground leave no mark in climate, rain, "
                           "plant or land-cover data. Finding them needs geological maps or a mineral-mapping instrument "
                           "(NASA EMIT, ASTER). Mines smaller than a few hectares, and mines under forest canopy, are below "
                           "what 500 m pixels resolve."),
            "validation": val, "patches": patches,
            "mapped_mines": mines}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--region", default="cameroon_full")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--workers", type=int, default=2)
    a = ap.parse_args(argv)
    out = run(a.region, offline=a.offline, workers=a.workers)
    f = land.OUT / f"{a.region}_scars.json"
    f.write_text(json.dumps(out))
    print(f"Saved {f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
