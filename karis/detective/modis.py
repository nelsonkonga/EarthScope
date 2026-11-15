"""MODIS land products at any point, without login: the ORNL DAAC MODIS web service.

https://modis.ornl.gov/data/modis_webservice.html — NASA's Oak Ridge DAAC serves subsets of the
MODIS land products around a point (a window of up to 100 km on each side) as JSON, with no
Earthdata Login. A request carries at most 10 dates. The detective uses two products, both
measured by the MODIS instruments on the Terra and Aqua satellites, independent of the MERRA-2
reanalysis that NASA POWER serves:

- ``MOD17A3HGF`` : yearly net primary productivity (NPP, kg of carbon fixed per m² per year,
  gap-filled), 500 m, from 2001: how much the plants actually grew;
- ``MCD12Q1``    : yearly land cover (IGBP classes), 500 m, from 2001: where the croplands are,
  and how they spread.

Every answer is cached on disk (``data/earth/cache/modis``); the service is slow (about 10 s a
request), so the requests run a few at a time.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BASE = "https://modis.ornl.gov/rst/api/v1"
CACHE = Path(__file__).resolve().parents[1] / "data" / "earth" / "cache" / "modis"
WINDOW_KM = 5  # the window: ±5 km around the point (21 x 21 pixels of 463 m)

# IGBP classes of MCD12Q1 (LC_Type1)
IGBP = {1: "evergreen needleleaf forest", 2: "evergreen broadleaf forest", 3: "deciduous needleleaf forest",
        4: "deciduous broadleaf forest", 5: "mixed forest", 6: "closed shrubland", 7: "open shrubland",
        8: "woody savanna", 9: "savanna", 10: "grassland", 11: "permanent wetland", 12: "cropland",
        13: "urban", 14: "cropland / natural vegetation mosaic", 15: "snow and ice", 16: "barren", 17: "water"}
FOREST = {1, 2, 3, 4, 5}


class ModisError(RuntimeError):
    pass


def _get(path: str, query: dict, offline: bool = False) -> dict:
    url = f"{BASE}/{path}?{urllib.parse.urlencode(query)}"
    key = hashlib.sha1(url.encode()).hexdigest()[:24]
    file = CACHE / f"{key}.json"
    if file.exists():
        return json.loads(file.read_text())
    if offline:
        raise ModisError(f"offline and not cached: {url}")
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json",
                                                       "User-Agent": "eva-trend-detective/0.1"})
            with urllib.request.urlopen(req, timeout=180) as r:
                data = json.loads(r.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < 4:
                time.sleep(10 * (attempt + 1))
                continue
            raise ModisError(f"MODIS {e.code} for {url}") from e
        except (urllib.error.URLError, TimeoutError):
            if attempt == 4:
                raise
            time.sleep(10 * (attempt + 1))
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps(data))
    return data


def _subset(product: str, band: str, lat: float, lon: float, start: int, end: int, km: int = WINDOW_KM,
            offline: bool = False) -> dict:
    """``{year: [pixel values]}`` of a yearly product over the window (raw integers)."""
    out: dict = {}
    for y0 in range(start, end + 1, 10):  # at most 10 dates a request
        y1 = min(end, y0 + 9)
        d = _get(f"{product}/subset", {"latitude": round(lat, 4), "longitude": round(lon, 4), "band": band,
                                       "startDate": f"A{y0}001", "endDate": f"A{y1}365",
                                       "kmAboveBelow": km, "kmLeftRight": km}, offline=offline)
        for s in d.get("subset", []):
            out[int(s["calendar_date"][:4])] = s["data"]
    return out


def npp(lat: float, lon: float, start: int = 2001, end: int = 2025, offline: bool = False) -> dict:
    """Yearly net primary productivity (kg C / m² / year): the mean of the valid vegetated pixels
    of the window, and the share of the window they cover."""
    raw = _subset("MOD17A3HGF", "Npp_500m", lat, lon, start, end, offline=offline)
    out = {}
    for y, px in sorted(raw.items()):
        ok = [v * 1e-4 for v in px if -30000 <= v <= 32700]  # 32761-32767: water, barren, urban, fill
        if ok and len(ok) >= 0.2 * len(px):
            out[y] = {"npp": sum(ok) / len(ok), "share": len(ok) / len(px)}
    return out


def land_cover(lat: float, lon: float, years=(2001, 2023), offline: bool = False) -> dict:
    """Share of the window in cropland (cropland mosaics count half), forest, savanna/grass and
    water, for each year asked."""
    out = {}
    for y in years:
        d = _get("MCD12Q1/subset", {"latitude": round(lat, 4), "longitude": round(lon, 4), "band": "LC_Type1",
                                    "startDate": f"A{y}001", "endDate": f"A{y}365",
                                    "kmAboveBelow": WINDOW_KM, "kmLeftRight": WINDOW_KM}, offline=offline)
        sub = d.get("subset") or []
        if not sub:
            continue
        px = [v for v in sub[0]["data"] if 1 <= v <= 17]
        if not px:
            continue
        n = len(px)
        out[y] = {"cropland": (sum(1 for v in px if v == 12) + 0.5 * sum(1 for v in px if v == 14)) / n,
                  "forest": sum(1 for v in px if v in FOREST) / n,
                  "savanna_grass": sum(1 for v in px if v in (8, 9, 10)) / n,
                  "water": sum(1 for v in px if v == 17) / n,
                  "barren": sum(1 for v in px if v == 16) / n}
    return out


def fetch_points(points: list[tuple[float, float]], workers: int = 4, offline: bool = False, log=print,
                 what: str = "all", lc_years=(2001, 2024)) -> dict:
    """``what`` at every point, a few requests at a time: ``{(lat, lon): {...}}``. ``what`` is
    ``"npp"``, ``"cover"`` or ``"all"``; a point that fails carries ``"error"``."""
    def one(p):
        la, lo = p
        r: dict = {}
        try:
            if what in ("all", "npp"):
                r["npp"] = npp(la, lo, offline=offline)
            if what in ("all", "cover"):
                r["cover"] = land_cover(la, lo, lc_years, offline=offline)
        except (ModisError, OSError) as e:
            r["error"] = str(e)
        return p, r

    out, done = {}, 0
    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        for p, r in ex.map(one, points):
            out[p] = r
            done += 1
            if done % 20 == 0 or done == len(points):
                log(f"  MODIS {what} {done}/{len(points)} points")
    return out
