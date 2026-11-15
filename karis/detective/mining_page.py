"""The mining page: where mining changes the land of East Cameroon, how fast, where it goes next,
and what Eva learnt of the places next to mines. One standalone HTML file, French and English.

    python -m detective.mining_page        # data/earth/mining/index.html

It embeds ``land_change.json`` (detective/mining_land.py), ``eva_mines_s<seed>.json`` and the maps
(checks/mining_eva.py). Only the fonts come from the internet; the map is drawn in the page.
"""

from __future__ import annotations

import base64
import json
import math
import sys
from pathlib import Path

import numpy as np

from . import mining_land as ml
from .mining import SITES

TEMPLATE = Path(__file__).with_name("mining_page.html")


def _u8(a: np.ndarray, lo: float, hi: float) -> str:
    """A map as bytes 1..255 (0 = no data), base64."""
    v = np.where(np.isfinite(a), np.clip((a - lo) / (hi - lo), 0, 1) * 254 + 1, 0).astype(np.uint8)
    return base64.b64encode(v.tobytes()).decode()


def _rank(a: np.ndarray, ok: np.ndarray) -> np.ndarray:
    """Percentile rank (0..1) of each cell among the usable ones."""
    from scipy.stats import rankdata
    out = np.full(a.shape, np.nan)
    v = a[ok]
    out[ok] = (rankdata(v) - 0.5) / len(v)
    return out


def _r(x, sig=3):
    if isinstance(x, float):
        return None if not math.isfinite(x) else float(f"{x:.{sig}g}")
    if isinstance(x, dict):
        return {k: _r(v, sig) for k, v in x.items()}
    if isinstance(x, list):
        return [_r(v, sig) for v in x]
    return x


def data(seed: int = 0) -> dict:
    c = ml.load()
    lc = json.loads((ml.OUT / "land_change.json").read_text())
    ev = json.loads((ml.OUT / f"eva_mines_s{seed}.json").read_text())
    maps_lc = np.load(ml.OUT / "land_change_maps.npz")
    maps_ev = np.load(ml.OUT / f"eva_mines_s{seed}.npz")
    ok = ml.usable(c)
    loss = c["loss"].sum(0)
    yrs = np.array(ml.YEARS, float)[:, None, None]
    tot = c["loss"].sum(0)
    year = np.where(tot > 0.01, (c["loss"] * yrs).sum(0) / np.maximum(tot, 1e-9), np.nan)
    eva_rank = _rank(maps_ev["score_terre"], ok & np.isfinite(maps_ev["score_terre"]))
    risk = maps_lc["risk_loss_2026_2030"]
    layers = {
        "loss": {"b": _u8(np.where(c["land"] > 0.5, np.sqrt(np.clip(loss, 0, 1)), np.nan), 0, 1), "max": 1.0, "sqrt": True},
        "year": {"b": _u8(year, 2001, 2025), "lo": 2001, "hi": 2025},
        "risk": {"b": _u8(np.where(c["land"] > 0.5, risk, np.nan), 0, 1), "max": 1.0},
        "eva": {"b": _u8(eva_rank, 0, 1), "max": 1.0},
    }
    # per cell, for the hover: loss share, near water, risk, Eva rank, distance to a mapped mine
    cells = {
        "loss": np.round(loss, 4), "lw": np.round(c["loss_near_water"].sum(0), 4),
        "risk": np.round(np.nan_to_num(risk, nan=-1), 3), "eva": np.round(np.nan_to_num(eva_rank, nan=-1), 3),
        "dm": np.round(np.minimum(c["dist_mine"], 99), 1), "ok": ok.astype(int),
    }
    mines = np.argwhere(c["mine_mapped"] > 0)
    lat, lon = ml.centres()
    speed = lc["speed"]
    zones = {k: {"share_by_year": [v["loss_km2_by_year"][str(y)] / v["area_km2"] for y in ml.YEARS],
                 "near_water_share": [v["loss_near_water_km2_by_year"][str(y)] / max(v["loss_km2_by_year"][str(y)], 1e-9)
                                      for y in ml.YEARS],
                 **{kk: v[kk] for kk in ("cells", "area_km2", "cleared_2001_2025_km2", "cleared_share", "sen_km2_per_year",
                                         "sen_lo", "sen_hi", "mk_p", "growth_per_year", "growth_lo", "growth_hi",
                                         "doubling_years", "break_year", "break_p", "share_of_area_per_year_2021_2025")}}
             for k, v in speed["zones"].items()}
    evout = {}
    for tag, r in ev.items():
        evout[tag] = {"auc": r["auc"], "auc_logistic": r["auc_logistic"],
                      "folds": [{kk: f[kk] for kk in ("auc", "auc_logistic", "accuracy_at_0", "test_mine", "test_far", "train")}
                                for f in r["folds"]],
                      "by_variable": r["by_variable"][:14], "candidates": r.get("candidates", [])[:15],
                      "towns": r.get("towns")}
    return _r({
        "grid": {"rows": ml.NR, "cols": ml.NC, "north": ml.AREA.north, "west": ml.AREA.west, "step": ml.STEP},
        "years": ml.YEARS, "layers": layers,
        "cells": {k: v.ravel().tolist() for k, v in cells.items()},
        "mines": [[int(a), int(b)] for a, b in mines],
        "sites": [[n, la, lo] for n, (la, lo) in SITES.items()],
        "reservoir": ml.RESERVOIR,
        "where": lc["where"], "zones": zones,
        "distance_trend": speed["distance_trend_km_per_year"],
        "spread": {k: {"hindcast": v["hindcast_2021_2025"], "weights": v["weights"][:8]} for k, v in lc["spread"].items()},
        "eva": evout, "near_km": ml.NEAR_MINE_KM, "neg_km": 5.0,
    }, 4)


def build(seed: int = 0, out: Path | None = None) -> Path:
    out = out or ml.OUT / "index.html"
    d = data(seed)
    html = TEMPLATE.read_text().replace("/*DATA*/null", json.dumps(d, ensure_ascii=False, separators=(",", ":")))
    out.write_text(html)
    return out


if __name__ == "__main__":
    print(build(int(sys.argv[1]) if len(sys.argv) > 1 else 0))
