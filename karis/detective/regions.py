"""Regions: where the detective looks.

A region is a latitude / longitude box. CMR searches take it as WKT (longitude first); the
POWER API takes boxes of at most 10° x 10°, so larger regions are cut into tiles.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Region:
    key: str
    name: str
    south: float
    north: float
    west: float
    east: float
    why: str = ""  # what one might investigate there (shown to the user)
    country: str = ""  # ISO 3166 alpha-3: the land analysis keeps only the box's cells in this country

    def wkt(self) -> str:
        """The box as a WKT polygon (longitude latitude, counter-clockwise, closed)."""
        w, s, e, n = self.west, self.south, self.east, self.north
        return f"POLYGON(({w} {s}, {e} {s}, {e} {n}, {w} {n}, {w} {s}))"

    def center(self) -> tuple[float, float]:
        return (self.south + self.north) / 2, (self.west + self.east) / 2

    def tiles(self, span: float = 10.0) -> list["Region"]:
        """The box cut into tiles of at most ``span`` degrees on each side."""
        def cuts(a, b):
            n = max(1, math.ceil((b - a) / span - 1e-9))
            step = (b - a) / n
            return [(a + i * step, a + (i + 1) * step) for i in range(n)]

        return [Region(f"{self.key}#{i}", self.name, s, n, w, e)
                for i, ((s, n), (w, e)) in enumerate((la, lo) for la in cuts(self.south, self.north)
                                                     for lo in cuts(self.west, self.east))]

    def as_dict(self) -> dict:
        d = {"key": self.key, "name": self.name, "south": self.south, "north": self.north,
             "west": self.west, "east": self.east, "why": self.why}
        return {**d, "country": self.country} if self.country else d


REGIONS: dict[str, Region] = {r.key: r for r in [
    Region("barents", "Barents Sea & Svalbard", 72, 80, 20, 40,
           "The Arctic warms faster than the rest of the planet; its sea ice is retreating."),
    Region("ross", "Ross Sea (Antarctica)", -76, -66, -180, -170,
           "Antarctic sea ice grew here for decades while it shrank elsewhere."),
    Region("bellingshausen", "Bellingshausen Sea (Antarctica)", -72, -62, -90, -80,
           "The other pole of the Antarctic sea-ice dipole, west of the Antarctic Peninsula."),
    Region("sahel", "Central Sahel", 12, 18, -5, 5,
           "A semi-arid belt that lived a great drought in the 1970s–80s."),
    Region("amazon", "Central Amazon", -10, 0, -65, -55,
           "The largest rain forest: are its dry seasons getting hotter and drier?"),
    Region("west_europe", "Western Europe (France)", 43, 51, -2, 8,
           "Heat waves and droughts have hit Western Europe repeatedly since 2003."),
    Region("halley", "Antarctic ozone (Weddell Sea coast)", -80, -70, -30, -20,
           "Where the ozone hole was discovered in 1985."),
    Region("warm_pool", "Western Pacific warm pool", -5, 5, 140, 150,
           "The tropical atmosphere above the warmest ocean on Earth, from the surface to the tropopause."),
    Region("delhi", "Indo-Gangetic Plain (Delhi)", 25, 31, 74, 80,
           "One of the most populated, polluted and irrigated plains on Earth."),
    Region("cameroon", "Central Cameroon", 2, 8, 10, 16,
           "From the equatorial forest to the savanna."),
    Region("cameroon_chad", "Cameroon and the Lake Chad basin", 2, 13, 8, 16,
           "Forest, savanna and Sahel in one country: where is the land gaining or losing its growing season?"),
    Region("cameroon_full", "Cameroon", 2, 13, 8, 16.5,
           "Forest, savanna and Sahel in one country: where is the land gaining or losing its growing season?",
           country="CMR"),
    Region("west_sahel", "Western Sahel (Senegal to Niger)", 11, 17, -17, 3,
           "The Sahel's re-greening after the great droughts: does it reach the croplands?"),
]}


def parse_region(text: str) -> Region:
    """A named region (``sahel``), a box ``south,north,west,east``, or a point ``lat,lon``
    (the box of ±1° around it)."""
    t = text.strip()
    if t.lower() in REGIONS:
        return REGIONS[t.lower()]
    try:
        parts = [float(x) for x in t.replace(";", ",").split(",")]
    except ValueError:
        parts = []
    if len(parts) == 2:
        lat, lon = parts
        return Region(f"pt{lat:+.2f}{lon:+.2f}", f"Around {lat:.2f}, {lon:.2f}", lat - 1, lat + 1, lon - 1, lon + 1)
    if len(parts) == 4:
        s, n, w, e = parts
        if not (s < n and w < e):
            raise ValueError("a box is south,north,west,east with south < north and west < east")
        return Region(f"box{s:+g}{n:+g}{w:+g}{e:+g}", f"Box {s}..{n}°N, {w}..{e}°E", s, n, w, e)
    raise ValueError(f"unknown region {text!r}: a name ({', '.join(REGIONS)}), lat,lon or south,north,west,east")
