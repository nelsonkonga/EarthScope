"""Mining and the land in East Cameroon (Lom-Kadéï gold belt): the data.

Where is mining transforming the land, how fast, and where will it spread? The layers the
question needs over ``AREA``: raw rasters in ``data/earth/cache/mining`` (re-downloadable,
git-ignored), small tables and vectors in ``data/earth/mining``.

Change through time
- ``hansen``: Global Forest Change v1.13 (Hansen et al. 2013, UMD; Landsat), 30 m: tree cover
  in 2000, year of loss 2001-2025, land/water mask.
- ``gsw``: JRC Global Surface Water v1.4 (Pekel et al. 2016; Landsat 1984-2021), 30 m: water
  occurrence, change, seasonality, transitions (new seasonal / permanent water: flooded pits,
  diverted channels).
- ``appeears`` (NASA LP DAAC, asynchronous): MODIS NDVI 250 m / 16 days, land cover 500 m /
  year, day land surface temperature 1 km / 8 days, 2000-2025.
Where, and what drives it
- ``mrds``: USGS Mineral Resources Data System, every Cameroon record.
- ``polygons``: global mining polygons v2 (Maus et al. 2022, PANGAEA 942325), Cameroon.
- ``dem``: NASA SRTM 1 arc-second (LP DAAC, Earthdata bearer token).
- ``worldpop``: WorldPop population counts, 1 km (the 100 m files are 250 MB each, no range requests), 2000-2020.
- ``osm``: OpenStreetMap rivers, roads and tracks, settlements, mapped mines (Overpass).

    python -m detective.mining fetch [--only hansen,gsw,...]
    python -m detective.mining appeears        # status of the MODIS request; downloads it when done
    python -m detective.mining summary
"""

from __future__ import annotations

import base64
import csv
import json
import math
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

from .regions import Region

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "earth" / "cache" / "mining"
OUT = ROOT / "data" / "earth" / "mining"
UA = "eva-trend-detective/0.1 (kariskam222@gmail.com)"

AREA = Region("lom_kadei", "Lom-Kadéï gold belt (East Cameroon)", 3.9, 6.1, 13.5, 15.3,
              "Artisanal and semi-mechanised gold mining along the Lom, Kadéï and Doumé rivers.",
              country="CMR")
CAMEROON = Region("cameroon_box", "Cameroon", 1.6, 13.1, 8.4, 16.2, country="CMR")

# OpenStreetMap (Nominatim) positions, checked 2026-11-15
SITES = {
    "Bétaré-Oya": (5.5885, 14.0864), "Garoua-Boulaï": (5.8948, 14.5472), "Colomine": (4.9993, 14.3722),
    "Ngoura": (4.8777, 14.2438), "Kétté": (4.8960, 14.5432), "Batouri": (4.4356, 14.3647),
    "Kambélé": (4.4661, 14.4231), "Bertoua": (4.5776, 13.6844), "Ndélélé": (4.0419, 14.9282),
    "Kentzou": (4.1735, 15.0316),
}

HANSEN = ("https://storage.googleapis.com/earthenginepartners-hansen/GFC-2025-v1.13/"
          "Hansen_GFC-2025-v1.13_{layer}_10N_010E.tif")  # tile 0-10°N, 10-20°E
GSW = ("https://storage.googleapis.com/global-surface-water/downloads2021/{layer}/"
       "{layer}_10E_10Nv1_4_2021.tif")
GSW_TRANSITIONS = {1: "permanent", 2: "new permanent", 3: "lost permanent", 4: "seasonal", 5: "new seasonal",
                   6: "lost seasonal", 7: "seasonal to permanent", 8: "permanent to seasonal",
                   9: "ephemeral permanent", 10: "ephemeral seasonal"}
MAUS = "https://download.pangaea.de/dataset/942325/files/global_mining_polygons_v2.gpkg"
MRDS_WFS = "https://mrdata.usgs.gov/services/wfs/mrds"
WORLDPOP = ("https://data.worldpop.org/GIS/Population/Global_2000_2020_1km/{y}/CMR/"
            "cmr_ppp_{y}_1km_Aggregated.tif")
APPEEARS = "https://appeears.earthdatacloud.nasa.gov/api"
OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.private.coffee/api/interpreter",
            "https://maps.mail.ru/osm/tools/overpass/api/interpreter"]


class MiningDataError(RuntimeError):
    pass


def _bounds(r: Region = AREA) -> tuple[float, float, float, float]:
    return r.west, r.south, r.east, r.north


def _env():
    import rasterio
    return rasterio.Env(GDAL_HTTP_MAX_RETRY=5, GDAL_HTTP_RETRY_DELAY=3, GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
                        GDAL_HTTP_USERAGENT=UA)


def _write(path: Path, arr: np.ndarray, transform, crs, nodata=None, descriptions=None) -> Path:
    import rasterio
    arr = arr if arr.ndim == 3 else arr[None]
    prof = {"driver": "GTiff", "width": arr.shape[2], "height": arr.shape[1], "count": arr.shape[0],
            "dtype": arr.dtype, "crs": crs, "transform": transform, "nodata": nodata,
            "compress": "deflate", "tiled": True, "blockxsize": 512, "blockysize": 512}
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part.tif")
    with rasterio.open(tmp, "w", **prof) as ds:
        ds.write(arr)
        for i, d in enumerate(descriptions or [], 1):
            ds.set_band_description(i, d)
    tmp.replace(path)
    return path


def _window(url: str, region: Region = AREA, out: Path | None = None, log=print) -> Path:
    """Read only the region's window of a remote GeoTIFF (HTTP range requests) and save it."""
    import rasterio
    from rasterio.windows import from_bounds
    if out is not None and out.exists():
        return out
    with _env(), rasterio.open("/vsicurl/" + url) as ds:
        b = ds.bounds
        if not (b.left <= region.west and region.east <= b.right and b.bottom <= region.south and region.north <= b.top):
            raise MiningDataError(f"{url} ({b}) does not hold {region.name}")
        w = from_bounds(*_bounds(region), ds.transform).round_offsets().round_lengths()
        arr = ds.read(1, window=w)
        log(f"  {url.rsplit('/', 1)[-1]}: {arr.shape[1]} x {arr.shape[0]} px")
        return _write(out, arr, ds.window_transform(w), ds.crs, ds.nodata)


def _get(url: str, data: bytes | None = None, headers: dict | None = None, timeout: float = 300,
         tries: int = 4) -> bytes:
    h = {"User-Agent": UA, **(headers or {})}
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=h), timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < tries - 1:
                time.sleep(10 * (attempt + 1))
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == tries - 1:
                raise
            time.sleep(10 * (attempt + 1))
    raise MiningDataError(f"no answer from {url}")


def _token() -> str:
    env = ROOT / ".env"
    for line in env.read_text().splitlines() if env.exists() else []:
        if line.startswith("EARTHDATA_TOKEN="):
            return line.split("=", 1)[1].strip()
    raise MiningDataError("no EARTHDATA_TOKEN in .env (urs.earthdata.nasa.gov, Generate Token)")


# ------------------------------------------------------------------ change through time
def fetch_hansen(log=print) -> list[Path]:
    return [_window(HANSEN.format(layer=k), out=RAW / f"hansen_{k}.tif", log=log)
            for k in ("treecover2000", "lossyear", "datamask")]


def fetch_gsw(log=print) -> list[Path]:
    return [_window(GSW.format(layer=k), out=RAW / f"gsw_{k}.tif", log=log)
            for k in ("occurrence", "change", "seasonality", "transitions")]


# ------------------------------------------------------------------ where, and drivers
def fetch_mrds(log=print) -> Path:
    """Every MRDS record in Cameroon (FIPS code ``CM``), with its commodities (``code_list``)."""
    out = OUT / "mrds_cameroon.csv"
    if out.exists():
        return out
    q = {"service": "WFS", "version": "1.0.0", "request": "GetFeature", "typeName": "mrds",
         "bbox": f"{CAMEROON.west},{CAMEROON.south},{CAMEROON.east},{CAMEROON.north}"}
    root = ET.fromstring(_get(MRDS_WFS + "?" + urllib.parse.urlencode(q)))
    rows = []
    for fm in root.iter("{http://www.opengis.net/gml}featureMember"):
        rec = next(iter(fm))
        row = {}
        for child in rec:
            tag = child.tag.split("}")[-1]
            if tag == "boundedBy":
                continue
            if tag == "geometry":
                pos = child.find(".//{http://www.opengis.net/gml}coordinates")
                lon, lat = pos.text.split(",")[:2]
                row["lon"], row["lat"] = float(lon), float(lat)
            else:
                row[tag] = (child.text or "").strip()
        if "lat" in row and row.get("fips_code", "").endswith("CM"):
            rows.append(row)
    if not rows:
        raise MiningDataError("MRDS returned no record over Cameroon")
    keys = sorted({k for r in rows for k in r}, key=lambda k: (k not in ("lat", "lon", "site_name", "dep_id"), k))
    OUT.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    log(f"  MRDS: {len(rows)} records in Cameroon")
    return out


def _gpkg_geometry(blob: bytes):
    """GeoPackage binary -> shapely geometry (header: 'GP', version, flags, srs id, envelope)."""
    import shapely
    env = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}[(blob[3] >> 1) & 0b111]
    return shapely.from_wkb(blob[8 + env:])


def fetch_polygons(log=print) -> Path:
    """Maus et al. (2022) mining polygons that touch Cameroon's box, as GeoJSON."""
    import shapely
    out = OUT / "mining_polygons_maus2022_cameroon.geojson"
    if out.exists():
        return out
    gpkg = RAW / "global_mining_polygons_v2.gpkg"
    if not gpkg.exists():
        RAW.mkdir(parents=True, exist_ok=True)
        gpkg.write_bytes(_get(MAUS, timeout=600))
    con = sqlite3.connect(gpkg)
    table, = con.execute("select table_name from gpkg_contents where data_type='features'").fetchone()
    gcol, = con.execute("select column_name from gpkg_geometry_columns where table_name=?", (table,)).fetchone()
    cols = [r[1] for r in con.execute(f'pragma table_info("{table}")')]
    box = shapely.box(*_bounds(CAMEROON))
    feats = []
    for row in con.execute(f'select * from "{table}"'):
        rec = dict(zip(cols, row))
        g = _gpkg_geometry(rec.pop(gcol))
        if g.intersects(box):
            props = {k: v for k, v in rec.items() if isinstance(v, (str, int, float)) or v is None}
            feats.append({"type": "Feature", "properties": props, "geometry": shapely.geometry.mapping(g)})
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
    log(f"  Maus 2022: {len(feats)} mining polygons in Cameroon's box")
    return out


def fetch_dem(log=print) -> Path:
    """NASA SRTM 1 arc-second over the area: the tiles from LP DAAC, merged and cut."""
    import rasterio
    from rasterio.merge import merge
    out = RAW / "srtm_dem.tif"
    if out.exists():
        return out
    q = {"short_name": "SRTMGL1", "version": "003", "page_size": 50,
         "bounding_box": ",".join(map(str, _bounds()))}
    feed = json.loads(_get("https://cmr.earthdata.nasa.gov/search/granules.json?" + urllib.parse.urlencode(q)))
    urls = [next(l["href"] for l in e["links"] if l["href"].startswith("https") and l["href"].endswith(".zip"))
            for e in feed["feed"]["entry"]]
    files = []
    for u in urls:
        f = RAW / "srtm" / u.rsplit("/", 1)[-1]
        if not f.exists():
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(_get(u, headers={"Authorization": f"Bearer {_token()}"}, timeout=600))
        files.append(f)
    log(f"  SRTM: {len(files)} tiles")
    with _env():
        srcs = [rasterio.open(f"/vsizip/{f}/{f.name.split('.')[0]}.hgt") for f in files]
        arr, tr = merge(srcs, bounds=_bounds(), nodata=-32768)
        crs = srcs[0].crs
        for s in srcs:
            s.close()
    return _write(out, arr[0], tr, crs, -32768)


def fetch_worldpop(log=print) -> Path:
    """WorldPop population counts (1 km), one band a year 2000-2020, over the area."""
    import rasterio
    out = RAW / "worldpop_2000_2020.tif"
    if out.exists():
        return out
    from rasterio.windows import from_bounds
    bands, desc, ref = [], [], None
    for y in range(2000, 2021):
        f = RAW / "worldpop" / f"cmr_ppp_{y}_1km.tif"  # the whole country: the server refuses range reads
        if not f.exists():
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(_get(WORLDPOP.format(y=y)))
        with rasterio.open(f) as ds:
            w = from_bounds(*_bounds(), ds.transform).round_offsets().round_lengths()
            bands.append(ds.read(1, window=w))
            ref = ref or (ds.window_transform(w), ds.crs, ds.nodata)
        desc.append(f"population {y}")
    log(f"  WorldPop: {len(bands)} years, {bands[0].shape[1]} x {bands[0].shape[0]} px")
    return _write(out, np.stack(bands), ref[0], ref[1], ref[2], desc)


OSM_QUERIES = {
    "mines": 'nwr["landuse"="quarry"]({b});nwr["industrial"="mine"]({b});nwr["man_made"~"^(mineshaft|adit)$"]({b});'
             'nwr["resource"]({b});nwr["landuse"="industrial"]["industrial"="mine"]({b});',
    "rivers": 'way["waterway"~"^(river|stream|canal)$"]({b});',
    "roads": 'way["highway"~"^(trunk|primary|secondary|tertiary|unclassified|residential|track|path)$"]({b});',
    "places": 'node["place"~"^(city|town|village|hamlet|isolated_dwelling)$"]({b});',
}


def _overpass(body: str, log=print) -> dict:
    last = None
    for attempt in range(3):
        for url in OVERPASS:
            try:
                return json.loads(_get(url, data=urllib.parse.urlencode({"data": body}).encode(), timeout=400, tries=1))
            except Exception as e:  # noqa: BLE001 — every mirror can be down; try the next
                last = e
                log(f"    {url.split('/')[2]}: {str(e)[:60]}")
        time.sleep(30 * (attempt + 1))
    raise MiningDataError(f"Overpass unreachable: {last}")


def fetch_osm(log=print) -> list[Path]:
    """OpenStreetMap layers as GeoJSON (ways as lines, or polygons when closed)."""
    outs = []
    b = f"{AREA.south},{AREA.west},{AREA.north},{AREA.east}"
    for name, q in OSM_QUERIES.items():
        out = OUT / f"osm_{name}.geojson"
        outs.append(out)
        if out.exists():
            continue
        d = _overpass(f"[out:json][timeout:300];({q.format(b=b)});out geom tags;", log)
        feats = []
        for e in d["elements"]:
            if e["type"] == "node":
                geom = {"type": "Point", "coordinates": [e["lon"], e["lat"]]}
            elif "geometry" in e:
                pts = [[p["lon"], p["lat"]] for p in e["geometry"] if p]
                closed = len(pts) > 3 and pts[0] == pts[-1] and name == "mines"
                geom = {"type": "Polygon", "coordinates": [pts]} if closed else {"type": "LineString", "coordinates": pts}
            elif "center" in e or "bounds" in e:
                c = e.get("center") or {"lat": (e["bounds"]["minlat"] + e["bounds"]["maxlat"]) / 2,
                                        "lon": (e["bounds"]["minlon"] + e["bounds"]["maxlon"]) / 2}
                geom = {"type": "Point", "coordinates": [c["lon"], c["lat"]]}
            else:
                continue
            feats.append({"type": "Feature", "properties": {"osm": f"{e['type']}/{e['id']}", **e.get("tags", {})},
                          "geometry": geom})
        OUT.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
        log(f"  OSM {name}: {len(feats)} features")
    return outs


# ------------------------------------------------------------------ MODIS through AppEEARS
def _appeears_token() -> str:
    pw = next(l.split()[1] for l in (Path.home() / ".netrc").read_text().splitlines()
              if l.strip().startswith("password"))
    auth = base64.b64encode(f"kariskam_eva3:{pw}".encode()).decode()
    return json.loads(_get(APPEEARS + "/login", data=b"", headers={"Authorization": f"Basic {auth}"}))["token"]


def appeears(log=print) -> str:
    """Status of the MODIS area request (``RAW/appeears_task.json``); its files once it is done."""
    task = json.loads((RAW / "appeears_task.json").read_text())["task_id"]
    h = {"Authorization": f"Bearer {_appeears_token()}"}
    st = json.loads(_get(f"{APPEEARS}/task/{task}", headers=h))
    log(f"  AppEEARS {task}: {st['status']}" + (f" ({st.get('progress', {}).get('summary', '')}%)"
                                               if st.get("progress") else ""))
    if st["status"] != "done":
        return st["status"]
    dest = RAW / "appeears"
    files = json.loads(_get(f"{APPEEARS}/bundle/{task}", headers=h))["files"]
    for i, f in enumerate(files):
        p = dest / f["file_name"]
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(_get(f"{APPEEARS}/bundle/{task}/{f['file_id']}", headers=h, timeout=600))
        if (i + 1) % 200 == 0:
            log(f"    {i + 1}/{len(files)} files")
    log(f"  AppEEARS: {len(files)} files in {dest}")
    return "done"


FETCHERS = {"hansen": fetch_hansen, "gsw": fetch_gsw, "mrds": fetch_mrds, "polygons": fetch_polygons,
            "dem": fetch_dem, "worldpop": fetch_worldpop, "osm": fetch_osm}


# ------------------------------------------------------------------ first look
def _pixel_km2(transform, rows: int) -> np.ndarray:
    """Area of a pixel (km²) for each row of a geographic grid."""
    lat = transform.f + transform.e * (np.arange(rows) + 0.5)
    return (abs(transform.a) * 111.32) * (abs(transform.e) * 110.57) * np.cos(np.radians(lat))


DAM_WEST = 14.0  # west of this the Lom Pangar reservoir (filled 2015-2016) makes most of the new water


def _count_in_area(path: Path) -> int:
    import shapely
    if not path.exists():
        return 0
    box = shapely.box(*_bounds())
    return sum(1 for f in json.loads(path.read_text())["features"]
               if shapely.geometry.shape(f["geometry"]).intersects(box))


def summary(log=print) -> dict:
    """Does mining show? Forest loss within 1 km of water, east of the reservoir valley, against
    the share of land that lies there (chance); its trend and break year; the new water."""
    import rasterio
    from scipy import ndimage

    from . import stats
    out: dict = {"area": AREA.as_dict(), "dam_west": DAM_WEST}
    with rasterio.open(RAW / "hansen_lossyear.tif") as ds:
        loss, tr = ds.read(1), ds.transform
    with rasterio.open(RAW / "hansen_treecover2000.tif") as ds:
        tc = ds.read(1)
    with rasterio.open(RAW / "hansen_datamask.tif") as ds:
        land = ds.read(1) == 1
    with rasterio.open(RAW / "gsw_occurrence.tif") as ds:
        occ = ds.read(1)
    with rasterio.open(RAW / "gsw_transitions.tif") as ds:
        trans = ds.read(1)
    px = _pixel_km2(tr, loss.shape[0])[:, None]
    lon = tr.c + tr.a * (np.arange(loss.shape[1]) + 0.5)
    east = np.broadcast_to(lon >= DAM_WEST, loss.shape)
    out["forest_2000_km2"] = float((px * (land & (tc >= 30))).sum())
    water = (occ > 0) & (occ <= 100)
    near = ndimage.distance_transform_edt(~water, sampling=(abs(tr.e) * 110.57, abs(tr.a) * 111.32 * math.cos(
        math.radians((AREA.south + AREA.north) / 2)))) <= 1.0
    chance = float((px * (land & near & east)).sum() / (px * (land & east)).sum())
    out["east_land_within_1km_of_water"] = chance
    years, ratio = {}, []
    for k in range(1, int(loss.max()) + 1):
        m = loss == k
        tot, me = float((px * m).sum()), m & east
        te, ne = float((px * me).sum()), float((px * (me & near)).sum())
        r = (ne / te) / chance if te else float("nan")
        years[2000 + k] = {"loss_km2": tot, "east_loss_km2": te, "east_near_water_km2": ne, "near_water_ratio": r}
        ratio.append(r)
    out["loss_by_year"] = years
    # the ratio is a share within each year: it does not move when Hansen's detection improves (2013+)
    mk, pt = stats.mann_kendall(ratio), stats.pettitt(ratio)
    yrs = sorted(years)
    out["near_water_ratio_trend"] = {"mann_kendall_p": mk["p"], "tau": mk["tau"], "pettitt_p": pt["p"],
                                     "break_year": yrs[pt["at"]] if pt["at"] is not None else None,
                                     "before": pt.get("before"), "after": pt.get("after")}
    newer = {c: trans == c for c in (2, 5)}
    out["new_water_km2"] = {GSW_TRANSITIONS[c]: {"all": float((px * m).sum()), "east": float((px * (m & east)).sum())}
                            for c, m in newer.items()}
    out["mapped_in_area"] = {"maus2022_polygons": _count_in_area(OUT / "mining_polygons_maus2022_cameroon.geojson"),
                             "osm_mines": _count_in_area(OUT / "osm_mines.geojson")}
    if (OUT / "mrds_cameroon.csv").exists():
        rows = list(csv.DictReader((OUT / "mrds_cameroon.csv").open()))
        out["mapped_in_area"]["mrds"] = sum(1 for r in rows if AREA.south <= float(r["lat"]) <= AREA.north
                                            and AREA.west <= float(r["lon"]) <= AREA.east)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    log(f"Forest (tree cover >= 30 %) in 2000: {out['forest_2000_km2']:,.0f} km². East of {DAM_WEST}°E, "
        f"{100 * chance:.1f} % of the land lies within 1 km of water (chance).")
    log("year  loss km²  east km²  east near water: x chance")
    for y, v in years.items():
        log(f"{y}  {v['loss_km2']:8.1f}  {v['east_loss_km2']:8.1f}  x{v['near_water_ratio']:.2f}")
    t = out["near_water_ratio_trend"]
    log(f"Near-water ratio: Mann-Kendall p = {t['mann_kendall_p']:.3g} (tau {t['tau']:+.2f}); Pettitt break "
        f"{t['break_year']} (p = {t['pettitt_p']:.3g}): x{t['before']:.2f} before, x{t['after']:.2f} after")
    log("New water since 1984 (km², all / east): " + ", ".join(
        f"{k} {v['all']:.1f} / {v['east']:.1f}" for k, v in out["new_water_km2"].items()))
    log(f"Mapped in the area: {out['mapped_in_area']}")
    return out


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="detective.mining", description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=["fetch", "appeears", "summary"])
    ap.add_argument("--only", default=",".join(FETCHERS))
    args = ap.parse_args(argv)
    if args.cmd == "appeears":
        appeears()
    elif args.cmd == "summary":
        summary()
    else:
        failed = []
        for name in args.only.split(","):
            print(f"{name} ...", flush=True)
            try:
                FETCHERS[name]()
            except Exception as e:  # noqa: BLE001 — one source down must not stop the others
                failed.append(name)
                print(f"  FAILED {name}: {e}", flush=True)
        if failed:
            print("failed: " + ",".join(failed))
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
