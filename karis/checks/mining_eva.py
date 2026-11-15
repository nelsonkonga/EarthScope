"""Eva learns what changes around a mine, then points at places that may hold mining zones.

The places are the 0.01° cells of the Lom-Kadéï gold belt (detective/mining_land.py, reservoir
box left out). Eva reads a place through five periods of five years (2001-2005 ... 2021-2025),
each sensor showing one variable in that period, then answers « mine » or « sans mine » and gets
+1 or −1 (eva/envs/cells.py). A place is « mine » when a mine or quarry mapped on OpenStreetMap
lies within 1 km, « sans mine » beyond 5 km; the places in between are not taught.

Nothing tells her which variable matters. Two sets of sensors:
- ``satellite``: what the satellites and censuses measure (forest loss here and around, loss near
  water, people, water history, relief, tree cover).
- ``terre``: the satellite sensors without the people: only what the land shows. Mapped mines sit
  in inhabited places, and with the people Eva's best candidates are towns (RESULTS.md § 39).
- ``all``: the satellite sensors + the distances to roads, villages, towns, rivers (OpenStreetMap). Mappers
  map mines they can reach: these distances tell where mappers went as much as where mines are.

Judged on places she has never seen, two-fold by 0.2° blocks of the map (neighbouring cells are
not independent): trained on the blocks of one fold, she reads every place of the other. So every
place gets a score from an Eva that never saw its block. Controls: the same with the names
shuffled (should be at chance), and a logistic regression on the same variables.

Then: which readings pushed her toward the right name (by variable, and the dynamics themselves),
and the places with a high score more than 5 km from any mapped mine: candidates.

Usage: mining_eva.py [per class] [passes] [seed] [out.json]
       MINING_VARIANTS=3,4 …: only these variants (0 satellite, 1 all, 2 satellite shuffled, 3 terre,
       4 terre shuffled), added to the earlier results of the same seed
"""

from __future__ import annotations

import json
import os
import random
import resource
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from detective import mining_land as ml  # noqa: E402
from eva import Eva, EvaConfig  # noqa: E402
from eva.env import run_episode  # noqa: E402
from eva.envs.cells import OUT, PlaceReadings, levels  # noqa: E402

MINE, NONE = "mine", "sans mine"
NEG_KM = 5.0
BLOCK = 20  # cells: 0.2°
PERIODS = [(2001, 2005), (2006, 2010), (2011, 2015), (2016, 2020), (2021, 2025)]


def variables(c: dict, which: str) -> tuple[dict, dict]:
    """(series name -> places x periods, static name -> places) over every cell, row-major."""
    from scipy import ndimage
    Y = ml.YEARS
    s, st = {}, {}

    def per(a, years):
        out = np.full((ml.NR * ml.NC, len(PERIODS)), np.nan)
        for j, (a0, a1) in enumerate(PERIODS):
            idx = [years.index(y) for y in range(a0, a1 + 1) if y in years]
            if idx:
                out[:, j] = a[idx].mean(0).ravel() if a is c["population"] else a[idx].sum(0).ravel()
        return out

    around = lambda a: np.stack([ndimage.uniform_filter(x, 5, mode="nearest") for x in a])  # noqa: E731
    s["perte de forêt"] = per(c["loss"], Y)
    s["perte de forêt autour"] = per(around(c["loss"]), Y)
    s["perte près de l'eau"] = per(c["loss_near_water"], Y)
    s["perte près de l'eau autour"] = per(around(c["loss_near_water"]), Y)
    if which != "terre":  # « terre »: only what the land itself shows, no people
        s["habitants"] = per(c["population"], ml.POP_YEARS)
        s["habitants"][:, -1] = np.nan  # WorldPop stops in 2020
    for k, name in (("treecover2000", "couvert d'arbres 2000"), ("water_occurrence", "eau présente (1984-2021)"),
                    ("near_water", "terre près de l'eau"), ("new_seasonal_water", "eau saisonnière nouvelle"),
                    ("new_permanent_water", "eau permanente nouvelle"),
                    ("ephemeral_seasonal_water", "eau saisonnière éphémère"), ("elevation", "altitude"),
                    ("slope", "pente")):
        st[name] = c[k].ravel().astype(float)
    if which == "all":
        for k, name in (("dist_stream", "distance au ruisseau"), ("dist_river", "distance à la rivière"),
                        ("dist_road", "distance à la piste"), ("dist_main_road", "distance à la route"),
                        ("dist_village", "distance au village"), ("dist_town", "distance à la ville")):
            st[name] = c[k].ravel().astype(float)
    return s, st


def folds(usable: np.ndarray, seed: int) -> np.ndarray:
    """0 or 1 for each cell: its 0.2° block's fold, drawn at random (half the blocks each)."""
    br, bc = np.arange(ml.NR) // BLOCK, np.arange(ml.NC) // BLOCK
    blk = br[:, None] * 100 + bc[None, :]
    ids = np.unique(blk)
    r = np.random.default_rng(seed)
    f = dict(zip(ids, r.permutation(np.arange(len(ids)) % 2)))
    return np.vectorize(f.get)(blk).ravel()


def auc(score, pos) -> float:
    from scipy.stats import rankdata
    score, pos = np.asarray(score, float), np.asarray(pos, bool)
    r = rankdata(score)
    n1, n0 = pos.sum(), (~pos).sum()
    return float((r[pos].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def read_all(eva, env_kw, ids, influence=None, truth=None, q=1.0):
    """Eva reads each place once (no learning): her score (« mine » minus « sans mine ») and, with
    ``influence``, what each reading pushed toward."""
    env = PlaceReadings(ids=ids, order="in turn", **env_kw)
    eva.training = False
    scores = np.zeros(len(ids))
    for j in range(len(ids)):
        env.reset()
        eva.begin(0, env)
        while not env.done():
            acts = env.actions()
            if len(acts) > 1:
                cands = [env.afterstate(a, 0) for a in acts]
                rs = eva.dyn.reading_scores(0, cands)
                scores[j] = rs[acts.index(MINE)] - rs[acts.index(NONE)]
                if influence is not None:
                    tr = eva.dyn.track[0]
                    tk = dict(zip(acts, tr.cand_t))
                    notes = eva.dyn.notes
                    for r in eva.dyn._reading_keys(tr):
                        vm = notes.get(("L", r, tk[MINE][0]), 0.0) if tk[MINE] else 0.0
                        vn = notes.get(("L", r, tk[NONE][0]), 0.0) if tk[NONE] else 0.0
                        w = abs(vm) ** q * np.sign(vm) - abs(vn) ** q * np.sign(vn)  # toward « mine » if > 0
                        if w:
                            st = influence[r]
                            st[0 if truth[j] else 1] += w
                            st[2] += 1
            a = eva.act(env, 0)
            env.step(a)
            eva.tick(0, env)
        eva.end(0, env)
        eva.dyn.track = {}
    return scores


def sensors_of(key) -> list[str]:
    X = key[0]
    if isinstance(X, tuple) and X and X[0] == "M":
        return sorted({m for m in X[2] if isinstance(m, str)})
    if isinstance(X, tuple):
        return [str(X)]
    return [str(X)]


def logistic_baseline(series, static, tr_ids, y_tr, te_ids):
    cols = [np.nan_to_num(a, nan=-1.0) for a in series.values()] + [a[:, None] for a in static.values()]
    X = np.concatenate([c if c.ndim == 2 else c[:, None] for c in cols], axis=1)
    sc = ml.Scaler(X[tr_ids])
    w = ml.logistic(sc(X[tr_ids]), np.asarray(y_tr, float))
    return sc(X[te_ids]) @ w


def run(which: str, n: int, passes: int, seed: int, shuffle: bool = False, log=print) -> dict:
    c = ml.load()
    usable = ml.usable(c).ravel()
    dm = c["dist_mine"].ravel()
    pos_all = usable & (dm <= ml.NEAR_MINE_KM)
    neg_all = usable & (dm > NEG_KM)
    series, static = variables(c, which)
    grain_rng = np.random.default_rng(999)
    grain_ids = grain_rng.choice(np.flatnonzero(usable), 4000, replace=False)  # no name used
    edges = {k: levels(a[grain_ids].ravel()) for k, a in series.items()}
    edges.update({k: levels(a[grain_ids]) for k, a in static.items()})
    labels = np.where(pos_all, MINE, NONE).astype(object)
    fold = folds(usable, seed)
    score = np.full(ml.NR * ml.NC, np.nan)
    influence = defaultdict(lambda: [0.0, 0.0, 0])  # reading -> [push toward mine on mine places, on others, count]
    out = {"which": which, "per_class": n, "passes": passes, "seed": seed, "shuffled": shuffle, "folds": []}
    base_scores = np.full(ml.NR * ml.NC, np.nan)
    for f in (0, 1):
        rng = np.random.default_rng(seed * 10 + f)
        tp = rng.permutation(np.flatnonzero(pos_all & (fold != f)))[:n]
        tn = rng.permutation(np.flatnonzero(neg_all & (fold != f)))[:len(tp)]
        train = list(tp) + list(tn)
        lab = labels.copy()
        if shuffle:  # control: the same places, the names drawn at random
            perm = rng.permutation(len(train))
            names = [labels[i] for i in train]
            for i, j in zip(train, perm):
                lab[i] = names[j]
        env_kw = {"series": series, "static": static, "edges": edges, "labels": lab, "answers": (MINE, NONE)}
        eva = Eva(EvaConfig(seed=seed, dyn_elements=False))
        env = PlaceReadings(ids=train, **env_kw)
        r = random.Random(seed + f)
        eva.training = True
        t0 = time.time()
        for ep in range(passes * len(train)):
            run_episode(env, [eva], r)
        train_s = time.time() - t0
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024
        # every place of the other fold, read once
        test = np.flatnonzero(usable & (fold == f))
        t0 = time.time()
        truth = pos_all[test]
        sc = read_all(eva, env_kw, list(test), influence=influence, truth=truth, q=eva.cfg.dyn_power)
        score[test] = sc
        judged = pos_all[test] | neg_all[test]
        a = auc(sc[judged], truth[judged])
        ytr = [1.0 if lab[i] == MINE else 0.0 for i in train]
        bs = logistic_baseline(series, static, train, ytr, list(test))
        base_scores[test] = bs
        ab = auc(bs[judged], truth[judged])
        acc = float(np.mean((sc[judged] > 0) == truth[judged]))
        out["folds"].append({"fold": f, "train": len(train), "test_places": int(len(test)),
                             "test_mine": int(truth.sum()), "test_far": int(neg_all[test].sum()),
                             "auc": a, "accuracy_at_0": acc, "auc_logistic": ab, "train_s": train_s,
                             "read_s": time.time() - t0, "rss_mb": rss, "stats": eva.stats()})
        log(f"  {which}{' (noms mélangés)' if shuffle else ''} pli {f}: {len(train)} lieux appris, "
            f"{int(judged.sum())} jugés ({int(truth.sum())} mines) : AUC Eva {a:.3f}, régression {ab:.3f}, "
            f"justes {100 * acc:.0f} % ({train_s:.0f} s + {time.time() - t0:.0f} s, {rss} Mo)", flush=True)
    judged = pos_all | neg_all
    ok = judged & np.isfinite(score)
    out["auc"] = auc(score[ok], pos_all[ok])
    out["auc_logistic"] = auc(base_scores[ok], pos_all[ok])
    # by variable: how much its readings pushed toward the right name, and toward « mine » on mine places
    by_var = defaultdict(lambda: [0.0, 0.0, 0])
    for key, (on_mine, on_other, cnt) in influence.items():
        for s_ in sensors_of(key):
            by_var[s_][0] += on_mine
            by_var[s_][1] += on_other
            by_var[s_][2] += cnt
    npos = int((pos_all & np.isfinite(score)).sum())
    noth = int((~pos_all & usable & np.isfinite(score)).sum())
    out["by_variable"] = sorted(({"variable": k, "push_mine_on_mine_places": v[0] / max(npos, 1),
                                  "push_mine_on_other_places": v[1] / max(noth, 1),
                                  "separation": v[0] / max(npos, 1) - v[1] / max(noth, 1), "readings": v[2]}
                                 for k, v in by_var.items()), key=lambda r: -r["separation"])
    top = sorted(influence.items(), key=lambda kv: -(kv[1][0] / max(npos, 1) - kv[1][1] / max(noth, 1)))
    out["top_readings_toward_mine"] = [{"lecture": repr(k), "capteurs": sensors_of(k),
                                        "sur_mines": v[0] / max(npos, 1), "ailleurs": v[1] / max(noth, 1)}
                                       for k, v in top[:30]]
    out["top_readings_toward_none"] = [{"lecture": repr(k), "capteurs": sensors_of(k),
                                        "sur_mines": v[0] / max(npos, 1), "ailleurs": v[1] / max(noth, 1)}
                                       for k, v in top[-20:]]
    out["edges"] = {k: [float(x) for x in v] for k, v in edges.items()}
    out["score"] = score
    out["score_logistic"] = base_scores
    return out


def candidates(score: np.ndarray, c: dict, top_share: float = 0.02) -> list[dict]:
    """Places in the top share of Eva's scores more than NEG_KM km from any mapped mine, merged
    into patches of touching cells."""
    from scipy import ndimage
    usable = ml.usable(c)
    s = score.reshape(ml.NR, ml.NC)
    ok = usable & np.isfinite(s)
    th = np.quantile(s[ok], 1 - top_share)
    cand = ok & (s >= th) & (c["dist_mine"] > NEG_KM)
    lab, n = ndimage.label(cand)
    lat, lon = ml.centres()
    out = []
    for k in range(1, n + 1):
        rr, cc = np.where(lab == k)
        out.append({"lat": float(lat[rr].mean()), "lon": float(lon[cc].mean()), "cells": int(len(rr)),
                    "score_max": float(s[rr, cc].max()), "dist_mine_km": float(c["dist_mine"][rr, cc].min()),
                    "dist_maus_km": float(c["dist_maus"][rr, cc].min()),
                    "loss_2001_2025": float(c["loss"][:, rr, cc].sum(0).mean()),
                    "loss_near_water_2001_2025": float(c["loss_near_water"][:, rr, cc].sum(0).mean()),
                    "dist_road_km": float(c["dist_road"][rr, cc].min()),
                    "dist_village_km": float(c["dist_village"][rr, cc].min()),
                    "dist_town_km": float(c["dist_town"][rr, cc].min()),
                    "people_2020": float(c["population"][-1][rr, cc].sum())})
    out.sort(key=lambda d: -d["score_max"] * d["cells"] ** 0.5)
    return out


def town_check(score: np.ndarray, c: dict, top_share: float = 0.02) -> dict:
    """Are the places Eva scores highest towns? The share within 3 km of a town or city, among her
    top places, among the mapped mine places, and among all places."""
    ok = ml.usable(c) & np.isfinite(score)
    top = ok & (score >= np.quantile(score[ok], 1 - top_share))
    town = c["dist_town"] <= 3.0
    mines = ok & (c["dist_mine"] <= ml.NEAR_MINE_KM)
    far_top = top & (c["dist_mine"] > NEG_KM)
    return {"top_within_3km_of_town": float(town[top].mean()), "far_top_within_3km_of_town": float(town[far_top].mean()),
            "mines_within_3km_of_town": float(town[mines].mean()), "all_within_3km_of_town": float(town[ok].mean()),
            "top_people_median": float(np.median(c["population"][-1][top])),
            "mines_people_median": float(np.median(c["population"][-1][mines])),
            "all_people_median": float(np.median(c["population"][-1][ok]))}


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 600
    passes = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    path = Path(sys.argv[4]) if len(sys.argv) > 4 else ml.OUT / f"eva_mines_s{seed}.json"
    c = ml.load()
    res, maps = {}, {}
    variants = [(("satellite", False), ("all", False), ("satellite", True), ("terre", False), ("terre", True))[int(k)]
                for k in os.environ.get("MINING_VARIANTS", "0,1,2,3,4").split(",")]
    if path.exists():  # add to an earlier run of the same seed
        res = json.loads(path.read_text())
        with np.load(path.with_suffix(".npz")) as z:
            maps = {k: z[k] for k in z.files}
    for which, shuffle in variants:
        tag = which + ("_shuffled" if shuffle else "")
        r = run(which, n, passes, seed, shuffle)
        maps[f"score_{tag}"] = r.pop("score").reshape(ml.NR, ml.NC)
        maps[f"logistic_{tag}"] = r.pop("score_logistic").reshape(ml.NR, ml.NC)
        res[tag] = r
        print(f"{tag}: AUC Eva {r['auc']:.3f}, régression {r['auc_logistic']:.3f}", flush=True)
        for v in r["by_variable"][:8]:
            print(f"    {v['variable']:30s} séparation {v['separation']:+.4f}", flush=True)
    for tag in res:  # candidates and the town check, for every variant (also those of an earlier run)
        if not tag.endswith("_shuffled"):
            res[tag]["candidates"] = candidates(maps[f"score_{tag}"].ravel(), c)
            res[tag]["towns"] = town_check(maps[f"score_{tag}"], c)
            t = res[tag]["towns"]
            print(f"{tag}: top 2 % of places, {100 * t['top_within_3km_of_town']:.0f} % within 3 km of a town "
                  f"(mapped mine places {100 * t['mines_within_3km_of_town']:.0f} %, all places {100 * t['all_within_3km_of_town']:.0f} %)")
    np.savez_compressed(path.with_suffix(".npz"), **maps)
    path.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float))
    print(f"-> {path}")


if __name__ == "__main__":
    main()
