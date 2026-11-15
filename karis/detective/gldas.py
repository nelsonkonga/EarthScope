"""GLDAS-NOAH025_M (GES DISC, OPeNDAP): monthly land-surface model output, 0.25 degree.

Earthdata Login is required for the actual values (unlike NASA POWER); ``.netrc`` basic auth
is rejected by the GES DISC cloud gateway (401), a Bearer token in the Authorization header
works. Set ``EARTHDATA_TOKEN`` (and ``EARTHDATA_USERNAME``, unused by the request itself but
kept for reference) in ``.env``.

Two product versions, not interchangeable (different forcing, different production run):
GLDAS_NOAH025_M 2.0 (Princeton forcing) 1948-01 to 2014-12, and 2.1 (NOAA GDAS forcing)
2000-01 to near-present. Same variable names in both.

One GET per month fetches every requested variable at once, subset to the region's grid
cells (OPeNDAP ``.ascii`` with index constraints) — a few KB instead of the ~25 MB full
granule. Every response is cached on disk (``data/earth/cache/gldas``).
"""

from __future__ import annotations

import math
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

from .regions import Region

CACHE = Path(__file__).resolve().parents[1] / "data" / "earth" / "cache" / "gldas"
FILL = -9999.0
GRID = 0.25  # degrees, both versions

COLLECTIONS = {
    "2.0": ("C1233767569-GES_DISC", "020", 1948, 2014),
    "2.1": ("C1342986036-GES_DISC", "021", 2000, None),  # None end = near-present, probed
}

# key -> (GLDAS variable name, units, what it is)
VARIABLES = {
    "soil_top": ("SoilMoi0_10cm_inst", "kg/m^2", "Soil moisture, 0-10 cm"),
    "soil_root": ("SoilMoi10_40cm_inst", "kg/m^2", "Soil moisture, 10-40 cm (root zone)"),
    "rain": ("Rainf_f_tavg", "kg/m^2/s", "Precipitation (observation-corrected forcing)"),
    "surf_temp": ("AvgSurfT_inst", "K", "Surface (skin) temperature"),
    "evap": ("Evap_tavg", "kg/m^2/s", "Evapotranspiration (soil, canopy, transpiration)"),
    "runoff": ("Qs_acc", "kg/m^2", "Surface runoff, accumulated over the month"),
    "pet": ("PotEvap_tavg", "W/m^2", "Potential evapotranspiration"),
    "albedo": ("Albedo_inst", "%", "Surface albedo"),
}


class GldasError(RuntimeError):
    pass


def _token() -> str:
    t = os.environ.get("EARTHDATA_TOKEN")
    if not t:
        raise GldasError("EARTHDATA_TOKEN is not set (see .env)")
    return t


def _index(region: Region) -> tuple[int, int, int, int]:
    """(lat_i0, lat_i1, lon_j0, lon_j1), inclusive, on GLDAS' 0.25 deg grid (lat -60..90,
    lon -180..180)."""
    i0 = round((region.south + 60) / GRID)
    i1 = round((region.north + 60) / GRID)
    j0 = round((region.west + 180) / GRID)
    j1 = round((region.east + 180) / GRID)
    return i0, i1, j0, j1


def _granule_url(version: str, year: int, month: int, keys: list[str], region: Region) -> str:
    coll, suffix, _first, _last = COLLECTIONS[version]
    i0, i1, j0, j1 = _index(region)
    fname = f"GLDAS_NOAH025_M.A{year:04d}{month:02d}.{suffix}.nc4"
    parts = []
    for k in keys:
        var, _u, _d = VARIABLES[k]
        parts.append(f"{var}%5B0:1:0%5D%5B{i0}:1:{i1}%5D%5B{j0}:1:{j1}%5D")
    parts.append(f"lat%5B{i0}:1:{i1}%5D")
    parts.append(f"lon%5B{j0}:1:{j1}%5D")
    constraint = ",".join(parts)
    return (f"https://opendap.earthdata.nasa.gov/collections/{coll}/granules/"
            f"GLDAS_NOAH025_M.{version}:{fname}.ascii?{constraint}")


def _fetch_raw(version: str, year: int, month: int, keys: list[str], region: Region,
                offline: bool = False) -> str | None:
    cache_key = f"{version}_{year:04d}{month:02d}_{region.key}_{'-'.join(sorted(keys))}.txt"
    file = CACHE / cache_key
    if file.exists():
        text = file.read_text()
        return None if text == "__MISSING__" else text
    if offline:
        raise GldasError(f"offline and not cached: {cache_key}")
    url = _granule_url(version, year, month, keys, region)
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {_token()}"})
    text = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                text = r.read().decode()
            break
        except urllib.error.HTTPError as e:
            if e.code == 404:  # granule does not exist (before launch / after last update)
                text = None
                break
            if e.code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(3 * (attempt + 1))
                continue
            raise GldasError(f"GLDAS {e.code} for {year}-{month:02d} ({version}): "
                              f"{e.read().decode()[:300]}") from e
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
            if attempt == 3:
                raise
            time.sleep(3 * (attempt + 1))
    CACHE.mkdir(parents=True, exist_ok=True)
    file.write_text("__MISSING__" if text is None else text)
    return text


_ROW = re.compile(r'^(\w+)\.\1\[\1\.time=[^\]]+\]\[\1\.lat=([^\]]+)\], (.*)$', re.M)


def _parse(text: str, keys: list[str]) -> dict[str, float | None]:
    """Area mean (cos-latitude weighted) per variable key, ignoring fill values."""
    out: dict[str, float | None] = {}
    by_var: dict[str, list[tuple[float, list[float]]]] = {}
    for m in _ROW.finditer(text):
        var, lat, rest = m.group(1), float(m.group(2)), m.group(3)
        vals = [float(x) for x in rest.split(",")]
        by_var.setdefault(var, []).append((lat, vals))
    for k in keys:
        var, _u, _d = VARIABLES[k]
        rows = by_var.get(var)
        if not rows:
            out[k] = None
            continue
        num = den = 0.0
        for lat, vals in rows:
            w = math.cos(math.radians(lat))
            for v in vals:
                if v <= FILL + 1e-6:
                    continue
                num += w * v
                den += w
        out[k] = (num / den) if den > 0 else None
    return out


def monthly_series(keys: list[str], region: Region, offline: bool = False,
                    progress: bool = True) -> dict[str, dict[str, dict[tuple[int, int], float | None]]]:
    """``{version: {key: {(year, month): value}}}`` for every month either GLDAS version
    covers, over the region's area mean. ``.0`` and ``.1`` stay separate (see module
    docstring): do not splice them into one series without saying so."""
    out: dict[str, dict[str, dict]] = {}
    for version, (_coll, _suf, first, last) in COLLECTIONS.items():
        end_year = last or (time.gmtime().tm_year)
        series: dict[str, dict] = {k: {} for k in keys}
        months = [(y, m) for y in range(first, end_year + 1) for m in range(1, 13)
                  if not (last is None and y == end_year and m > time.gmtime().tm_mon)]
        for y, m in months:
            text = _fetch_raw(version, y, m, keys, region, offline=offline)
            if text is not None:
                vals = _parse(text, keys)
                for k in keys:
                    series[k][(y, m)] = vals.get(k)
            if progress:
                print(f"\r  GLDAS {version} {y}-{m:02d}", end="", flush=True)
        if progress:
            print()
        out[version] = series
    return out
