"""Land intelligence (detective/land.py, budget.py, land_page.py): the published definitions, the
false discovery rate, the calibrated forecast, the budget's linear programme, and one synthetic
region end to end. No network: everything runs on made-up cells."""

from __future__ import annotations

import math
import random

import numpy as np
import pytest
from scipy.optimize import linprog

from detective import budget, land, land_page
from detective.regions import Region

MONTHS = land._months()


def test_extraterrestrial_radiation_matches_fao56_example():
    # FAO-56 example 8: 20° S, 3 September (day 246): Ra = 32.2 MJ/m²/day, i.e. 13.1 mm/day
    assert land.extraterrestrial_mm(-20.0, 246) == pytest.approx(0.408 * 32.2, rel=0.01)


def test_growing_period_wet_dry_and_cold():
    n = len(MONTHS)
    pet = np.full((1, n), 4.0)
    warm = np.full((1, n), 25.0)
    wet = land.growing_period(np.full((1, n), 6.0), pet, warm, MONTHS)
    dry = land.growing_period(np.full((1, n), 0.5), pet, warm, MONTHS)
    cold = land.growing_period(np.full((1, n), 6.0), pet, np.full((1, n), 2.0), MONTHS)
    assert wet[0, 0] == 365 and wet[0, 3] == 366  # 1984 is a leap year
    assert dry.max() == 0 and cold.max() == 0


def test_growing_period_counts_the_rains_and_the_soil_store_after_them():
    # rains from May to September (5 months), dry otherwise: the season is the rains plus the days the
    # 100 mm store keeps feeding the plants after them
    P = np.array([[8.0 if m in (5, 6, 7, 8, 9) else 0.0 for _y, m in MONTHS]])
    pet = np.full_like(P, 5.0)
    T = np.full_like(P, 28.0)
    lgp = land.growing_period(P, pet, T, MONTHS)[0]
    assert 140 <= lgp[5] <= 200
    no_store = land.growing_period(P, pet, T, MONTHS, store=0.0)[0]
    assert lgp[5] > no_store[5]


def test_water_indicators_definitions():
    n = len(MONTHS)
    P = np.full((1, n), 2.0)  # 2 mm/day every month
    pet = np.full((1, n), 4.0)
    T = np.full((1, n), 25.0)
    ind = land.water_indicators(P, pet, T, MONTHS, ws=np.full((1, n), 3.0))
    assert ind["aridity"][0, 0] == pytest.approx(0.5)  # P / PET
    days = np.array([31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31], float)
    pm = 2.0 * days
    assert ind["erosivity"][0, 0] == pytest.approx(float((pm ** 2).sum() / pm.sum()))  # modified Fournier
    # FAO wind factor: 1/100 * sum u^3 (PET - P) / PET * days = 27 * 0.5 * 365 / 100
    assert ind["wind_erosion"][0, 0] == pytest.approx(27 * 0.5 * 365 / 100)


def test_benjamini_hochberg():
    flags, thr = land.benjamini_hochberg([0.001, 0.008, 0.039, 0.041, 0.6], q=0.05)
    assert flags == [True, True, False, False, False] and thr == 0.008
    assert land.benjamini_hochberg([0.5, 0.9])[0] == [False, False]


def test_trend_detects_a_real_trend_and_not_a_flat_series():
    rng = random.Random(1)
    years = list(range(1981, 2026))
    up = [0.05 * (y - 1981) + rng.gauss(0, 0.3) for y in years]
    t = land.trend(years, up)
    assert t["level"] == "significant" and t["per_decade"] == pytest.approx(0.5, abs=0.15)
    assert t["ci"][0] < t["per_decade"] < t["ci"][1]
    flat = land.trend(years, [3.0] * len(years))
    assert flat["p"] == 1.0 and flat["level"] == "not significant"


def test_project_carries_a_line_and_admits_its_uncertainty():
    rng = random.Random(2)
    years = list(range(1981, 2026))
    v = [10 + 0.1 * (y - 1981) + rng.gauss(0, 0.2) for y in years]
    pr = land.project(years, v, (2026, 2035))
    assert pr["pred"] == pytest.approx(10 + 0.1 * (2030.5 - 1981), abs=0.5)
    assert pr["sd"] > 0 and pr["p_up"] > 0.9
    const = land.project(years, [5.0] * len(years), (2026, 2035))
    assert const["sd"] == 0 and const["pred"] == 5.0


def test_blend_learns_persistence_when_the_future_repeats_the_recent_past():
    rows = [{"pred": 10 + i % 3, "persistence": 5.0, "norm": 3.0 - i % 2, "obs": 5.0 + 0.01 * (-1) ** i, "sd0": 1.0}
            for i in range(30)]
    w = land.fit_blend(rows)
    assert w["persistence"] == pytest.approx(1.0) and w["eva"] == 0.0 and w["q90"] < 0.5


def _lp(area, sev, B, ivs):
    """The same programme, solved by a general LP solver: max sum b x, sum c x <= B, sum_j x_kj <= A_k."""
    keys = [k for k in area if sev.get(k)]
    c, A_ub, b_ub = [], [], []
    for k in keys:
        for iv in ivs:
            c.append(-budget.benefit_per_ha(iv["effects"], sev[k]))
    A_ub.append([iv["cost"] for _k in keys for iv in ivs])
    b_ub.append(B)
    for i, k in enumerate(keys):
        row = [0.0] * len(c)
        for j in range(len(ivs)):
            row[i * len(ivs) + j] = 1.0
        A_ub.append(row)
        b_ub.append(area[k])
    return -linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=(0, None), method="highs").fun


@pytest.mark.parametrize("B", [0.0, 3e4, 2e5, 1e6, 1e9])
def test_allocation_is_the_optimum_of_the_linear_programme(B):
    rng = random.Random(3)
    area = {f"c{i}": rng.uniform(50, 500) for i in range(12)}
    sev = {k: {t: rng.uniform(0, 0.3) for t in ("water", "erosion", "wind", "heat") if rng.random() < 0.7}
           for k in area}
    got = budget.allocate(area, sev, B)
    assert got["spent"] <= B + 1e-6
    assert got["protected_ha"] == pytest.approx(_lp(area, sev, B, budget.INTERVENTIONS), rel=1e-6, abs=1e-6)
    for k, x in got["plan"].items():
        assert sum(x.values()) <= area[k] + 1e-6


def test_severity_and_evidence_filters():
    assert budget.severity("water", 200.0, 20.0) == pytest.approx(0.1)
    assert budget.severity("heat", 30.0, 1.0) == pytest.approx(budget.SENSITIVITY["heat"])
    assert budget.severity("erosion", 100.0, -5.0) == 0.0


def _synthetic(n_side: int = 4, seed: int = 0) -> dict:
    """A small made-up region: rain falling in the north-east, warming everywhere."""
    rng = random.Random(seed)
    data = {p: {} for p in land.PARAMS}
    for i in range(n_side):
        for j in range(n_side):
            la, lo = 10.0 + 0.5 * i, 10.0 + 0.625 * j
            k = land.cell_key(la, lo)
            dry = 0.004 * (i + j)  # mm/day lost per year
            for p in land.PARAMS:
                s = {}
                for (y, m) in MONTHS:
                    wet = m in (5, 6, 7, 8, 9)
                    t = y - 1981
                    v = {"PRECTOTCORR": max(0.0, (6.0 - dry * t if wet else 0.2) + rng.gauss(0, 0.6)),
                         "GWETROOT": min(1.0, max(0.0, (0.6 if wet else 0.3) - 0.001 * (i + j) * t + rng.gauss(0, 0.03))),
                         "GWETTOP": min(1.0, max(0.0, (0.5 if wet else 0.2) + rng.gauss(0, 0.04))),
                         "TS": 28 + 0.03 * t + rng.gauss(0, 0.4), "T2M": 27 + 0.03 * t + rng.gauss(0, 0.4),
                         "T2M_MAX_AVG": 33 + 0.03 * t + rng.gauss(0, 0.4), "T2M_MIN_AVG": 21 + 0.03 * t + rng.gauss(0, 0.4),
                         "WS2M": 2.5 + rng.gauss(0, 0.2), "ALLSKY_SRF_ALB": 0.2 + rng.gauss(0, 0.01),
                         "EVLAND": 2.0 + rng.gauss(0, 0.2)}[p]
                    if p == "ALLSKY_SRF_ALB" and y < 2001:
                        v = None
                    s[(y, m)] = v
                data[p][k] = s
    return data


def test_a_synthetic_region_end_to_end():
    data = _synthetic()
    keys = list(data[land.MASK])
    mod = {k: {"cover": {2024: {"cropland": 0.3, "forest": 0.1, "savanna_grass": 0.5, "water": 0.0, "barren": 0.0}}}
           for k in keys}
    region = Region("synthetic", "Synthetic", 9.75, 11.75, 9.6875, 12.1875)
    res = land.analyse(region, data, mod, im={}, draws=0, control_draws=0, log=lambda *_: None)
    det = res["detect"]["lgp"]["summary"]
    assert det["tested"] == 16 and det["down"] >= 8 and det["up"] == 0  # the drying is found, nothing else
    assert res["detect"]["surface_temp"]["summary"]["up"] >= 12
    assert res["hindcast"]["lgp"]["cells"] == 16 and 0 <= res["hindcast"]["lgp"]["coverage90"]["blend"] <= 1
    assert all(0 <= f["p_down"] <= 1 for f in res["forecast"]["lgp"].values())
    assert res["story"] and res["cells"][keys[0]]["cropland_ha"] > 0
    b = budget.summary(res)
    assert b["plan"]["spent"] <= 20e6 + 1e-6 and b["hindcast"]["budgets"]
    html = land_page.render([land_page.slim(res)])
    assert "kepler.gl@3.1.10" in html and '"synthetic"' in html and "/*__DATA__*/null" not in html
    assert "—" not in land_page.TEMPLATE.read_text(encoding="utf-8")  # no em dash on the page (user rule)


def test_subgrid_is_the_same_for_a_region_and_its_part():
    # counted on the global grid: cutting a region to a country must not change which cells MODIS and IMERG check
    full = [(2.0 + 0.5 * i, 8.125 + 0.625 * j) for i in range(10) for j in range(10)]
    part = [p for p in full if p[0] >= 3.0 and p[1] >= 9.0]
    assert set(land.subgrid(part)) == set(land.subgrid(full)) & set(part)
    assert len(land.subgrid(full)) == 25


def test_point_in_polygon_with_a_hole():
    from detective.places import _inside
    square = [[[0, 0], [4, 0], [4, 4], [0, 4], [0, 0]], [[1, 1], [3, 1], [3, 3], [1, 3], [1, 1]]]
    assert _inside(0.5, 0.5, square) and not _inside(2, 2, square) and not _inside(5, 2, square)
    region = Region("box", "Box", 0, 1, 0, 1)
    assert land.in_country(region, {land.MASK: {"0.000,0.000": {}}}) == {land.MASK: {"0.000,0.000": {}}}
