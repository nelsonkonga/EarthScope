"""Where and when the dynamics changed, and of which type, over every grid cell of the investigations
already made (detective/changes.py; NASA POWER, read offline from data/earth/cache).

For each investigation (data/earth/investigations) and each variable × region: every cell's yearly
series read by Eva at the level of a trend, its transitions placed on the heatmap (year × type), the
concentrations judged against the same fields with no change of dynamic (99 shuffled fields).
Control: the same reading of one shuffled field per unit (no change in it): how often a change is told.

Usage: earth_changes.py [out.json] [draws]
"""

from __future__ import annotations

import glob
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from detective import changes, power  # noqa: E402
from detective.regions import Region  # noqa: E402
from detective.variables import VARIABLES  # noqa: E402


def units_of(path: str):
    d = json.load(open(path))
    regions = [Region(**{k: r[k] for k in ("key", "name", "south", "north", "west", "east")}, why=r.get("why", ""))
               for r in d["regions"]]
    start, end = d.get("period", [1981, 2025])
    for r in regions:
        for v in d["variables"]:
            var = VARIABLES[v]
            _, cs = power.region_series(v, r, max(start, var.first_year), end, offline=True)
            yield f"{v}@{r.key}", f"{var.label} ({r.name})", cs


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    draws = int(sys.argv[2]) if len(sys.argv) > 2 else 99
    res, told, ctl, n = {}, 0, 0, 0
    if out and out.exists():  # resume: the units already read are kept
        res = json.loads(out.read_text())
        n = len(res)
        told = sum(bool(r["changes"]) for r in res.values())
        ctl = sum(r.get("control_changes", 0) > 0 for r in res.values())
    for f in sorted(glob.glob(str(ROOT / "data/earth/investigations/*.json"))):
        case = Path(f).stem
        for u, label, cs in units_of(f):
            key = f"{case}:{u}"
            if any(k.split(":", 1)[1] == u for k in res):
                continue  # the same variable over the same region, already read in another investigation
            r = changes.read_cells(cs, draws=draws)
            r["label"] = label
            # control, once per investigation (a shuffled field is exchangeable with the draws of chance,
            # so it is told a change 1 time in 100 by construction: this checks the code, not the theory):
            # one shuffled field (no change of dynamic in it), read the same way
            years, cc = changes._cell_years(cs)
            first = not any(k.startswith(case + ":") for k in res)
            if len(cc) >= 4 and first:
                ser = [v for _, _, v in cc]
                res_ = [changes._read(years, v)[1] for v in ser]
                sh = changes._shuffled(years, ser, res_, random.Random(12345), changes._block(res_))
                fake = [(la, lo, {(y, m): x for y, x in zip(years, v) for m in range(1, 13)}) for (la, lo, _), v in zip(cc, sh)]
                rc = changes.read_cells(fake, draws=draws, seed=1)
                r["control_changes"] = len(rc["changes"])
                ctl += len(rc["changes"]) > 0
            n += 1
            told += bool(r["changes"])
            res[key] = r
            if out:  # kept after every unit: a long run can be resumed
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(json.dumps(res, ensure_ascii=False))
            head = f"{case:9s} {label[:40]:40s} {r['cells']:4d} mailles, {r.get('transitions', 0):4d} transitions, hasard au plus {r.get('chance_largest', 0)}"
            print(head + (" | témoin : " + str(r.get("control_changes")) if "control_changes" in r else ""), flush=True)
            for line in changes.text(u, r):
                print("     " + line, flush=True)
            for b in r.get("bridges", []):
                print(f"     type de types : {b['from']} → {b['to']} dans {b['cells']}/{b['of']} mailles (p {b['p']:.2g})", flush=True)
    nctl = sum("control_changes" in r for r in res.values())
    print(f"\n{n} variables × régions ; un changement prouvé dans {told} ; témoin (champs sans changement) : {ctl}/{nctl}")
    if out:
        out.write_text(json.dumps(res, ensure_ascii=False))
        print(f"→ {out}")


if __name__ == "__main__":
    main()
