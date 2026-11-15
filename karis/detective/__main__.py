"""Command line of the Earth System Trend Detective.

    python -m detective list
    python -m detective ask "sea ice" --region barents
    python -m detective investigate --region barents --vars T2M,FRSEAICE,TS,SLP --words "sea ice"
    python -m detective investigate --region ross,bellingshausen --vars FRSEAICE,T2M --out data/earth/investigations/dipole.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .investigate import discover, investigate
from .mcp import EarthdataMCP
from .regions import REGIONS, parse_region
from .variables import TOPICS, VARIABLES

OUT = Path(__file__).resolve().parents[1] / "data" / "earth" / "investigations"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="detective", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="regions and variables")
    a = sub.add_parser("ask", help="what NASA data exists for these words over this region (earthdata-mcp)")
    a.add_argument("words")
    a.add_argument("--region", default="sahel")
    a.add_argument("--start", type=int, default=1981)
    a.add_argument("--end", type=int, default=2025)
    i = sub.add_parser("investigate", help="trends, Eva's view and links for variables over regions")
    i.add_argument("--region", required=True, help="name(s), comma-separated, or a box south,north,west,east")
    i.add_argument("--vars", required=True, help="POWER parameters, comma-separated (see `list`)")
    i.add_argument("--words", default=None, help="what to look for in NASA's catalogue (default: first variable)")
    i.add_argument("--base", default="1981-2010", help="baseline years Eva learns her norm on")
    i.add_argument("--start", type=int, default=1981)
    i.add_argument("--end", type=int, default=2025)
    i.add_argument("--out", default=None)
    i.add_argument("--no-mcp", action="store_true")
    i.add_argument("--offline", action="store_true", help="use the cached answers only")
    args = ap.parse_args(argv)

    if args.cmd == "list":
        print("Regions:")
        for r in REGIONS.values():
            print(f"  {r.key:15s} {r.name} [{r.south}..{r.north}°N, {r.west}..{r.east}°E] — {r.why}")
        for t, name in TOPICS.items():
            print(f"{name}:")
            for v in VARIABLES.values():
                if v.topic == t:
                    print(f"  {v.key:18s} {v.label} ({v.units}, {v.source}, from {v.first_year}) — {v.simple}")
        return 0
    if args.cmd == "ask":
        r = parse_region(args.region)
        d = discover(EarthdataMCP(), args.words, r, args.start, args.end)
        for k in d["keywords"]:
            print(f"\n{k['prefLabel']}: {k['definition']}")
            for c in d["collections"].get(k["prefLabel"], []):
                print(f"   - {c['short_name']} v{c['version']} | {', '.join(c['platforms'] or [])} | "
                      f"{(c['start'] or '')[:10]}..{(c['end'] or 'now')[:10]} | {c['title']}")
        for e in d["errors"]:
            print("error:", e, file=sys.stderr)
        return 0
    regions = [parse_region(x) for x in args.region.split(",")] if "," in args.region and args.region.count(",") != 3 \
        else [parse_region(args.region)]
    b0, b1 = (int(x) for x in args.base.split("-"))
    keys = [k.strip().upper() for k in args.vars.split(",")]
    unknown = [k for k in keys if k not in VARIABLES]
    if unknown:
        print(f"unknown variables {unknown}; see `python -m detective list`", file=sys.stderr)
        return 2
    print(f"Investigating {', '.join(keys)} over {', '.join(r.name for r in regions)} ...")
    res = investigate(regions, keys, args.words, (b0, b1), args.start, args.end, with_mcp=not args.no_mcp,
                      offline=args.offline)
    out = Path(args.out) if args.out else OUT / f"{'_'.join(r.key for r in regions)}-{'_'.join(keys).lower()}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res))
    print(f"\nFindings:")
    for line in res["story"]:
        print(" -", line["text"])
    print(f"\nSaved {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
