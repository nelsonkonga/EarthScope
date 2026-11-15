"""Ask Eva: the tools on the real land results, and the tool loop with a fake model (no API call)."""

from __future__ import annotations

import json
from types import SimpleNamespace as NS

import pytest

from detective import agent, land

HAVE = (land.OUT / "cameroon_full.json").exists()
need_data = pytest.mark.skipif(not HAVE, reason="land results not on disk")


@need_data
def test_find_place_and_report():
    t = agent.LandTools()
    f = t.find_place("GAROUA")["found"][0]
    assert f["country"] == "Cameroon" and f["on_the_map"]
    r = t.place_report(f["lat"], f["lon"])
    assert r["region"] == "cameroon_full"
    assert abs(r["cell"]["lat"] - f["lat"]) <= 0.25 and abs(r["cell"]["lon"] - f["lon"]) <= 0.3125
    lgp = r["indicators"]["lgp"]
    assert lgp["units"] == "days" and "classical_trend" in lgp and "eva" in lgp
    assert t.place_report(40.0, 2.0)["error"].startswith("outside")


@need_data
def test_read_series_months_and_yearly():
    t = agent.LandTools()
    s = t.read_series(9.3, 13.4, "PRECTOTCORR", [6, 7, 8, 9])
    assert "Jun-Jul-Aug-Sep" in s["series"] and s["classical_trend"]["per_decade"] is not None
    assert len(s["values"]) >= 40
    y = t.read_series(9.3, 13.4, "rain")
    assert y["series"].startswith("Rain") and "eva" in y
    assert "error" in t.read_series(9.3, 13.4, "rain", [6, 7])  # months only for POWER variables


@need_data
def test_rank_places_keeps_coordinates():
    t = agent.LandTools()
    r = t.rank_places("lgp", "worse", n=5)
    assert r["count"] >= 5 and len(r["places"]) == 5
    assert all(p["per_decade"] < 0 for p in r["places"])  # the growing season: higher is better
    assert any(round(p["lon"] * 1000) % 125 == 0 for p in r["places"])  # 13.75, not 13.8


def test_tool_schemas_are_strict():
    for tdef in agent.TOOLS:
        s = tdef["input_schema"]
        assert tdef["strict"] and s["additionalProperties"] is False
        assert set(s["required"]) == set(s["properties"])


class FakeTools:
    def __init__(self):
        self.calls = []

    def run(self, name, args):
        self.calls.append((name, args))
        return {"region": "r", "cell": {"lat": 9.5, "lon": 13.125}, "ok": True}


class FakeClient:
    """Answers with one tool call, then with text."""

    def __init__(self):
        self.requests = []
        self.beta = NS(messages=NS(create=self.create))

    def create(self, **kw):
        self.requests.append(kw)
        if len(self.requests) == 1:
            return NS(stop_reason="tool_use", content=[
                NS(type="text", text="Let me look."),
                NS(type="tool_use", id="tu_1", name="place_report", input={"lat": 9.3, "lon": 13.4, "indicators": None})])
        return NS(stop_reason="end_turn", content=[NS(type="text", text="The season shortened.")])


def test_loop_runs_tools_and_returns_focus():
    tools, client = FakeTools(), FakeClient()
    a = agent.Agent(tools=tools, client=client)
    out = a.ask("Is the season shorter near Garoua?", [{"role": "assistant", "text": "hello"},
                                                         {"role": "user", "text": "hi"},
                                                         {"role": "assistant", "text": "Ask me."}])
    assert out["text"] == "The season shortened."
    assert out["tools"] == ["place_report"] and tools.calls[0][1]["lat"] == 9.3
    assert out["focus"] == [{"lat": 9.5, "lon": 13.125, "region": "r", "kind": "cell"}]
    first = client.requests[0]
    assert first["model"] == agent.MODEL and first["fallbacks"] == "default"
    assert first["messages"][0]["role"] == "user"  # a leading assistant turn is dropped
    second = client.requests[1]["messages"]
    assert second[-1]["role"] == "user" and second[-1]["content"][0]["tool_use_id"] == "tu_1"
    assert json.loads(second[-1]["content"][0]["content"])["ok"] is True


def test_limiter_and_empty_question():
    lim = agent.Limiter(per_hour=2)
    assert lim.allow("a") and lim.allow("a") and not lim.allow("a") and lim.allow("b")
    with pytest.raises(ValueError):
        agent.Agent(tools=FakeTools(), client=FakeClient()).ask("   ")


# ------------------------------------------------ beyond the map: chosen data, imported once
def _fake_store(tmp_path):
    import random

    from detective.datastore import DataStore, cells_in_box

    calls = []

    def series(param, la, lo):
        rng = random.Random(f"{param}{la}{lo}")
        x, out = 0.0, {}
        for y in range(1981, 2026):
            for m in range(1, 13):
                x = 0.6 * x + rng.gauss(0, 1)
                base = x if param != "GWETROOT" else 0.8 * out.get((y, m - 1) if m > 1 else (y - 1, 12), 0) + rng.gauss(0, 1)
                out[(y, m)] = 20 + 3 * (m in (6, 7, 8, 9)) + 0.02 * (y - 1981) + base
        return out

    def box(param, s, n, w, e, offline=False):
        calls.append(("box", param))
        return [(la, lo, series(param, la, lo)) for la, lo in cells_in_box(param, s, n, w, e)]

    def point(param, la, lo, offline=False):
        calls.append(("point", param))
        return series(param, la, lo)

    return DataStore(tmp_path, power_box=box, power_point=point, seed=False), calls


def test_eva_trend_compares_places_and_imports_once(tmp_path):
    st, calls = _fake_store(tmp_path)
    T = agent.LandTools(store=st)
    r = T.eva_trend("T2M", ["4.0,10.0", "-10,-6,20,25"], [6, 7, 8, 9])
    assert [p.get("error") for p in r["places"]] == [None, None]
    assert all(p["classical_trend"] and p["eva"] for p in r["places"]) and len(r["focus"]) == 2
    assert r["months"] == "Jun-Jul-Aug-Sep"
    n = len(calls)
    r2 = T.eva_trend("T2M", ["-10,-6,20,25"], None)  # the same box again: the store answers
    assert len(calls) == n and r2["places"][0]["data"]["from_store"] == r2["places"][0]["data"]["cells"]


def test_eva_links_on_chosen_variables(tmp_path):
    st, _calls = _fake_store(tmp_path)
    T = agent.LandTools(store=st)
    r = T.eva_links(["T2M", "GWETROOT"], ["4.0,10.0"])
    assert "error" not in r and r["series"] == ["Air temperature", "Root-zone soil wetness"]
    assert isinstance(r["links"], list) and "how_to_read" in r
    assert "error" in T.eva_links(["T2M"], ["4.0,10.0"])  # one series: nothing to link
    assert "error" in T.eva_links(["CLOUD_AMT", "T2M"], ["4.0,10.0"])  # starts in 1984


@need_data
def test_both_regions_at_once():
    T = agent.LandTools()
    o = T.region_overview("all")
    assert len(o["regions"]) == len(T.regions()) >= 2
    r = T.rank_places("lgp", "worse", "all", 10)
    assert r["region"] == "all" and len({(p["lat"], p["lon"]) for p in r["places"]}) == len(r["places"])
