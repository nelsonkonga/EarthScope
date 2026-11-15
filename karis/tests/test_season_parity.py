"""JS copy of the season statistics (detective/stats.js) against Python, through node (fast subset)."""

import random
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "checks"))

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="needs node")


def test_js_season_statistics_match_python():
    import season_stats_parity as P

    if not (P.report.INV / "arctic.json").exists():
        pytest.skip("no investigation file")
    series = [s for s in P.load_series() if s[0] == "arctic.json"][:2]
    jobs = P.jobs_for(series, random.Random(1))
    import json
    import subprocess
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "jobs.json").write_text(json.dumps([[j[1], j[2], list(j[3]), j[4]] for j in jobs]))
        (Path(d) / "run.js").write_text(P.RUN)
        res = subprocess.run(["node", str(Path(d) / "run.js"), str(P.JS), str(Path(d) / "jobs.json")],
                             capture_output=True, text=True, check=True)
    js = json.loads(res.stdout)
    bad, worst = [], {}
    for (label, months, values, base, sel), got in zip(jobs, js):
        want = P.stats.season_trend(P.py_series(months, values), base, sel)
        assert (want is None) == (got is None), label
        if want is not None:
            P.compare(want, got, "r", worst, bad)
    assert not bad, bad[:5]
