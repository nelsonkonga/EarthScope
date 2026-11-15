"""Where a cell is on the ground: its country (or countries, for a cell across a border) and its
nearest town, from Natural Earth (public domain, naturalearthdata.com).

The 1:10 m countries and populated places are downloaded once into ``data/earth/cache/naturalearth``;
what a region needs (the countries and towns around its box) is kept in ``data/earth/places.json``,
small enough to travel with the results.

    country_shares(lat, lon, dlat, dlon)   -> [("CMR", "Cameroon", 0.62), ("NGA", "Nigeria", 0.38)]
    nearest_town(lat, lon)                 -> ("Garoua", "Cameroon", 23.4)  (km)
"""

from __future__ import annotations

import json
import math
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "data" / "earth"
CACHE = ROOT / "cache" / "naturalearth"
STORE = ROOT / "places.json"
URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/{}"
COUNTRIES, TOWNS = "ne_10m_admin_0_countries.geojson", "ne_10m_populated_places_simple.geojson"
SAMPLES = 6  # a cell's share of a country: SAMPLES x SAMPLES points spread over it


def _source(name: str) -> dict:
    f = CACHE / name
    if not f.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(URL.format(name), timeout=120) as r:  # noqa: S310 (fixed https URL)
            f.write_bytes(r.read())
    return json.loads(f.read_text(encoding="utf-8"))


def _bbox(rings) -> list[float]:
    xs = [p[0] for ring in rings for p in ring]
    ys = [p[1] for ring in rings for p in ring]
    return [min(xs), min(ys), max(xs), max(ys)]


def _store() -> dict:
    return json.loads(STORE.read_text(encoding="utf-8")) if STORE.exists() else {"boxes": [], "countries": {}, "towns": []}


def ensure(south: float, north: float, west: float, east: float, pad: float = 3.0) -> dict:
    """The countries and towns around a box, extracted once from Natural Earth into ``places.json``."""
    st = _store()
    box = [south - pad, north + pad, west - pad, east + pad]
    if any(b[0] <= box[0] and b[1] >= box[1] and b[2] <= box[2] and b[3] >= box[3] for b in st["boxes"]):
        return st
    s, n, w, e = box
    for f in _source(COUNTRIES)["features"]:
        p, g = f["properties"], f["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        keep = [[[[round(x, 4), round(y, 4)] for x, y in ring] for ring in poly] for poly in polys
                if (lambda b: b[0] <= e and b[2] >= w and b[1] <= n and b[3] >= s)(_bbox(poly))]
        if keep:
            iso = p["ADM0_A3"]
            old = st["countries"].get(iso, {"name": p["NAME"], "polys": []})
            seen = {json.dumps(q[0][:3]) for q in old["polys"]}
            old["polys"] += [q for q in keep if json.dumps(q[0][:3]) not in seen]
            st["countries"][iso] = old
    have = {(t[0], t[1], t[2]) for t in st["towns"]}
    for f in _source(TOWNS)["features"]:
        p = f["properties"]
        la, lo = p["latitude"], p["longitude"]
        if s <= la <= n and w <= lo <= e and (p["name"], la, lo) not in have:
            st["towns"].append([p["name"], la, lo, p["pop_max"], p["adm0_a3"]])
    st["boxes"].append(box)
    STORE.write_text(json.dumps(st, separators=(",", ":")), encoding="utf-8")
    return st


def _inside(x: float, y: float, poly) -> bool:
    """Ray casting; a polygon is its outer ring then its holes."""
    def ring_in(ring):
        c = False
        for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
            if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                c = not c
        return c
    return ring_in(poly[0]) and not any(ring_in(h) for h in poly[1:])


class Places:
    def __init__(self, south: float, north: float, west: float, east: float):
        st = ensure(south, north, west, east)
        self.countries = {iso: (c["name"], [(p, _bbox(p)) for p in c["polys"]]) for iso, c in st["countries"].items()}
        self.towns = st["towns"]

    def country_at(self, lat: float, lon: float) -> str | None:
        for iso, (_name, polys) in self.countries.items():
            for p, b in polys:
                if b[0] <= lon <= b[2] and b[1] <= lat <= b[3] and _inside(lon, lat, p):
                    return iso
        return None

    def country_shares(self, lat: float, lon: float, dlat: float, dlon: float) -> list[tuple[str, str, float]]:
        """The countries a cell covers, largest share first (the sea and lakes are left out)."""
        n, k = {}, SAMPLES
        for i in range(k):
            for j in range(k):
                iso = self.country_at(lat - dlat / 2 + (i + .5) * dlat / k, lon - dlon / 2 + (j + .5) * dlon / k)
                if iso:
                    n[iso] = n.get(iso, 0) + 1
        return sorted(((iso, self.countries[iso][0], c / k / k) for iso, c in n.items()), key=lambda x: -x[2])

    def nearest_town(self, lat: float, lon: float) -> tuple[str, str, float] | None:
        def km(t):
            p1, p2 = math.radians(lat), math.radians(t[1])
            a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(t[2] - lon) / 2) ** 2
            return 6371 * 2 * math.asin(math.sqrt(a))
        if not self.towns:
            return None
        t = min(self.towns, key=km)
        return t[0], (self.countries.get(t[4]) or (t[4],))[0], km(t)
