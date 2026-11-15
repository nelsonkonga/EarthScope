"""Bare ground opened since 2001 (detective/scars.py), on synthetic MODIS windows: no network."""

from __future__ import annotations

import math

import numpy as np

from detective import scars

V, B, W = 9, scars.BARE, 17  # savanna, bare ground, water


def test_opened_needs_vegetation_first_and_bare_to_the_end():
    px = {  # four readings of one pixel -> (opened?, index of the first reading from which it stays bare)
        "early": [V, B, B, B], "late": [V, V, V, B], "flicker": [V, B, V, B],
        "came back": [V, B, B, V], "always bare": [B, B, B, B], "water": [W, B, B, B]}
    stack = np.array([[v] for v in px.values()], dtype=np.int16).T.reshape(4, len(px), 1)
    mask, first = scars.opened(stack)
    got = {k: (bool(mask[i, 0]), int(first[i, 0]) if mask[i, 0] else None) for i, k in enumerate(px)}
    assert got == {"early": (True, 1), "late": (True, 3), "flicker": (True, 3), "came back": (False, None),
                   "always bare": (False, None), "water": (False, None)}


def _window(lat0: float, lon0: float, grids: list[np.ndarray]) -> list[dict]:
    """MODIS-like responses whose lower-left corner sits at (lat0, lon0) in the sinusoidal projection."""
    cs = 463.312716528
    y = math.radians(lat0) * scars.R_SIN
    x = math.radians(lon0) * scars.R_SIN * math.cos(math.radians(lat0))
    n = grids[0].shape[0]
    return [{"nrows": n, "ncols": n, "xllcorner": str(x), "yllcorner": str(y), "cellsize": cs,
             "subset": [{"data": g.ravel().tolist()}]} for g in grids]


def test_patches_are_placed_north_first_and_counted_once():
    n = 9
    g = [np.full((n, n), V, dtype=np.int16) for _ in scars.YEARS]
    for k in range(1, len(g)):  # a 2 x 2 patch in the top-left corner (north-west), bare from 2008
        g[k][0:2, 0:2] = B
    g[3][8, 8] = B  # one pixel only: dropped
    resp = _window(5.0, 14.0, g)
    centre = (5.02, 14.02)
    resps = {(centre, y): r for y, r in zip(scars.YEARS, resp)}
    cells = {"5.000,14.000": {"lat": 5.0, "lon": 14.0}}
    grid = {"dlat": 0.5, "dlon": 0.625}
    ps = scars.read_patches(resps, [centre], cells, grid, log=lambda *_: None)
    assert len(ps) == 1
    p = ps[0]
    assert p["pixels"] == 4 and p["opened"] == [2001, 2008] and p["before"] == "savanna"
    # the top rows are the north: the patch is about (n - 1) pixels of 463 m north of the lower-left corner
    assert p["lat"] > 5.0 + 0.8 * (n - 2) * 463 / 111_000
    assert p["lon"] < 14.0 + 3 * 463 / 111_000
    # the same window read twice (overlapping windows): the patch is counted once
    c2 = (5.03, 14.03)
    resps.update({(c2, y): r for y, r in zip(scars.YEARS, resp)})
    assert len(scars.read_patches(resps, [centre, c2], cells, grid, log=lambda *_: None)) == 1


def test_validation_counts_mines_near_patches():
    cells = {f"{la:.3f},{lo:.3f}": {"lat": la, "lon": lo} for la in (5.0, 5.5) for lo in (14.0, 14.625)}
    grid = {"dlat": 0.5, "dlon": 0.625}
    patches = [{"lat": 5.1, "lon": 14.1}, {"lat": 5.4, "lon": 14.5}]
    mines = [{"lat": 5.11, "lon": 14.11, "kind": "quarry"}, {"lat": 5.41, "lon": 14.49, "kind": "mine"},
             {"lat": 5.7, "lon": 14.8, "kind": "quarry"}]
    v = scars.validate(patches, mines, cells, grid)
    assert v["mapped_mines"] == 3 and v["mapped_with_patch"] == 2
    assert v["share_random_places"] < 0.2 and v["enrichment"] > 2
    assert scars.validate(patches, [], cells, grid)["mapped_mines"] == 0
