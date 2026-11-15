"""Where does the link between sea-level pressure and tropopause temperature change sign?

The sweep (checks/earth_sweep.py) found Eva linking the months when sea-level pressure and
tropopause temperature leave their norm: the same way over the Indo-Gangetic Plain (all year),
the opposite way over the Bellingshausen Sea. This transect reads the same pair in boxes along a
meridian band, with the detective's whole chain (extreme lens, heat layer, chance at the same
moment, persistence test). The pair is fixed in advance, so each box makes one family of 14
readings (Bonferroni over 14 only; the latitudes are reported, not selected).

Usage: python checks/earth_transect.py [west east]   (default 70 80: the Indian sector)
Writes data/earth/sweep/transect_<west>_<east>.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from detective.investigate import investigate  # noqa: E402
from detective.regions import parse_region  # noqa: E402

LATS = [(-64, -56), (-52, -44), (-40, -32), (-28, -20), (-16, -8), (-4, 4), (8, 16), (20, 28), (32, 40),
        (44, 52), (56, 64), (66, 74)]


def main(argv: list[str]) -> None:
    w, e = (float(argv[0]), float(argv[1])) if len(argv) >= 2 else (70.0, 80.0)
    out_file = ROOT / "data" / "earth" / "sweep" / f"transect_{w:g}_{e:g}.json"
    rows = json.loads(out_file.read_text()) if out_file.exists() else []
    done = {tuple(r["lat"]) for r in rows}
    for s, n in LATS:
        if (s, n) in done:
            continue
        try:
            res = investigate([parse_region(f"{s},{n},{w},{e}")], ["SLP", "TROPT"], with_mcp=False, log=lambda *a: None)
        except Exception as ex:  # a failed download: try again later
            print(f"{s}..{n}: failed ({ex})", flush=True)
            continue
        c = res["eva"]["extreme"]["couplings"]
        links = c["links"]
        x = links[0] if links else None
        rows.append({"lat": [s, n], "level": x["level"] if x else None, "transform": x["transform"] if x else None,
                     "sign": x["sign"] if x else None, "lag": x["lag"] if x else None, "hits": x["hits"] if x else None,
                     "expected": x["expected"] if x else None, "p": x["p"] if x else None,
                     "z": x["z_persistence"] if x else None, "trends": {u: t["verdict"]["direction"] + " / " +
                                                                        t["verdict"]["level"]
                                                                        for u, t in res["trends"].items()}})
        out_file.write_text(json.dumps(rows, indent=1))
        r = rows[-1]
        print(f"{s:+4d}..{n:+4d}°: {r['level'] or '—':10s} {r['transform'] or '':9s} "
              + (f"{r['hits']}/{r['expected']:.1f} p {r['p']:.0e} z {r['z']:.1f}" if x else ""), flush=True)
    rows.sort(key=lambda r: r["lat"][0])
    out_file.write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main(sys.argv[1:])
