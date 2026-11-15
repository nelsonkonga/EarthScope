"""Builds the Cameroon "fusion" CSV the WhatsApp team asked for: GLDAS-NOAH025_M (2.0 + 2.1,
via OPeNDAP, real per-cell values, area mean over cameroon_full) and NASA POWER (MERRA-2 +
CERES, via power.py, already in this repo), all on the same Cameroon box (not Africa-wide),
one row per month, one column per (source, variable).

Usage: .venv/bin/python checks/build_cameroon_fusion.py [--offline]
"""

from __future__ import annotations

import csv
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from detective import gldas, power
from detective.regions import REGIONS

CAM = REGIONS["cameroon_full"]
OUT = Path(__file__).resolve().parents[1] / "data" / "earth" / "cameroon_fusion.csv"

GLDAS_KEYS = list(gldas.VARIABLES.keys())
POWER_PARAMS = {
    "T2M": "Air temperature (deg C)",
    "TS": "Surface (skin) temperature (deg C)",
    "PRECTOTCORR": "Precipitation, gauge-corrected (mm/day)",
    "GWETROOT": "Root-zone soil wetness (0-1 fraction)",
    "GWETTOP": "Surface (top 5cm) soil wetness (0-1 fraction)",
    "EVLAND": "Evaporation from land (mm/day)",
    "RH2M": "Relative humidity at 2m (%)",
    "ALLSKY_SRF_ALB": "Surface albedo, CERES 1deg grid (0-1 fraction)",
}


def fetch_gldas(offline: bool) -> dict:
    """{version: {key: {(y,m): v}}}, fetched with a thread pool (I/O bound)."""
    out = {v: {k: {} for k in GLDAS_KEYS} for v in gldas.COLLECTIONS}
    jobs = []
    for version, (_coll, _suf, first, last) in gldas.COLLECTIONS.items():
        end_year = last or time.gmtime().tm_year
        end_month = 12 if last else time.gmtime().tm_mon
        for y in range(first, end_year + 1):
            for m in range(1, 13):
                if y == end_year and m > end_month:
                    continue
                jobs.append((version, y, m))
    done = 0
    with ThreadPoolExecutor(max_workers=5) as ex:
        futs = {ex.submit(gldas._fetch_raw, version, y, m, GLDAS_KEYS, CAM, offline): (version, y, m)
                for version, y, m in jobs}
        for fut in as_completed(futs):
            version, y, m = futs[fut]
            text = fut.result()
            if text is not None:
                vals = gldas._parse(text, GLDAS_KEYS)
                for k in GLDAS_KEYS:
                    out[version][k][(y, m)] = vals.get(k)
            done += 1
            print(f"\r  GLDAS {done}/{len(jobs)}", end="", flush=True)
    print()
    return out


def fetch_power(offline: bool) -> dict:
    """{param: {(y,m): v}}, area mean (cos-lat) of every POWER cell in the Cameroon box."""
    out = {}
    for i, (p, _label) in enumerate(POWER_PARAMS.items(), 1):
        print(f"\r  POWER {i}/{len(POWER_PARAMS)} {p}", end="", flush=True)
        cells = power.monthly_cells(p, CAM, start=power.FIRST_YEAR, end=time.gmtime().tm_year,
                                      offline=offline)
        out[p] = power.area_mean(cells)
    print()
    return out


def main(offline: bool = False) -> None:
    print("Fetching GLDAS (OPeNDAP, Cameroon box)...")
    g = fetch_gldas(offline)
    print("Fetching NASA POWER (Cameroon box)...")
    p = fetch_power(offline)

    all_months = sorted({k for ver in g.values() for series in ver.values() for k in series}
                         | {k for series in p.values() for k in series})

    columns = []
    for version in ("2.0", "2.1"):
        for key in GLDAS_KEYS:
            var, units, desc = gldas.VARIABLES[key]
            columns.append((f"GLDAS_{version}_{var}", g[version][key], f"{desc} [{units}] (GLDAS-NOAH025_M {version})"))
    for param, label in POWER_PARAMS.items():
        columns.append((f"POWER_{param}", p[param], f"{label} (NASA POWER, MERRA-2/CERES)"))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["# Cameroon box (cameroon_full): south=2, north=13, west=8, east=16.5 "
                    "(country=CMR) -- NOT Africa-wide, unlike the Giovanni fusion(1).csv"])
        w.writerow(["date"] + [c[0] for c in columns])
        w.writerow(["# description"] + [c[2] for c in columns])
        for y, m in all_months:
            row = [f"{y:04d}-{m:02d}-01"]
            for _name, series, _desc in columns:
                v = series.get((y, m))
                row.append("" if v is None else round(v, 6))
            w.writerow(row)

    print(f"Wrote {OUT} ({len(all_months)} months, {len(columns)} data columns)")


if __name__ == "__main__":
    main(offline="--offline" in sys.argv)
