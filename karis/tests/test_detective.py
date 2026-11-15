"""Earth System Trend Detective (detective/): statistics checked against scipy and known
answers, Eva's lens and meta molettes on synthetic series whose truth is known, and the
plumbing (MCP messages, regions, POWER parsing). Offline: no network is used."""

import json
import math
import random

import numpy as np
import pytest
from scipy import stats as st

from detective import power, stats
from detective.mcp import EarthdataMCP, MCPError, parse_messages
from detective.regions import REGIONS, Region, parse_region
from detective.watch import EXTREME_CUTS, PhaseLens, Watch, evidence_bins


def monthly(values, y0=1981):
    return {(y0 + i // 12, i % 12 + 1): v for i, v in enumerate(values)}


def seasonal(n_years=45, trend=0.0, noise=1.0, seed=0, phi=0.0):
    """A seasonal cycle + a linear trend per year + AR(1) noise."""
    rng = np.random.default_rng(seed)
    e, out = 0.0, []
    for i in range(12 * n_years):
        e = phi * e + rng.normal(0, noise)
        out.append(10 * math.sin(2 * math.pi * (i % 12) / 12) + trend * i / 12 + e)
    return monthly(out)


# ---------------------------------------------------------------- statistics
def test_ols_matches_scipy_when_residuals_are_not_autocorrelated():
    t = np.arange(60, dtype=float)
    y = 0.3 * t + np.array([(-1) ** i for i in range(60)], float) * 2  # alternating: r1 < 0
    got = stats.ols(t, y)
    ref = st.linregress(t, y)
    assert got["r1"] < 0 and got["n_eff"] == 60
    assert got["slope"] == pytest.approx(ref.slope)
    assert got["p"] == pytest.approx(ref.pvalue, rel=1e-6)


def test_ols_autocorrelation_widens_the_interval():
    s = seasonal(trend=0.02, phi=0.8, seed=3)
    a = stats.anomalies(s, (1981, 2010))
    t = np.array([stats.decimal_year(k) for k in a])
    y = np.array(list(a.values()))
    got = stats.ols(t, y)
    naive = st.linregress(t, y)
    assert got["n_eff"] < 0.3 * len(y)
    assert got["p"] > naive.pvalue


def test_mann_kendall_counts_every_pair():
    rng = random.Random(1)
    y = [rng.randint(0, 6) for _ in range(40)]  # many ties
    s = sum((y[j] > y[i]) - (y[j] < y[i]) for i in range(40) for j in range(i + 1, 40))
    got = stats.mann_kendall(y, autocorr=False)
    assert got["S"] == s
    ties = sum(c * (c - 1) * (2 * c + 5) for c in np.unique(y, return_counts=True)[1])
    assert got["var"] == pytest.approx((40 * 39 * 85 - ties) / 18)


def test_mann_kendall_agrees_with_kendall_tau():
    rng = np.random.default_rng(2)
    y = 0.05 * np.arange(80) + rng.normal(size=80)
    got = stats.mann_kendall(y, autocorr=False)
    tau, p = st.kendalltau(np.arange(80), y, method="asymptotic")
    assert got["tau"] == pytest.approx(tau)
    assert got["p"] == pytest.approx(p, rel=0.05)  # ours has the continuity correction


def test_hamed_rao_inflates_the_variance_of_a_persistent_series():
    rng = np.random.default_rng(4)
    e, y = 0.0, []
    for _ in range(300):
        e = 0.85 * e + rng.normal()
        y.append(e)
    got = stats.mann_kendall(y, autocorr=True)
    assert got["factor"] > 2
    assert got["p"] > stats.mann_kendall(y, autocorr=False)["p"]


def test_sen_slope_matches_scipy():
    rng = np.random.default_rng(5)
    t = np.arange(45, dtype=float)
    y = -0.2 * t + rng.normal(size=45)
    got = stats.sen(t, y)
    ref = st.theilslopes(y, t)
    assert got["slope"] == pytest.approx(ref.slope)
    assert got["ci"][0] <= got["slope"] <= got["ci"][1]
    assert got["ci"][0] == pytest.approx(ref.low_slope, rel=0.05)
    assert got["ci"][1] == pytest.approx(ref.high_slope, rel=0.05)


def test_pettitt_finds_a_step():
    rng = np.random.default_rng(6)
    y = np.concatenate([rng.normal(0, 1, 25), rng.normal(3, 1, 20)])
    got = stats.pettitt(y)
    assert abs(got["at"] - 25) <= 1 and got["p"] < 0.01


def test_years_to_detect_formula():
    # Weatherhead et al. 1998: n* = (3.3 sigma / |omega| * sqrt((1+phi)/(1-phi)))^(2/3)
    assert stats.years_to_detect(0.1, 1.0, 0.0) == pytest.approx(33 ** (2 / 3))
    assert stats.years_to_detect(0.1, 1.0, 0.5) > stats.years_to_detect(0.1, 1.0, 0.0)


def test_trend_report_recovers_a_known_trend_and_ignores_the_season():
    rep = stats.trend_report(seasonal(trend=0.05, noise=0.8, seed=7), (1981, 2010))
    lo, hi = rep["per_decade_ci"]
    assert lo <= 0.5 <= hi
    assert rep["verdict"]["level"] == "significant" and rep["verdict"]["direction"] == "rising"
    flat = stats.trend_report(seasonal(trend=0.0, noise=0.8, seed=8), (1981, 2010))
    assert flat["verdict"]["level"] != "significant"


# --------------------------------------------------------------- Eva's lens
def test_evidence_bins_follow_the_data():
    assert evidence_bins(360) == 4  # 30 years of months: 16 transitions seen ~20 times each
    assert evidence_bins(30) == 3 and evidence_bins(10 ** 6) == 9


def test_fine_lens_is_equiprobable_on_the_baseline_and_sees_the_unseen():
    s = seasonal(noise=1.0, seed=9)
    lens = PhaseLens(s, (1981, 2010))
    pos = [lens.position(k[1], v) for k, v in s.items() if k[0] <= 2010]
    shares = [pos.count(i) / len(pos) for i in range(lens.bins)]
    assert all(abs(x - 1 / lens.bins) < 0.06 for x in shares)
    assert lens.position(7, 1e6) == lens.bins and lens.position(7, -1e6) == -1


def test_extreme_lens_marks_the_tails():
    s = seasonal(noise=1.0, seed=10)
    lens = PhaseLens(s, (1981, 2010), cuts=EXTREME_CUTS)
    pos = [lens.position(k[1], v) for k, v in s.items() if k[0] <= 2010]
    assert set(pos) <= {-1, 0, 1}
    assert pos.count(1) / len(pos) == pytest.approx(0.1, abs=0.04)
    assert pos.count(-1) / len(pos) == pytest.approx(0.1, abs=0.04)


# ------------------------------------------------------------- Eva watches
def test_eva_sees_a_dynamic_leave_its_norm_and_a_stable_one_stay():
    rng = np.random.default_rng(11)
    up = seasonal(noise=1.0, seed=12)
    up = {k: v + (1.5 if k[0] > 2010 else 0.0) for k, v in up.items()}  # a new level after the baseline
    calm = seasonal(noise=1.0, seed=13)
    res = Watch({"up": up, "calm": calm}, (1981, 2010)).run()
    u, c = res["units"]["up"], res["units"]["calm"]
    assert u["verdict"]["level"] == "left its norm" and u["verdict"]["direction"] == "up"
    assert u["recent"]["top_share"] > 2 * u["recent"]["expected_share"]
    assert c["verdict"]["level"] == "within its norm"
    assert rng is not None


def test_eva_learns_nothing_while_judging():
    """Pass B judges the recent years against the baseline norm without counting them."""
    w = Watch({"a": seasonal(seed=14), "b": seasonal(seed=15)}, (1981, 2010))
    dyn, _reads, _back = w.pass_b()
    before = {k: m.size() for k, m in dyn.mol.items()}
    dyn.begin(2, w.obs(0))
    for t in range(1, len(w.months)):
        dyn.tick(2, w.obs(t), learn=False)
    assert {k: m.size() for k, m in dyn.mol.items()} == before


def test_one_event_moving_two_dynamics_gives_a_meta_molette_with_its_direction():
    """Shared extremes, in opposite directions: a meta molette at the extreme grain, anti-phase;
    an independent dynamic is left alone."""
    rng = np.random.default_rng(16)
    n = 12 * 45
    shock = np.where(rng.random(n) < 0.12, rng.choice([-3.0, 3.0], n), 0.0)
    a = monthly(list(shock + rng.normal(0, 0.5, n)))
    b = monthly(list(-shock + rng.normal(0, 0.5, n)))
    c = monthly(list(rng.normal(0, 1, n)))
    res = Watch({"a": a, "b": b, "c": c}, (1981, 2010), cuts=EXTREME_CUTS).run()
    pairs = {tuple(g["members"]): g for g in res["metas"]}
    assert ("a", "b") in pairs
    assert pairs[("a", "b")]["phase"] < -0.5
    assert not any("c" in m for m in pairs)


# --------------------------------------------------------- heatmaps of departures
def _departures(rng, n, rate=0.12):
    return list(np.where(rng.random(n) < rate, rng.choice([-1, 1], n), 0))


def test_a_mirror_one_month_later_is_read_with_its_direction_and_its_delay():
    """b leaves its norm the opposite way one month after a (plus its own noise): the heat layer
    keeps the transformation (x+1, −y) — direction and delay — and leaves an independent c alone."""
    from detective.heat import couplings
    rng = np.random.default_rng(21)
    n = 540
    a = _departures(rng, n)
    b = [0] + [-x for x in a[:-1]]
    b = [x if rng.random() > 0.3 else 0 for x in b]  # b misses 30 % of them
    c = _departures(rng, n)
    res = couplings({"a": a, "b": b, "c": c}, {}, [str(t) for t in range(n)])
    links = {tuple(x["members"]): x for x in res["links"]}
    ab = links[("a", "b")]
    assert ab["level"] == "proven" and ab["lag"] == 1 and ab["sign"] == -1 and ab["transform"] == "(x+1,-y)"
    assert "a comes first" in ab["text"] and "opposite way" in ab["text"]
    assert not any(x["level"] == "proven" for k, x in links.items() if "c" in k)


def test_a_shared_trend_is_not_a_link():
    """Two independent dynamics that both leave their norm upward late in the record: chance read
    at the same moment explains their joint months; chance read over the whole record would not."""
    from detective.heat import Reading, Shift, couplings, heatmap
    rng = np.random.default_rng(22)
    n = 540
    late = lambda: [1 if (t > 360 and rng.random() < 0.6) else (_departures(rng, 1, 0.05)[0]) for t in range(n)]
    a, b = late(), late()
    res = couplings({"a": a, "b": b}, {}, [str(t) for t in range(n)])
    assert not any(x["level"] == "proven" for x in res["links"])
    r = Reading(heatmap(a), heatmap(b), Shift(0, 1), n, window=n)  # chance over the whole record
    assert r.p < 1e-6  # … would have taken the trend for a link


def test_long_episodes_of_two_independent_dynamics_are_not_a_link():
    """Each dynamic leaves its norm for months at a time (persistence): month-by-month coincidences
    then come in bunches. Moving one of them 1 to 5 years gives the spread of those bunches; two
    independent dynamics stay within it, a real link stands far above it."""
    from detective.heat import Shift, couplings, heatmap, persistence_test
    rng = np.random.default_rng(25)
    n = 540

    def episodes_(rate=0.03, length=8):
        out = [0] * n
        for t in range(n):
            if rng.random() < rate:
                s = int(rng.choice([-1, 1]))
                for k in range(t, min(n, t + length)):
                    out[k] = s
        return out
    a, b = episodes_(), episodes_()
    res = couplings({"a": a, "b": b}, {}, [str(t) for t in range(n)])
    assert not any(x["level"] == "proven" for x in res["links"])
    z, _p = persistence_test(heatmap(a), heatmap([-x for x in a]), Shift(0, -1), n)
    assert z > 4


def test_two_dynamics_that_almost_always_leave_their_norm_together_are_one():
    """The union simplified into a transition: both readings above HOLD, one sure; each implies
    the months the other left its norm without it."""
    from detective.heat import couplings
    rng = np.random.default_rng(23)
    n = 540
    a = _departures(rng, n, 0.15)
    b = [x if rng.random() > 0.15 else 0 for x in a]
    b = [x if x else (_departures(rng, 1, 0.02)[0]) for x in b]
    res = couplings({"a": a, "b": b}, {"a": "A", "b": "B"}, [str(t) for t in range(n)])
    x = res["links"][0]
    assert x["union"] and x["transform"] == "(x,y)"
    assert x["implied"]["b"] and x["implied"]["a"]
    assert "one dynamic" in x["text"]


def test_the_same_transformation_in_two_regions_is_one_process():
    from detective.heat import same_process
    units = {"I@n": {"variable": "ICE", "region": "n", "region_name": "North"},
             "T@n": {"variable": "AIR", "region": "n", "region_name": "North"},
             "I@s": {"variable": "ICE", "region": "s", "region_name": "South"},
             "T@s": {"variable": "AIR", "region": "s", "region_name": "South"}}
    links = [{"members": ["I@n", "T@n"], "level": "proven", "transform": "(x,-y)", "lag": 0, "sign": -1},
             {"members": ["T@s", "I@s"], "level": "proven", "transform": "(x,-y)", "lag": 0, "sign": -1},
             {"members": ["I@n", "T@s"], "level": "proven", "transform": "(x,y)", "lag": 0, "sign": 1}]
    sp = same_process(links, units)
    assert len(sp) == 1 and sp[0]["transform"] == "(x,-y)" and sp[0]["regions"] == ["North", "South"]


def test_watch_reports_the_heat_layer_at_the_extreme_grain():
    rng = np.random.default_rng(24)
    n = 12 * 45
    shock = np.where(rng.random(n) < 0.12, rng.choice([-3.0, 3.0], n), 0.0)
    a = monthly(list(shock + rng.normal(0, 0.5, n)))
    b = monthly(list(-shock + rng.normal(0, 0.5, n)))
    ext = Watch({"a": a, "b": b}, (1981, 2010), cuts=EXTREME_CUTS).run()
    assert ext["couplings"]["links"][0]["transform"] == "(x,-y)"
    assert Watch({"a": a, "b": b}, (1981, 2010)).run()["couplings"] is None  # fine grain: not read


# ------------------------------------------------------------------ plumbing
def test_mcp_messages_json_and_sse():
    sse = 'event: message\ndata: {"jsonrpc":"2.0","id":1,"result":{"ok":true}}\n\n'
    assert parse_messages(sse, "text/event-stream")[0]["result"]["ok"] is True
    assert parse_messages('{"jsonrpc":"2.0","id":2,"result":{}}', "application/json")[0]["id"] == 2
    assert parse_messages("", "application/json") == []


def test_mcp_cache_replays_offline(tmp_path):
    m = EarthdataMCP(cache=tmp_path, offline=True)
    with pytest.raises(MCPError):
        m.call("get_keywords", query="sea ice")
    import hashlib
    key = hashlib.sha1(json.dumps(["get_keywords", {"query": "sea ice"}], sort_keys=True).encode()).hexdigest()[:20]
    (tmp_path / f"get_keywords-{key}.json").write_text(json.dumps({"keywords": [{"prefLabel": "SEA ICE"}]}))
    assert m.call("get_keywords", query="sea ice")["keywords"][0]["prefLabel"] == "SEA ICE"


def test_regions_tiles_and_wkt():
    r = Region("x", "X", 12, 18, -15, 20)
    tiles = r.tiles(10)
    assert len(tiles) == 4 and all(t.east - t.west <= 10 + 1e-9 and t.north - t.south <= 10 for t in tiles)
    assert r.wkt().startswith("POLYGON((-15 12, 20 12")
    assert parse_region("sahel") is REGIONS["sahel"]
    assert parse_region("10,20").south == 9


def test_power_parsing_and_area_mean():
    got = power._months({"198101": 1.5, "198113": 9.0, "198102": -999.0})
    assert got == {(1981, 1): 1.5, (1981, 2): None}
    cells = [(0.0, 0.0, {(1981, 1): 1.0}), (60.0, 0.0, {(1981, 1): 4.0}), (30.0, 0.0, {(1981, 1): 5.0})]
    still = [(10.0, 0.0, {(1981, 1): 0.0, (1981, 2): 0.0})]
    assert power.informative(still) == []
    w = [1.0, 0.5, math.cos(math.radians(30))]
    assert power.area_mean(cells)[(1981, 1)] == pytest.approx((1 * w[0] + 4 * w[1] + 5 * w[2]) / sum(w))


def test_a_transition_is_read_from_both_ends():
    """The user's rule: a transition is not a question of time and is symmetric — the reverse
    reading comes from the same joint counts (P(first | tail, last))."""
    from eva.dynamics import Molette, WORLD
    m = Molette()
    for a, b, n in ((0, 1, 6), (2, 1, 2), (1, 1, 4)):
        for _ in range(n):
            m.record(a, WORLD, b, 2.0)
    rev = Watch.backwards(m)
    assert rev[((), 1)] == {0: 6, 2: 2, 1: 4}
    w = Watch({"a": seasonal(seed=17), "b": seasonal(seed=18)}, (1981, 2010))
    _dyn, _reads, back = w.pass_b()
    assert sum(1 for t in range(len(w.months)) if "a" in back[t]) > 0.9 * len(w.months)


# ------------------------------------------------- dynamics at the level of the year (RESULTS § 27)
def _annual(values, start=1981):
    return {"annual": {"years": [float(start + i) for i in range(len(values))], "values": list(values)}}


def _ar1(n, phi, sd, seed):
    import random as _r
    rng, x, out = _r.Random(seed), 0.0, []
    for _ in range(n):
        x = phi * x + (1 - phi * phi) ** 0.5 * rng.gauss(0, sd)
        out.append(x)
    return out


def test_a_steady_trend_with_persistent_noise_is_one_dynamic():
    """The lesson of the curves: read at the year, with the noise measured where it is
    (persistence included), a steady trend is one dynamic — no invented change of regime."""
    from detective import dynamics

    multi = 0
    for seed in range(20):
        noise = _ar1(45, 0.3, 1.0, seed)  # as persistent as the upper quarter of the real yearly series
        d = dynamics.annual(_annual([0.05 * i + e for i, e in enumerate(noise)]))
        multi += len(d["dynamics"]) > 1
    assert multi <= 2  # about 5 % (RESULTS § 27)


def test_pettitt_reports_a_jump_in_a_steady_trend():
    """Why the detective no longer calls Pettitt's year « when it shifted »: on a steady trend
    with no jump at all, the test is significant (a trend has no single level)."""
    from detective.stats import pettitt

    y = [0.05 * i + e for i, e in enumerate(_ar1(45, 0.5, 1.0, 3))]
    assert pettitt(y)["p"] < 0.05


def test_a_change_of_regime_is_found_where_it_happened():
    """Flat until 2000, then rising fast: two dynamics, the change around 2000."""
    from detective import dynamics

    noise = _ar1(45, 0.3, 0.3, 1)
    y = [(0.0 if 1981 + i <= 2000 else 0.15 * (1981 + i - 2000)) + e for i, e in enumerate(noise)]
    d = dynamics.annual(_annual(y))
    assert len(d["dynamics"]) == 2
    assert 1997 <= d["transitions"][0] <= 2005  # where the two dynamics meet
    assert abs(d["dynamics"][0]["per_decade"]) < 0.5 < d["dynamics"][1]["per_decade"]


def test_changes_shared_by_several_variables_are_told_against_chance():
    """The transitions' own meta molettes: several variables changing together are told, with how
    often chance would gather as many; changes at scattered years are not a shared change."""
    from detective import dynamics

    def res_with(breaks):
        trends, units = {}, {}
        for k, (b, seed) in enumerate(breaks):
            noise = _ar1(45, 0.3, 0.3, seed)
            trends[f"V{k}"] = _annual([(0.0 if 1981 + i <= b else 0.2 * (1981 + i - b)) + e for i, e in enumerate(noise)])
            units[f"V{k}"] = {"variable": f"V{k}", "region": "r", "region_name": "Region"}
        return {"trends": trends, "units": units}

    res = res_with([(2004, 1), (2004, 2), (2004, 3), (2004, 4)])
    sh = dynamics.read(res)["shared"]
    assert sh and len(sh[0]["members"]) >= 3 and sh[0]["p"] < 0.01 and abs(sh[0]["year"] - 2004) <= 2
    res = res_with([(1990, 1), (2004, 2), (2015, 3)])
    assert all(len(s["members"]) < 3 or s["p"] >= 0.01 for s in dynamics.read(res)["shared"])


def _field(change: bool, cells: int = 12, seed: int = 0):
    """Grid cells of one region, 1981–2025: a common trend, noise shared by the cells and their own;
    with ``change``, the trend turns upward in 2000 in every cell."""
    rng = random.Random(seed)
    common = [rng.gauss(0, 0.15) for _ in range(45)]
    out = []
    for c in range(cells):
        own = [rng.gauss(0, 0.1) for _ in range(45)]
        s = {}
        for i, y in enumerate(range(1981, 2026)):
            v = 0.01 * i + (0.15 * (y - 2000) if change and y > 2000 else 0.0) + common[i] + own[i]
            for m in range(1, 13):
                s[(y, m)] = v
        out.append((10.0 + c // 4, 20.0 + c % 4, s))
    return out


def test_changes_of_dynamic_are_mapped_over_the_cells_against_chance():
    """« les transitions de dynamiques ont aussi leur heatmap […] les types de transitions » — every
    cell read at the level of a trend; many cells turning the same way the same years are a change of
    the region's dynamic, told only if chance (the same fields with no change, shuffled in blocks
    across all cells together) rarely gathers as many."""
    from detective import changes

    r = changes.read_cells(_field(True), draws=99)
    assert r["changes"], r
    c = r["changes"][0]
    assert c["type"] == "trend turned upward" and 1996 <= c["year"] <= 2004 and c["cells"] >= 9
    assert changes.read_cells(_field(False, seed=1), draws=99)["changes"] == []


# ------------------------------------------------------- season / month filter
def _monthly_dict(values, first_year=1981):
    return {(first_year + i // 12, i % 12 + 1): v for i, v in enumerate(values)}


def test_season_plan_wraps_the_year_end_only_when_the_selection_does():
    assert stats.season_plan([12, 1, 2]) == ((1, 2, 12), frozenset({12}))
    assert stats.season_plan([11, 12, 1, 2]) == ((1, 2, 11, 12), frozenset({11, 12}))
    assert stats.season_plan([3, 4, 5]) == ((3, 4, 5), frozenset())
    assert stats.season_plan(range(1, 13))[1] == frozenset()
    with pytest.raises(ValueError):
        stats.season_plan([0, 1])


def test_djf_takes_december_of_the_previous_year_and_drops_incomplete_winters():
    s = {(y, m): float(100 * y + m) for y in range(1989, 1992) for m in range(1, 13)}
    djf = stats.seasonal_annual_means(s, (12, 1, 2))
    assert set(djf) == {1990, 1991, 1992} - {1992}  # 1989 lacks its December, 1992 has no data
    assert djf[1990] == pytest.approx(np.mean([100 * 1989 + 12, 100 * 1990 + 1, 100 * 1990 + 2]))
    s[(1990, 2)] = None
    assert 1990 not in stats.seasonal_annual_means(s, (12, 1, 2))


def test_all_twelve_months_is_the_annual_mean():
    s = _monthly_dict(list(np.random.default_rng(1).normal(size=12 * 10)))
    assert stats.seasonal_annual_means(s) == stats.annual_means(s)
    assert stats.seasonal_annual_means(s, range(1, 13)) == stats.annual_means(s)


def test_season_trend_reuses_the_annual_tests_and_isolates_a_season():
    # a trend only in summer: JJA sees it, DJF does not
    rng = np.random.default_rng(3)
    vals = []
    for i in range(12 * 30):
        y, m = divmod(i, 12)
        vals.append(rng.normal(0, 0.3) + (0.1 * y if m in (5, 6, 7) else 0.0))
    s = _monthly_dict(vals)
    full = stats.trend_report(s, (1981, 2000))
    allm = stats.season_trend(s, (1981, 2000), range(1, 13))
    assert allm["annual"]["sen"]["slope"] == pytest.approx(full["annual"]["sen"]["slope"], rel=1e-12)
    assert allm["annual"]["mann_kendall"]["p"] == pytest.approx(full["annual"]["mann_kendall"]["p"], rel=1e-9)
    assert allm["verdict"]["level"] == full["verdict"]["level"]
    jja = stats.season_trend(s, (1981, 2000), stats.SEASONS["JJA"])
    djf = stats.season_trend(s, (1981, 2000), stats.SEASONS["DJF"])
    assert jja["verdict"]["level"] == "significant" and jja["per_decade"] == pytest.approx(1.0, abs=0.15)
    assert djf["verdict"]["level"] != "significant"
    assert jja["months"] == [6, 7, 8]
    assert len(jja["anomalies"]) == len(jja["annual"]["years"])


def test_season_trend_needs_four_seasons():
    s = _monthly_dict(list(range(12 * 3)))
    assert stats.season_trend(s, (1981, 1983), (12, 1, 2)) is None
