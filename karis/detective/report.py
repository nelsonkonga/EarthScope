"""The investigation as a self-contained page (``page.html`` + the cases as embedded JSON).

    python -m detective.report                 # the demo cases -> data/earth/report/index.html (+ artifact.html)

``index.html`` is a complete document (open it in a browser, or let ``serve.py`` serve it
with live investigations); ``artifact.html`` is the same page without the document skeleton,
for publishing.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from . import dynamics, stats
from .regions import REGIONS
from .variables import TOPICS, VARIABLES

ROOT = Path(__file__).resolve().parents[1]
INV = ROOT / "data" / "earth" / "investigations"
OUT = ROOT / "data" / "earth" / "report"
TEMPLATE = Path(__file__).with_name("page.html")
STATS_JS = Path(__file__).with_name("stats.js")  # the season / month statistics, inlined into the page

# The demonstration cases a user can watch (id, title, question, investigation file).
DEMOS = [
    ("arctic", "Arctic warming", "Is the Arctic around Svalbard really warming, and what changes with it?", "arctic.json"),
    ("two-seas", "Two seas, opposite trends",
     "Can sea ice grow in one sea while it melts in another, and is the same process at work in both?", "two_seas.json"),
    ("sahel", "Sahel rains", "Did the rains and the soils of the Sahel recover after the great drought?", "sahel.json"),
    ("europe", "Western Europe", "Hotter, sunnier, drier: what is really changing over France?", "europe.json"),
    ("levels", "Two levels of the sky",
     "Above the warmest ocean on Earth, does the air warm alike at the surface and 17 km up?", "levels.json"),
]


def _r(x, sig: int = 4):
    """Round to ``sig`` significant digits (smaller JSON)."""
    if isinstance(x, float):
        if not math.isfinite(x) or x == 0:
            return x if math.isfinite(x) else None
        return round(x, max(0, sig - 1 - int(math.floor(math.log10(abs(x))))))
    if isinstance(x, list):
        return [_r(v, sig) for v in x]
    if isinstance(x, dict):
        return {k: _r(v, sig) for k, v in x.items()}
    return x


def _pick(d: dict | None, keys) -> dict:
    return {k: d.get(k) for k in keys} if d else {}


def slim_season(st_: dict) -> dict:
    """The page's view of ``stats.season_trend`` (same fields the page reads from a full-year trend)."""
    a = st_["annual"]
    return _r({
        **_pick(st_, ["months", "per_decade", "per_decade_ci", "ols_per_decade", "ols_per_decade_ci", "total_change",
                      "total_change_sd", "total_change_pct", "years", "years_needed", "noise_sd", "noise_r1",
                      "verdict", "baseline_mean", "baseline_sd"]),
        "annual": {"years": a["years"], "values": a["values"],
                   "sen": _pick(a["sen"], ["slope", "intercept", "ci"]),
                   "mann_kendall": _pick(a["mann_kendall"], ["p", "tau", "factor", "S"]),
                   "ols": _pick(a["ols"], ["p", "slope", "n_eff", "r1", "ci"]),
                   "pettitt": _pick(a["pettitt"], ["year", "p", "before", "after"])},
        "anomalies": st_["anomalies"]})


def season_presets(months: list, values: list, base) -> dict:
    """DJF / MAM / JJA / SON of a monthly series as the page embeds it (the full year is the case's
    own trend). Computed from the rounded embedded values so that the page's JavaScript gives the same."""
    series = {(int(k[:4]), int(k[5:7])): v for k, v in zip(months, values)}
    out = {}
    for name, ms in stats.SEASONS.items():
        r = stats.season_trend(series, tuple(base), ms)
        if r is not None:
            out[name] = slim_season(r)
    return out


def slim(res: dict, cid: str, title: str, question: str) -> dict:
    """What the page needs from an investigation."""
    trends = {}
    for u, t in res["trends"].items():
        a, m = t["annual"], t["monthly"]
        trends[u] = _r({
            **_pick(t, ["per_decade", "per_decade_ci", "ols_per_decade", "ols_per_decade_ci", "monthly_per_decade",
                        "monthly_per_decade_ci", "total_change", "total_change_sd", "total_change_pct", "years",
                        "years_needed", "noise_sd", "noise_r1", "verdict", "baseline_mean", "baseline_sd",
                        "first", "last", "months"]),
            "annual": {"years": a["years"], "values": a["values"],
                       "sen": _pick(a["sen"], ["slope", "intercept", "ci"]),
                       "mann_kendall": _pick(a["mann_kendall"], ["p", "tau", "factor", "S"]),
                       "ols": _pick(a["ols"], ["p", "slope", "n_eff", "r1", "ci"]),
                       "pettitt": _pick(a["pettitt"], ["year", "p", "before", "after"])},
            "monthly": {"mann_kendall": _pick(m["mann_kendall"], ["p", "factor", "tau"]),
                        "ols": _pick(m["ols"], ["p", "n_eff", "r1", "slope"]),
                        "seasonal_mann_kendall": _pick(m["seasonal_mann_kendall"], ["p", "slope"])},
            "anomalies": t["anomalies"]["values"],
        })
        if trends[u].get("verdict"):
            trends[u]["verdict"] = t["verdict"]
        if u in res["series"]:
            sr = res["series"][u]
            trends[u]["seasons"] = season_presets(sr["months"], _r(sr["values"], 5), res["baseline"])

    def eva_view(w: dict | None) -> dict | None:
        if not w or "units" not in w:
            return None
        units = {}
        for u, x in w["units"].items():
            units[u] = {**_pick(x, ["label", "bins", "position_labels", "positions", "verdict"]),
                        "norm": _r(x["norm"]), "recent": _r({k: v for k, v in x["recent"].items()}),
                        "departure_by_year": _r(x["departure_by_year"]), "bends": len(x["bends"])}
        metas = [_r(_pick(g, ["members", "labels", "degrees", "born", "z", "same", "opposite", "phase", "phase_p",
                              "first_born", "pattern", "text", "grain"])) for g in w.get("metas", [])]
        pairs = [_r(_pick(p, ["members", "labels", "co_changes", "expected", "lift", "z", "same", "opposite",
                              "direction_p", "meta"])) for p in w.get("pairs", [])]
        heat = w.get("couplings")
        if heat:
            heat = {"types": heat.get("types", {}), "readings": heat.get("readings"), "alpha": _r(heat.get("alpha")),
                    "same_process": heat.get("same_process", []),
                    "links": [{**_r(_pick(x, ["members", "labels", "transform", "lag", "sign", "level", "p", "hits",
                                               "tries", "expected", "share", "union", "episodes", "longest", "text",
                                               "z_persistence", "p_persistence", "model_note"])),
                               **({"implied": {m: {"n": len(v), "first": v[:6]} for m, v in x["implied"].items()}}
                                  if x.get("implied") else {})} for x in heat.get("links", [])]}
        return {"grain": w.get("grain"), "months": w["months"], "baseline": w["baseline"], "split": w["split"],
                "settings": w.get("settings"), "units": units, "metas": metas, "pairs": pairs, "couplings": heat,
                "engine": {k: _pick(v, ["molettes", "meta_molettes", "statistical_entries", "extremes_seen"])
                           for k, v in w.get("engine", {}).items()}}

    eva = {"fine": eva_view(res["eva"].get("fine")), "extreme": eva_view(res["eva"].get("extreme")),
           "alone": {u: eva_view(w) for u, w in res["eva"].get("alone", {}).items()}}
    disc = res.get("discovery") or {}
    return {
        "id": cid, "title": title, "question": question, "created": res.get("created"),
        "regions": res["regions"], "period": res["period"], "baseline": res["baseline"],
        "variables": {k: _pick(v, ["key", "label", "topic", "units", "simple", "source", "collection", "variable",
                                   "first_year"]) for k, v in res["variables"].items()},
        "units": res["units"],
        "series": {u: {"months": s["months"], "values": _r(s["values"], 5)} for u, s in res["series"].items()},
        "trends": trends, "eva": eva,
        "maps": {u: [_r({"lat": c["lat"], "lon": c["lon"], "v": c["per_decade"], "p": c["p"]}, 3) for c in cells]
                 for u, cells in res["maps"].items()},
        "fields": {u: {**_pick(f, ["dlat", "dlon", "pairs", "sign_changes", "strong", "classes"]),
                       "borders": [{"a": b["a"], "b": b["b"], "strong": b["strong"]} for b in f["borders"]]}
                   for u, f in res.get("fields", {}).items()},
        "provenance": res.get("provenance", {}),
        "discovery": {"query": disc.get("query"), "keywords": disc.get("keywords", []),
                      "collections": {k: v[:8] for k, v in disc.get("collections", {}).items()},
                      "errors": disc.get("errors", [])},
        "dynamics": _r(res.get("dynamics") or dynamics.read(res)),
        "changes": _r({u: {k: v for k, v in ch.items()} for u, ch in (res.get("changes") or {}).items()}),
        "story": [{"kind": s["kind"], "text": s["text"], **({"unit": s["unit"]} if "unit" in s else {}),
                   **({"level": s["level"], "direction": s["direction"]} if "level" in s else {})}
                  for s in res.get("story", [])],
    }


def catalog() -> dict:
    """Regions and variables, for the page's question form (live mode)."""
    return {"regions": [r.as_dict() for r in REGIONS.values()],
            "variables": [v.as_dict() for v in VARIABLES.values()], "topics": TOPICS}


def render(cases: list[dict], live: bool = False, skeleton: bool = True) -> str:
    page = TEMPLATE.read_text(encoding="utf-8")
    blob = json.dumps({"cases": cases, "catalog": catalog(), "live": live}, separators=(",", ":"))
    page = page.replace("__DATA_JSON__", blob.replace("</", "<\\/"))
    page = page.replace("__STATS_JS__", STATS_JS.read_text(encoding="utf-8").replace("</", "<\\/"))
    if not skeleton:
        return page
    return ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            f'</head>\n<body>\n{page}\n</body>\n</html>\n')


def demo_cases() -> list[dict]:
    out = []
    for cid, title, question, name in DEMOS:
        path = INV / name
        if path.exists():
            out.append(slim(json.loads(path.read_text()), cid, title, question))
    return out


def main() -> None:
    cases = demo_cases()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "index.html").write_text(render(cases), encoding="utf-8")
    (OUT / "artifact.html").write_text(render(cases, skeleton=False), encoding="utf-8")
    size = (OUT / "artifact.html").stat().st_size
    print(f"{len(cases)} cases -> {OUT / 'index.html'} and artifact.html ({size / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()
