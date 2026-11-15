"""The page's JavaScript copy of the season / month trend statistics (detective/stats.js) against
the Python reference (detective/stats.py: season_trend), on every demo unit.

Usage: season_stats_parity.py      (needs node; exits 1 beyond the tolerances)

Every unit of the investigation files x the 5 presets x 20 random month subsets (wrap-around ones
included). Both get the series exactly as the page embeds it (5 significant digits).
Tolerances: slopes, CIs and every other number 1e-9 relative (1e-12 absolute floor), p-values 1e-7
absolute, same verdict level.
"""

from __future__ import annotations

import json
import math
import random
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from detective import report, stats  # noqa: E402

JS = ROOT / "detective" / "stats.js"
RUN = """
const api = require(process.argv[2]);
const jobs = JSON.parse(require("fs").readFileSync(process.argv[3], "utf8"));
const out = jobs.map(([months, values, base, sel]) => api.seasonTrend(months, values, base, sel));
console.log(JSON.stringify(out, (k, v) => (typeof v === "number" && !Number.isFinite(v) ? (Number.isNaN(v) ? "NaN" : v > 0 ? "Inf" : "-Inf") : v)));
"""
PRESETS = {"year": list(range(1, 13)), **{k: list(v) for k, v in stats.SEASONS.items()}}


def load_series() -> list[tuple[str, str, list, list, tuple]]:
    out = []
    for _cid, _t, _q, name in report.DEMOS:
        path = report.INV / name
        if not path.exists():
            continue
        res = json.loads(path.read_text())
        for u, s in res["series"].items():
            out.append((name, u, s["months"], report._r(s["values"], 5), tuple(res["baseline"])))
    return out


def py_series(months, values) -> dict:
    return {(int(m[:4]), int(m[5:7])): v for m, v in zip(months, values)}


def num(x):
    return float("nan") if x == "NaN" else float("inf") if x == "Inf" else float("-inf") if x == "-Inf" else x


def compare(a, b, path, worst, bad):
    """Walk both results; update worst deviations by kind."""
    if isinstance(a, dict):
        for k in a:
            if k not in b:
                bad.append(f"{path}.{k} missing in js")
                continue
            compare(a[k], b[k], f"{path}.{k}", worst, bad)
        return
    if isinstance(a, (list, tuple)):
        if len(a) != len(b):
            bad.append(f"{path} length {len(a)} vs {len(b)}")
            return
        for i, (x, y) in enumerate(zip(a, b)):
            compare(x, y, f"{path}[{i}]", worst, bad)
        return
    if isinstance(a, str):
        if a != b:
            bad.append(f"{path} {a!r} vs {b!r}")
        return
    if a is None or b is None:
        if a is not b:
            bad.append(f"{path} {a} vs {b}")
        return
    b = num(b)
    if isinstance(a, float) and math.isnan(a) or isinstance(b, float) and math.isnan(b):
        if not (math.isnan(a) and math.isnan(b)):
            bad.append(f"{path} {a} vs {b}")
        return
    if math.isinf(a) or math.isinf(b):
        if a != b:
            bad.append(f"{path} {a} vs {b}")
        return
    if path.endswith(".p") or path.endswith(".K"):
        d = abs(a - b)
        kind, tol = "p", 1e-7
        if path.endswith(".K"):
            kind, tol = "other", 1e-9 * max(1, abs(a))
    else:
        d = abs(a - b) / max(abs(a), 1e-12)
        kind, tol = ("slope" if "slope" in path or ".ci" in path or "per_decade" in path else "other"), 1e-9
        if abs(a - b) < 1e-12:
            d = 0.0
    worst[kind] = max(worst.get(kind, 0.0), d)
    if d > tol:
        bad.append(f"{path} {a} vs {b} (dev {d:.3g})")


def jobs_for(series, rng):
    jobs = []
    for name, u, months, values, base in series:
        sels = [(k, v) for k, v in PRESETS.items()]
        for i in range(20):
            if i < 4:  # wrap-around ones: a run of consecutive months across the year end
                start, length = rng.choice([11, 12, 10, 9]), rng.randint(2, 6)
                sel = sorted({(start - 1 + j) % 12 + 1 for j in range(length)})
            else:
                sel = sorted(rng.sample(range(1, 13), rng.randint(1, 12)))
            sels.append((f"rand{i}", sel))
        for label, sel in sels:
            jobs.append((f"{name}:{u}:{label}:{sel}", months, values, base, sel))
    return jobs


def main() -> int:
    rng = random.Random(7)
    series = load_series()
    jobs = jobs_for(series, rng)
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "jobs.json").write_text(json.dumps([[j[1], j[2], list(j[3]), j[4]] for j in jobs]))
        (Path(d) / "run.js").write_text(RUN)
        res = subprocess.run(["node", str(Path(d) / "run.js"), str(JS), str(Path(d) / "jobs.json")],
                             capture_output=True, text=True, check=True)
    js = json.loads(res.stdout)
    worst: dict = {}
    bad: list = []
    for (label, months, values, base, sel), got in zip(jobs, js):
        want = stats.season_trend(py_series(months, values), base, sel)
        if want is None or got is None:
            if not (want is None and got is None):
                bad.append(f"{label}: one side None")
            continue
        local: list = []
        compare(want, got, "r", worst, local)
        if want["verdict"]["level"] != got["verdict"]["level"]:
            local.append("verdict level differs")
        bad += [f"{label}: {m}" for m in local]
    print(f"{len(jobs)} cases ({len(series)} units); max deviations: " +
          ", ".join(f"{k} {v:.3g}" for k, v in sorted(worst.items())))
    for m in bad[:25]:
        print("DIFF", m)
    print("OK" if not bad else f"{len(bad)} differences")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
