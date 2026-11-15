"""NASA POWER API: MERRA-2, GPM IMERG and CERES data for any point or region, no login.

https://power.larc.nasa.gov/docs/services/api/ — NASA Langley's "Prediction Of Worldwide
Energy Resources" project serves meteorology and land surface variables from the MERRA-2
reanalysis (NASA GMAO), precipitation from GPM IMERG and surface radiation from CERES, on
MERRA-2's grid (0.5° latitude x 0.625° longitude), as monthly means from 1981. A regional
request carries one parameter and a box of at most 10° x 10°; larger regions are tiled.

Monthly keys come back as ``YYYYMM`` (``MM`` = 13 is the annual mean, skipped here); missing
values are -999. Every answer is cached on disk (``data/earth/cache/power``).
"""

from __future__ import annotations

import hashlib
import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .regions import Region

BASE = "https://power.larc.nasa.gov/api"
CACHE = Path(__file__).resolve().parents[1] / "data" / "earth" / "cache" / "power"
FILL = -999.0
FIRST_YEAR = 1981


class PowerError(RuntimeError):
    pass


def _get(path: str, query: dict, cache: Path | None = CACHE, offline: bool = False) -> dict:
    url = f"{BASE}/{path}?{urllib.parse.urlencode(query)}"
    key = hashlib.sha1(url.encode()).hexdigest()[:24]
    file = cache / f"{key}.json" if cache is not None else None
    if file is not None and file.exists():
        return json.loads(file.read_text())
    if offline:
        raise PowerError(f"offline and not cached: {url}")
    data = None
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "eva-trend-detective/0.1"})
            with urllib.request.urlopen(req, timeout=300) as r:
                data = json.loads(r.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < 4:
                time.sleep(5 * (attempt + 1))
                continue
            try:
                msg = json.loads(e.read().decode("utf-8")).get("messages", [])
            except Exception:  # noqa: BLE001 — the error body is not always JSON
                msg = []
            raise PowerError(f"POWER {e.code} for {url}: {'; '.join(map(str, msg))}") from e
        except (urllib.error.URLError, TimeoutError):
            if attempt == 4:
                raise
            time.sleep(5 * (attempt + 1))
    if data is None or ("properties" not in data and "features" not in data and "parameters" not in data):
        raise PowerError(f"POWER gave no data for {url}: {json.dumps(data)[:300]}")
    if file is not None:
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(json.dumps(data))
    return data


def _months(values: dict) -> dict:
    """``{"YYYYMM": v}`` -> ``{(year, month): v or None}`` (annual means skipped)."""
    out = {}
    for k, v in values.items():
        y, m = int(k[:4]), int(k[4:])
        if 1 <= m <= 12:
            out[(y, m)] = None if v is None or v <= FILL + 1e-9 else float(v)
    return out


def catalog(temporal: str = "monthly", community: str = "AG", **kw) -> dict:
    """Every POWER parameter: name, units, definition, type (from the POWER parameter manager)."""
    url_path = "system/manager/parameters"
    return _get(url_path, {"community": community, "temporal": temporal}, **kw)


def monthly_point(params: list[str], lat: float, lon: float, start: int = FIRST_YEAR, end: int = 2024,
                  community: str = "AG", **kw) -> dict:
    """Monthly series at a point (the grid cell that contains it): ``{param: {(y, m): v}}``."""
    data = _get("temporal/monthly/point", {
        "parameters": ",".join(params), "community": community, "latitude": lat, "longitude": lon,
        "start": start, "end": end, "format": "JSON"}, **kw)
    return {p: _months(v) for p, v in data["properties"]["parameter"].items()}


def monthly_cells(param: str, region: Region, start: int = FIRST_YEAR, end: int = 2024, community: str = "AG",
                  **kw) -> list[tuple[float, float, dict]]:
    """Monthly series of every grid cell of a region: ``[(lat, lon, {(y, m): v})]``."""
    cells: dict = {}
    for t in region.tiles(10.0):
        data = _get("temporal/monthly/regional", {
            "parameters": param, "community": community,
            "latitude-min": round(t.south, 4), "latitude-max": round(t.north, 4),
            "longitude-min": round(t.west, 4), "longitude-max": round(t.east, 4),
            "start": start, "end": end, "format": "JSON"}, **kw)
        for f in data.get("features", []):
            lon, lat = f["geometry"]["coordinates"][:2]
            series = f["properties"]["parameter"].get(param)
            if series is not None:
                cells[(round(lat, 4), round(lon, 4))] = _months(series)  # tiles share their edges
    return [(la, lo, s) for (la, lo), s in sorted(cells.items())]


def informative(cells: list) -> list:
    """The cells whose series moves: a cell where the variable never changes (sea ice over
    land, snow over a tropical ocean) says nothing of its dynamics."""
    out = []
    for c in cells:
        vals = {v for v in c[2].values() if v is not None}
        if len(vals) > 1:
            out.append(c)
    return out


def area_mean(cells: list, min_valid: float = 0.5) -> dict:
    """Area-weighted mean (cos latitude) of the cells, month by month; a month where fewer than
    ``min_valid`` of the cells have a value is missing."""
    keys = sorted({k for _la, _lo, s in cells for k in s})
    out = {}
    for k in keys:
        num = den = 0.0
        valid = 0
        for la, _lo, s in cells:
            v = s.get(k)
            if v is None:
                continue
            w = math.cos(math.radians(la))
            num += w * v
            den += w
            valid += 1
        out[k] = num / den if cells and valid >= min_valid * len(cells) and den > 0 else None
    return out


def region_series(param: str, region: Region, start: int = FIRST_YEAR, end: int = 2024, **kw) -> tuple[dict, list]:
    """The region's monthly mean series of ``param`` and the informative cells it was made of."""
    cells = informative(monthly_cells(param, region, start, end, **kw))
    if not cells:
        raise PowerError(f"{param} never changes in {region.name}: nothing to investigate")
    return area_mean(cells), cells
