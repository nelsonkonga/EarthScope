"""A wider sweep of Eva's heat layer over the Earth, to look for links worth checking against the literature.

Each investigation (region(s) × variables) is run as the detective runs it — classical statistics,
Eva at two grains, the heat layer with chance read at the same moment and the persistence test —
without the earthdata-mcp discovery (provenance is not needed here). Results go to
data/earth/sweep/<name>.json; the candidates (proven links, with the model note the reader would
see) to data/earth/sweep/candidates.json, strongest first.

Usage: python checks/earth_sweep.py [name ...]   (default: every investigation below)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from detective.investigate import investigate  # noqa: E402
from detective.regions import parse_region  # noqa: E402
from detective.variables import MODEL_LINKS, model_note  # noqa: E402

LAND = "T2M,TS,PRECTOTCORR,GWETROOT,EVLAND,RH2M,TQV,SLP,WS10M,TROPT"
SWEEP = {
    "cameroon": ("cameroon", LAND),
    "amazon": ("amazon", LAND),
    "delhi": ("delhi", LAND),
    "sahel_wide": ("sahel", LAND),
    "bellingshausen": ("bellingshausen", "T2M,TS,FRSEAICE,SLP,WS10M,PRECTOTCORR,TQV,TROPT"),
    "sahel_cameroon": ("sahel,cameroon", "PRECTOTCORR,GWETROOT,T2M,SLP"),
    "warmpool_amazon": ("warm_pool,amazon", "T2M,PRECTOTCORR,TQV,SLP"),
    "warmpool_delhi": ("warm_pool,delhi", "T2M,PRECTOTCORR,TQV,SLP"),
}
OUT = ROOT / "data" / "earth" / "sweep"


def run(name: str) -> dict:
    regions, vars_ = SWEEP[name]
    out = OUT / f"{name}.json"
    if out.exists():
        return json.loads(out.read_text())
    rs = [parse_region(r) for r in regions.split(",")]
    print(f"{name}: {regions} × {vars_}", flush=True)
    res = investigate(rs, vars_.split(","), with_mcp=False, log=lambda *a: None)
    out.write_text(json.dumps(res))
    return res


def candidates(results: dict) -> list:
    out = []
    for name, res in results.items():
        heat = (res["eva"].get("extreme") or {}).get("couplings") or {}
        units = res["units"]
        for x in heat.get("links", []):
            if x["level"] != "proven":
                continue
            va, vb = (units[m]["variable"] for m in x["members"])
            ra, rb = (units[m]["region"] for m in x["members"])
            out.append({"sweep": name, "labels": x["labels"], "variables": [va, vb], "regions": [ra, rb],
                        "transform": x["transform"], "lag": x["lag"], "sign": x["sign"], "hits": x["hits"],
                        "expected": x["expected"], "p": x["p"], "z": x["z_persistence"], "union": x["union"],
                        "episodes": x["episodes"], "longest": x["longest"],
                        "definitional": frozenset((va, vb)) in MODEL_LINKS, "note": model_note(va, vb),
                        "text": x["text"]})
        for p in heat.get("same_process", []):
            out.append({"sweep": name, "same_process": p})
    out.sort(key=lambda c: -(c.get("z") or 0))
    return out


def main(argv: list[str]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    results = {}
    for name in argv or SWEEP:
        try:
            results[name] = run(name)
        except Exception as e:  # one failed download does not stop the sweep
            print(f"{name}: failed ({e})", flush=True)
    cands = candidates(results)
    (OUT / "candidates.json").write_text(json.dumps(cands, indent=1, default=list))
    print(f"\n{len(cands)} proven links / processes")
    for c in cands:
        if "same_process" in c:
            print(f"  [{c['sweep']}] SAME PROCESS {c['same_process']}")
            continue
        flag = "def" if c["definitional"] else ("mer" if c["note"] else "   ")
        print(f"  [{c['sweep']:15s}] {flag} {c['labels'][0][:34]:34s} {c['labels'][1][:34]:34s} {c['transform']:9s} "
              f"{c['hits']:3d}/{c['expected']:5.1f} z {c['z']:5.1f}{' U' if c['union'] else ''}")


if __name__ == "__main__":
    main(sys.argv[1:])
