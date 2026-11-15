"""Mining and the land (detective/mining_land.py) and places read through time (eva/envs/cells.py).
Synthetic data: no raster, no network."""

from __future__ import annotations

import random

import numpy as np

from detective import mining_land as ml
from eva import Eva, EvaConfig
from eva.env import run_episode
from eva.envs.cells import OUT, PlaceReadings, levels


def test_the_grid_is_the_area_in_hundredths_of_a_degree():
    assert (ml.NR, ml.NC) == (220, 180)
    lat, lon = ml.centres()
    assert abs(lat[0] - 6.095) < 1e-9 and abs(lon[0] - 13.505) < 1e-9
    a = np.arange(ml.NR * 40 * ml.NC * 40, dtype=np.float32).reshape(ml.NR * 40, ml.NC * 40)
    b = ml._blocks(a, 40, "max")
    assert b.shape == (ml.NR, ml.NC) and b[0, 0] == a[39, 39]


def test_the_reservoir_is_left_out():
    c = {"land": np.ones((ml.NR, ml.NC))}
    u = ml.usable(c)
    lat, lon = ml.centres()
    i, j = np.searchsorted(-lat, -5.4), np.searchsorted(lon, 13.8)
    assert not u[i, j] and u[0, -1]


def test_logistic_finds_the_side():
    r = np.random.default_rng(0)
    x = r.normal(size=(2000, 2))
    y = (x[:, 0] + 0.1 * r.normal(size=2000) > 0).astype(float)
    sc = ml.Scaler(x)
    w = ml.logistic(sc(x), y)
    assert w[0] > 2 and abs(w[1]) < 0.5
    assert ml._auc(sc(x) @ w, y.astype(bool)) > 0.95


def test_levels_keep_rare_changes_apart():
    v = np.r_[np.zeros(900), np.linspace(0.01, 1, 100)]
    e = levels(v, 8)
    assert len(e) == 7 and e[0] < 0.01  # one level for 0, the rest by quantiles of what moved
    assert np.digitize([0.0], e)[0] == 0 and np.digitize([1.0], e)[0] == 7


def _places(n=200, seed=0):
    """Places whose first variable climbs over the periods when the name is « a », stays flat otherwise."""
    r = np.random.default_rng(seed)
    lab = np.array(["a" if i % 2 == 0 else "b" for i in range(n)], dtype=object)
    s = np.zeros((n, 4))
    for i in range(n):
        s[i] = np.cumsum(r.uniform(0.5, 1.0, 4)) if lab[i] == "a" else r.uniform(0, 1.5, 4)
    noise = r.normal(size=(n, 4))
    pop = r.uniform(size=(n, 4))
    pop[:, -1] = np.nan
    series = {"x": s, "bruit": noise, "p": pop}
    static = {"z": r.normal(size=n)}
    edges = {k: levels(v.ravel()) for k, v in series.items()}
    edges["z"] = levels(static["z"])
    return series, static, edges, lab


def test_a_place_is_read_period_by_period_then_named():
    series, static, edges, lab = _places()
    env = PlaceReadings(series, static, edges, lab, ids=[0, 1], answers=("a", "b"), order="in turn")
    env.reset()
    seen = []
    while env.actions() == ["lire"]:
        seen.append(env.observe(0)["x"])
        env.step("lire")
    seen.append(env.observe(0)["x"])
    assert len(seen) == 4 and env.observe(0)["p"] == OUT  # the last period of « p » was not measured
    assert env.actions() == ["a", "b"]
    obs, fb = env.afterstate("a", 0)
    assert fb is None and obs["réponse"] == "a"  # the name is never shown before answering
    env.step("a")
    assert env.done() and env.final_feedback(0) == 1.0


def test_eva_learns_which_variable_goes_with_the_name():
    series, static, edges, lab = _places(400)
    kw = dict(series=series, static=static, edges=edges, labels=lab, answers=("a", "b"))
    eva = Eva(EvaConfig(seed=0, dyn_elements=False))
    env = PlaceReadings(ids=list(range(300)), **kw)
    rng = random.Random(0)
    eva.training = True
    for _ in range(900):
        run_episode(env, [eva], rng)
    eva.training = False
    test = PlaceReadings(ids=list(range(300, 400)), order="in turn", **kw)
    right = 0
    for _ in range(100):
        run_episode(test, [eva], learn=False)
        right += test.answer == lab[test.i]
    assert right >= 75
