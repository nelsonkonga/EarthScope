"""The land intelligence page: kepler.gl map + the findings, as one standalone HTML file.

    python -m detective.land_page                 # data/earth/land/index.html from the analysed regions
    python -m detective.land_page cameroon_chad   # only this region

The page embeds the results (``slim``), loads kepler.gl 3.1.10 and its React 18 / Redux stack
from unpkg (an internet connection is needed for the map and the basemap), and recomputes the
budget plan in the browser (the same algorithm as ``budget.allocate``). Served by
``python -m detective.serve`` (``/land``), it can also analyse a new region on demand.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

from . import budget
from .land import HORIZON, OUT, RISK_P
from .places import Places

TEMPLATE = Path(__file__).with_name("land_page.html")


def _r(x, sig: int = 4):
    if x is None:
        return None
    if isinstance(x, float):
        if not math.isfinite(x):
            return None
        return float(f"{x:.{sig}g}")
    return x


def where(res: dict) -> dict:
    """Each cell's countries (share of the cell, largest first) and nearest town (Natural Earth)."""
    r, g = res["region"], res["grid"]
    try:
        pl = Places(r["south"], r["north"], r["west"], r["east"])
    except OSError:  # offline and never extracted: the page simply shows the coordinates
        return {}
    out = {}
    for k, c in res["cells"].items():
        t = pl.nearest_town(c["lat"], c["lon"])
        out[k] = {"c": [[n, round(sh, 2)] for _iso, n, sh in pl.country_shares(c["lat"], c["lon"], g["dlat"], g["dlon"])],
                  "t": [t[0], t[1], round(t[2])] if t else None}
    return out


def slim(res: dict) -> dict:
    """What the page needs of one analysed region."""
    keys = list(res["cells"])
    wh = where(res)
    inds = {}
    for k, meta in res["indicators"].items():
        det = res["detect"][k]
        cells = {}
        for c in keys:
            t = det["cells"].get(c)
            if not t:
                continue
            cells[c] = [_r(t["per_decade"]), _r(t["ci"][0]), _r(t["ci"][1]), _r(t["p_mk"], 3), _r(t["p_t"], 3),
                        1 if t["detected"] else 0, _r(t.get("z"), 3), _r(t["base_mean"])]
        fc = {c: [_r(f["pred"]), _r(f["lo90"]), _r(f["hi90"]), _r(f["recent"]), _r(f["p_down"], 3), _r(f["eva"])]
              for c, f in (res["forecast"].get(k) or {}).items()}
        hc = res["hindcast"].get(k)
        if hc:
            hc = {kk: v for kk, v in hc.items() if kk != "per_cell"}
        eva = res["eva"].get(k)
        if eva:
            eva = {"cells": {c: {"d": [[d["from"], d["to"], _r(d["per_decade"])] for d in e["dynamics"]],
                                 "t": [_r(t, 5) for t in e["transitions"]],
                                 "l": [[_r(v) for v in seg] for seg in e.get("lines", [])]}
                             for c, e in eva["cells"].items()},
                   "changed": eva["changed"], "read": eva["read"], "expected": _r(eva["expected_by_control"]),
                   "p": _r(eva["p_changed"], 3), "stream_joins": eva.get("stream_joins"),
                   "changes": [{kk: c[kk] for kk in ("type", "year", "cells", "of", "p")}
                               for c in (eva.get("changes") or {}).get("changes", [])],
                   "borders": [{"a": b["a"], "b": b["b"], "strong": b["strong"]} for b in eva["borders"]["borders"]]}
        inds[k] = {"meta": meta, "summary": det["summary"], "cells": cells, "forecast": fc, "hindcast": hc,
                   "eva": eva, "series": {c: [_r(v) for v in vals] for c, vals in res["series"][k].items()}}
    b = budget.summary(res)
    b["threats"] = {e: {c: {t: _r(v, 3) for t, v in th.items() if v} for c, th in d.items()}
                    for e, d in b["threats"].items()}
    b.pop("plan", None)
    rep = res.get("replication") or {}
    return {
        "region": res["region"], "created": res["created"], "period": res["period"], "baseline": res["baseline"],
        "learn_cuts": res["learn_cuts"], "test_cut": res["test_cut"], "horizon": res["horizon"],
        "fdr_q": res["fdr_q"], "risk_p": res["risk_p"], "grid": res["grid"], "years": res["years"],
        "cells": {c: {"lat": v["lat"], "lon": v["lon"], "area": _r(v["area_km2"]), "crop": _r(v["cropland"], 3),
                      "forest": _r(v["forest"], 3), "crop_ha": _r(v["cropland_ha"]), **(wh.get(c) or {})}
                  for c, v in res["cells"].items()},
        "indicators": inds, "drivers": {c: {kk: _r(x, 3) for kk, x in d.items()} for c, d in res["drivers"].items()},
        "replication": {"cells": rep.get("cells", 0), "years": rep.get("years"), "indicators": rep.get("indicators", {}),
                        "per_cell": {c: {i: {"m": _r(x["merra"]), "s": _r(x["imerg"]), "r": _r(x["r"], 3),
                                             "status": x["status"]} for i, x in d.items()}
                                     for c, d in (rep.get("per_cell") or {}).items()}},
        "validation": res.get("validation"),
        "cover_change": {kk: v for kk, v in (res.get("cover_change") or {}).items() if kk != "per_cell"},
        "story": res["story"], "budget": b, "budget_text": budget.describe(b),
        "ground": ground(res["region"]["key"]),
    }


def ground(key: str, most: int = 3000) -> dict | None:
    """Bare ground opened since 2001 (detective/scars.py): the patches, the mines people mapped, the check."""
    f = OUT / f"{key}_scars.json"
    if not f.exists():
        return None
    d = json.loads(f.read_text())
    ps = sorted(d.get("patches", []), key=lambda p: -p["area_km2"])[:most]
    return {"years": d.get("years"), "method": d.get("method"), "cannot_see": d.get("cannot_see"),
            "validation": d.get("validation"), "count": len(d.get("patches", [])),
            "area_km2": _r(sum(p["area_km2"] for p in d.get("patches", []))),
            "patches": [[p["lat"], p["lon"], p["area_km2"], p["opened"][1], p["before"]] for p in ps],
            "mines": [[m["lat"], m["lon"], m.get("kind") or "", m.get("name") or "", m.get("resource") or ""]
                      for m in d.get("mapped_mines", [])]}


def render(cases: list[dict], live: bool = False) -> str:
    html = TEMPLATE.read_text(encoding="utf-8")
    data = json.dumps({"cases": cases, "live": live, "threats": {t: list(v) for t, v in budget.THREATS.items()},
                       "risk_p": RISK_P, "horizon": list(HORIZON)}, separators=(",", ":"))
    return html.replace("/*__DATA__*/null", data.replace("</", "<\\/"))


def cases_on_disk(only: list[str] | None = None) -> list[dict]:
    out = []
    for f in sorted(OUT.glob("*.json")):
        if only and f.stem not in only:
            continue
        res = json.loads(f.read_text())
        if "detect" in res and "cells" in res:
            out.append(slim(res))
    return sorted(out, key=lambda c: not c["region"].get("country"))  # a country first, then the wider boxes


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    cases = cases_on_disk(argv or None)
    if not cases:
        print("no analysed region in", OUT, "- run: python -m detective.land analyse --region cameroon_chad")
        return 1
    out = OUT / "index.html"
    out.write_text(render(cases), encoding="utf-8")
    print(f"Saved {out} ({out.stat().st_size / 1e6:.1f} MB, {len(cases)} region(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
