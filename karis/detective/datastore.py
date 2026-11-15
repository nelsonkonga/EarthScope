"""The NASA data the agent imports, downloaded once: the store, its ledger and the guardrail.

The agent (``agent.py``) may import data the map does not have: a NASA POWER variable over a
region or at a point (MERRA-2, CERES), GPM IMERG satellite rain at a point, MODIS plant
productivity or land cover around a point. Every import goes through this store.

What « the same data set » means here is the content, not the request: one variable of one
source at one grid cell (or one MODIS window), always over the whole record (POWER 1981-2025,
IMERG and MODIS 2001-2025). Two requests that differ only by their box, their years or their
order of variables ask for the same content, and the HTTP caches of ``power.py`` / ``modis.py``
(keyed by URL) would download it again; this store does not.

The guardrail, in order, for each (source, variable, cell) asked:
1. already in the store: read it, no network;
2. downloaded before by the detective or the land analysis (their HTTP caches, read offline):
   taken from there into the store, no network;
3. in the ledger but no longer in the store (a file deleted by hand): REFUSED, never downloaded
   again: an operator restores it (``force=True`` exists for that, the agent cannot pass it);
4. otherwise downloaded, only the missing cells (a box only where they form a full rectangle,
   one request per cell elsewhere), within a budget per import and per hour; each download is
   written to the ledger with the cells it brought.
A lock per (source, variable) makes two questions asking for the same data at the same moment
wait for one download instead of making two.

Store: ``data/earth/store/`` (``power/<VAR>.json``, ``imerg.json``, ``modis.json``,
``ledger.json``), written atomically.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import os
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "data" / "earth" / "store"
FIRST, LAST = 1981, 2025  # the whole POWER record, always: other years never mean another download
SAT_FIRST = 2001  # IMERG and MODIS
MERRA2 = (0.5, 0.625)  # grid of MERRA-2 cells: centres at multiples of the steps
CERES = (1.0, 1.0)  # CERES' 1° grid: centres at x.5
CERES_PARAMS = {"ALLSKY_SRF_ALB", "ALLSKY_SFC_SW_DWN", "CLOUD_AMT"}
MIN_BOX_CELLS = 5  # a box request needs at least this many rows and columns (POWER wants >= 2°)
MAX_CELLS = 1500  # cells of one variable in one import (about 20° x 20°)
MAX_REQUESTS = 24  # network requests in one import
PER_HOUR = {"power": 40, "imerg": 40, "modis": 8}  # network requests per hour, the whole server
MODIS_COVER_YEARS = (2001, 2024)


class GuardError(Exception):
    """A download the guardrail refuses."""


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _ym(k) -> str:
    y, m = k
    return f"{int(y)}{int(m):02d}"


def _from_ym(s: str) -> tuple[int, int]:
    return int(s[:4]), int(s[4:])


def cell_key(lat: float, lon: float) -> str:
    return f"{lat + 0.0:.3f},{lon + 0.0:.3f}".replace("-0.000", "0.000")  # POWER writes the meridian -0.0


def grid_of(param: str) -> tuple[float, float, float, float]:
    """(dlat, dlon, lat offset, lon offset) of the grid a POWER variable is served on."""
    if param in CERES_PARAMS:
        return CERES[0], CERES[1], 0.5, 0.5
    return MERRA2[0], MERRA2[1], 0.0, 0.0


def cell_of(param: str, lat: float, lon: float) -> tuple[float, float]:
    """The centre of the grid cell holding a point."""
    dla, dlo, ola, olo = grid_of(param)
    return round(round((lat - ola) / dla) * dla + ola, 4), round(round((lon - olo) / dlo) * dlo + olo, 4)


def cells_in_box(param: str, s: float, n: float, w: float, e: float) -> list[tuple[float, float]]:
    """The cell centres inside a box, edges included (what the POWER regional service returns)."""
    dla, dlo, ola, olo = grid_of(param)
    i0, i1 = math.ceil((s - ola) / dla - 1e-9), math.floor((n - ola) / dla + 1e-9)
    j0, j1 = math.ceil((w - olo) / dlo - 1e-9), math.floor((e - olo) / dlo + 1e-9)
    return [(round(i * dla + ola, 4), round(j * dlo + olo, 4)) for i in range(i0, i1 + 1) for j in range(j0, j1 + 1)]


def rectangles(cells: list[tuple[float, float]], param: str) -> list[list[tuple[float, float]]]:
    """The cells grouped into full rectangles (greedy: the widest run, then as many rows as stay
    full), so that a box request brings back only cells that are missing."""
    dla, dlo, ola, olo = grid_of(param)
    idx = {(round((la - ola) / dla), round((lo - olo) / dlo)) for la, lo in cells}
    out = []
    while idx:
        i, j = min(idx)
        j1 = j
        while (i, j1 + 1) in idx:
            j1 += 1
        i1 = i
        while all((i1 + 1, jj) in idx for jj in range(j, j1 + 1)):
            i1 += 1
        block = [(ii, jj) for ii in range(i, i1 + 1) for jj in range(j, j1 + 1)]
        idx -= set(block)
        out.append([(round(ii * dla + ola, 4), round(jj * dlo + olo, 4)) for ii, jj in block])
    return out


def _km(la1: float, lo1: float, la2: float, lo2: float) -> float:
    p1, p2 = math.radians(la1), math.radians(la2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lo2 - lo1) / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(min(1.0, a)))


# ---------------------------------------------------------------- default fetchers (network)
def _power_box(param: str, s: float, n: float, w: float, e: float, offline: bool = False) -> list:
    from . import power
    from .regions import Region
    return power.monthly_cells(param, Region("store", "store", s, n, w, e), FIRST, LAST, offline=offline)


def _power_point(param: str, lat: float, lon: float, offline: bool = False) -> dict:
    from . import power
    return power.monthly_point([param], lat, lon, FIRST, LAST, offline=offline).get(param, {})


def _imerg_point(lat: float, lon: float, offline: bool = False) -> dict:
    from . import power
    d = power._get("temporal/monthly/point", {
        "parameters": "IMERG_PRECTOT,PRECTOTCORR", "community": "AG", "latitude": lat, "longitude": lon,
        "start": SAT_FIRST, "end": LAST, "format": "JSON", "time-standard": "UTC"}, offline=offline)
    return power._months(d["properties"]["parameter"].get("IMERG_PRECTOT", {}))


def _modis(what: str, lat: float, lon: float, offline: bool = False) -> dict:
    from . import modis
    if what == "npp":
        return modis.npp(lat, lon, SAT_FIRST, LAST, offline=offline)
    return modis.land_cover(lat, lon, MODIS_COVER_YEARS, offline=offline)


class DataStore:
    """Every import of the agent; see the module's docstring for the guardrail."""

    def __init__(self, root: Path = ROOT, power_box=_power_box, power_point=_power_point,
                 imerg_point=_imerg_point, modis_fetch=_modis, seed: bool = True, clock=time.time):
        self.root = Path(root)
        self.power_box, self.power_point = power_box, power_point
        self.imerg_point, self.modis_fetch = imerg_point, modis_fetch
        self.seed, self.clock = seed, clock
        self._lock = threading.Lock()  # the files and the counters
        self._keys: dict = {}  # (source, variable) -> its lock: one download at a time per data set
        self._recent: dict = {s: [] for s in PER_HOUR}
        self._mem: dict = {}

    # -- files
    def _file(self, source: str, var: str = "") -> Path:
        return self.root / "power" / f"{var}.json" if source == "power" else self.root / f"{source}.json"

    def _load(self, path: Path) -> dict:
        if path not in self._mem:
            try:
                self._mem[path] = json.loads(path.read_text())
            except (OSError, ValueError):
                self._mem[path] = {}
        return self._mem[path]

    def _save(self, path: Path, data: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, separators=(",", ":")))
        os.replace(tmp, path)
        self._mem[path] = data

    def ledger(self) -> list:
        return self._load(self.root / "ledger.json").get("entries", [])

    def _record(self, source: str, var: str, keys: list[str], how: str, request: dict) -> None:
        with self._lock:
            path = self.root / "ledger.json"
            led = dict(self._load(path))
            entries = list(led.get("entries", []))
            entries.append({"source": source, "variable": var, "how": how, "request": request,
                            "cells": len(keys), "keys": sorted(keys), "at": _now()})
            led["entries"] = entries
            self._save(path, led)

    def _done(self, source: str, var: str) -> dict:
        """Cell key -> when it was brought (download or local cache), from the ledger."""
        out = {}
        for e in self.ledger():
            if e["source"] == source and e["variable"] == var:
                for k in e["keys"]:
                    out.setdefault(k, e["at"])
        return out

    def _key_lock(self, source: str, var: str) -> threading.Lock:
        with self._lock:
            return self._keys.setdefault((source, var), threading.Lock())

    # -- the budget
    def budget_left(self) -> dict:
        now = self.clock()
        with self._lock:
            for s in self._recent:
                self._recent[s] = [t for t in self._recent[s] if now - t < 3600]
            return {s: PER_HOUR[s] - len(self._recent[s]) for s in PER_HOUR}

    def _spend(self, source: str, n: int) -> None:
        left = self.budget_left()[source]
        if n > left:
            raise GuardError(f"{n} {source} download(s) needed, {left} left this hour: ask again later, or a smaller area")
        with self._lock:
            self._recent[source] += [self.clock()] * n

    # -- NASA POWER
    def power(self, param: str, cells: list[tuple[float, float]], force: bool = False,
              download: bool = True) -> tuple[dict, dict]:
        """``({cell key: {(y, m): v}}, report)`` for the cells asked (centres of ``param``'s grid)."""
        cells = sorted({cell_of(param, la, lo) for la, lo in cells})
        if len(cells) > MAX_CELLS:
            raise GuardError(f"{len(cells)} cells asked for {param}; at most {MAX_CELLS} in one import")
        report = {"source": "NASA POWER", "variable": param, "cells": len(cells), "from_store": 0,
                  "from_earlier_downloads": 0, "downloaded": 0, "requests": 0, "refused": []}
        with self._key_lock("power", param):
            path = self._file("power", param)
            store = self._load(path).get("cells", {})
            missing = [c for c in cells if cell_key(*c) not in store]
            report["from_store"] = len(cells) - len(missing)
            if missing and self.seed:
                got = self._seed_power(param, missing)
                report["from_earlier_downloads"] = got
                store = self._load(path).get("cells", {})
                missing = [c for c in cells if cell_key(*c) not in store]
            done = self._done("power", param)
            lost = [c for c in missing if cell_key(*c) in done]
            if lost and not force:
                report["refused"].append(
                    f"{len(lost)} cell(s) of {param} were downloaded before ({done[cell_key(*lost[0])]}) and are no "
                    "longer in the store: not downloaded again (an operator restores the store)")
                missing = [c for c in missing if c not in lost]
            if missing and download:
                plan = [r for r in rectangles(missing, param)]
                reqs = []
                for r in plan:
                    rows = len({la for la, _ in r})
                    cols = len({lo for _, lo in r})
                    if rows >= MIN_BOX_CELLS and cols >= MIN_BOX_CELLS:
                        reqs.append(("box", r))
                    else:
                        reqs += [("point", [c]) for c in r]
                if len(reqs) > MAX_REQUESTS:
                    raise GuardError(f"{len(reqs)} requests needed for {param} here; at most {MAX_REQUESTS} in one "
                                     "import: choose a smaller area or a rectangle")
                self._spend("power", len(reqs))
                for kind, r in reqs:
                    want = {cell_key(*c) for c in r}
                    if kind == "box":
                        las, los = [c[0] for c in r], [c[1] for c in r]
                        box = (min(las), max(las), min(los), max(los))
                        rows = {cell_key(round(la, 4), round(lo, 4)): s for la, lo, s in self.power_box(param, *box)}
                        request = {"box": list(box)}
                    else:
                        rows = {cell_key(*r[0]): self.power_point(param, *r[0])}
                        request = {"point": list(r[0])}
                    rows = {k: s for k, s in rows.items() if k in want and s}
                    self._write_power(param, rows)
                    self._record("power", param, list(rows), "download", request)
                    report["downloaded"] += len(rows)
                    report["requests"] += 1
            elif missing:
                report["refused"].append(f"{len(missing)} cell(s) of {param} not in the store (no download asked)")
            store = self._load(path).get("cells", {})
            out = {cell_key(*c): {_from_ym(k): v for k, v in store[cell_key(*c)].items()}
                   for c in cells if cell_key(*c) in store}
        return out, report

    def _write_power(self, param: str, rows: dict) -> None:
        if not rows:
            return
        with self._lock:
            path = self._file("power", param)
            data = dict(self._load(path))
            cells = dict(data.get("cells", {}))
            for k, s in rows.items():
                if k not in cells:  # what is in the store is never overwritten
                    cells[k] = {_ym(m): v for m, v in s.items()}
            data["cells"] = cells
            self._save(path, data)

    def _seed_power(self, param: str, missing: list) -> int:
        """Cells the detective or the land analysis already downloaded (their HTTP caches, offline)."""
        from .regions import REGIONS
        from .variables import VARIABLES
        firsts = sorted({FIRST, VARIABLES[param].first_year if param in VARIABLES else FIRST})
        want = {cell_key(*c) for c in missing}
        got = 0
        for r in REGIONS.values():
            if not any(r.south - 1e-9 <= la <= r.north + 1e-9 and r.west - 1e-9 <= lo <= r.east + 1e-9
                       for la, lo in missing):
                continue
            for start in firsts:
                try:
                    from . import power
                    rows = power.monthly_cells(param, r, start, LAST, offline=True)
                except Exception:  # noqa: BLE001 - not cached: nothing to take
                    continue
                new = {cell_key(round(la, 4), round(lo, 4)): s for la, lo, s in rows}
                new = {k: s for k, s in new.items() if k in want and s}
                if new:
                    self._write_power(param, new)
                    self._record("power", param, list(new), "earlier download (local cache)",
                                 {"region": r.key, "start": start})
                    got += len(new)
                    want -= set(new)
                break
            if not want:
                break
        return got

    # -- GPM IMERG (points)
    @staticmethod
    def imerg_pixel(lat: float, lon: float) -> tuple[float, float]:
        """The centre of IMERG's 0.1° pixel holding a point."""
        return round(math.floor(lat * 10) / 10 + 0.05, 2), round(math.floor(lon * 10) / 10 + 0.05, 2)

    def imerg(self, lat: float, lon: float, force: bool = False) -> tuple[dict, dict]:
        px = self.imerg_pixel(lat, lon)
        key = cell_key(*px)
        report = {"source": "GPM IMERG", "pixel": list(px), "from_store": 0, "from_earlier_downloads": 0,
                  "downloaded": 0, "requests": 0, "refused": []}
        with self._key_lock("imerg", "IMERG_PRECTOT"):
            path = self._file("imerg")
            store = self._load(path).get("pixels", {})
            if key in store:
                report["from_store"] = 1
            else:
                s, how = None, None
                if self.seed:  # the land analysis read IMERG at the MERRA-2 cell centres
                    c = cell_of("PRECTOTCORR", lat, lon)
                    if self.imerg_pixel(*c) == px:
                        try:
                            s, how = self.imerg_point(*c, offline=True), "earlier download (local cache)"
                        except Exception:  # noqa: BLE001
                            s = None
                if not s:
                    if key in self._done("imerg", "IMERG_PRECTOT") and not force:
                        report["refused"].append("this pixel was downloaded before and is no longer in the store")
                        return {}, report
                    self._spend("imerg", 1)
                    s, how = self.imerg_point(*px), "download"
                    report["downloaded"], report["requests"] = 1, 1
                else:
                    report["from_earlier_downloads"] = 1
                with self._lock:
                    data = dict(self._load(path))
                    pixels = dict(data.get("pixels", {}))
                    pixels[key] = {_ym(m): v for m, v in s.items()}
                    data["pixels"] = pixels
                    self._save(path, data)
                self._record("imerg", "IMERG_PRECTOT", [key], how, {"point": list(px)})
                store = self._load(path).get("pixels", {})
        return {_from_ym(k): v for k, v in store.get(key, {}).items()}, report

    # -- MODIS (windows of 5 km around a point)
    @staticmethod
    def modis_anchor(lat: float, lon: float) -> tuple[float, float]:
        """Where the window is centred: a MERRA-2 cell centre within 3 km (where the land analysis
        read MODIS: the same window), else the point on a 0.05° grid."""
        c = cell_of("PRECTOTCORR", lat, lon)
        if _km(lat, lon, *c) <= 3.0:
            return c
        return round(round(lat / 0.05) * 0.05, 3), round(round(lon / 0.05) * 0.05, 3)

    def modis(self, what: str, lat: float, lon: float, force: bool = False) -> tuple[dict, dict]:
        if what not in ("npp", "cover"):
            raise GuardError("MODIS products here: npp (plant productivity) or cover (land cover)")
        pt = self.modis_anchor(lat, lon)
        key = cell_key(*pt)
        report = {"source": "MODIS (ORNL DAAC)", "product": what, "window_centre": list(pt), "from_store": 0,
                  "from_earlier_downloads": 0, "downloaded": 0, "requests": 0, "refused": []}
        with self._key_lock("modis", what):
            path = self._file("modis")
            store = self._load(path).get(what, {})
            if key in store:
                report["from_store"] = 1
            else:
                r, how = None, None
                if self.seed:
                    try:
                        r, how = self.modis_fetch(what, *pt, offline=True), "earlier download (local cache)"
                    except Exception:  # noqa: BLE001
                        r = None
                if not r:
                    if key in self._done("modis", what) and not force:
                        report["refused"].append("this window was downloaded before and is no longer in the store")
                        return {}, report
                    self._spend("modis", 1)
                    r, how = self.modis_fetch(what, *pt), "download"
                    report["downloaded"], report["requests"] = 1, 1
                else:
                    report["from_earlier_downloads"] = 1
                with self._lock:
                    data = dict(self._load(path))
                    part = dict(data.get(what, {}))
                    part[key] = {str(y): v for y, v in r.items()}
                    data[what] = part
                    self._save(path, data)
                self._record("modis", what, [key], how, {"point": list(pt)})
                store = self._load(path).get(what, {})
        return {int(y): v for y, v in store.get(key, {}).items()}, report

    # -- what is there
    def summary(self) -> dict:
        out: dict = {}
        for e in self.ledger():
            k = f"{e['source']}:{e['variable']}"
            s = out.setdefault(k, {"cells": 0, "downloads": 0, "from_earlier_downloads": 0, "last": None})
            s["cells"] += e["cells"]
            s["downloads" if e["how"] == "download" else "from_earlier_downloads"] += 1
            s["last"] = e["at"]
        return {"in_store": out, "downloads_left_this_hour": self.budget_left()}


STORE = DataStore()
