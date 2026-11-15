"""The store of the agent's imports (detective/datastore.py): every data set downloaded once.
Fake fetchers, no network, no local caches (seed=False)."""

from __future__ import annotations

import threading
import time

import pytest

from detective import datastore
from detective.datastore import DataStore, GuardError, cells_in_box, cell_key


def _series(la, lo):
    return {(y, m): la + lo / 100 + m / 1000 for y in range(1981, 2026) for m in range(1, 13)}


class Fake:
    """Counts what was fetched; answers like POWER (box: the cells inside, edges included)."""

    def __init__(self, delay=0.0):
        self.boxes, self.points, self.delay, self.lock = [], [], delay, threading.Lock()

    def box(self, param, s, n, w, e, offline=False):
        time.sleep(self.delay)
        with self.lock:
            self.boxes.append((param, s, n, w, e))
        return [(la, lo, _series(la, lo)) for la, lo in cells_in_box(param, s, n, w, e)]

    def point(self, param, lat, lon, offline=False):
        time.sleep(self.delay)
        with self.lock:
            self.points.append((param, lat, lon))
        return _series(lat, lon)

    def fetched(self):
        out = [cell_key(la, lo) for _p, la, lo in self.points]
        for p, s, n, w, e in self.boxes:
            out += [cell_key(*c) for c in cells_in_box(p, s, n, w, e)]
        return out


def _store(tmp_path, fake, **kw):
    return DataStore(tmp_path, power_box=fake.box, power_point=fake.point, seed=False, **kw)


def test_the_same_data_is_never_downloaded_twice(tmp_path):
    f = Fake()
    st = _store(tmp_path, f)
    cells = cells_in_box("T2M", 2, 5, 8, 11)  # 7 x 5 cells: one box request
    rows, rep = st.power("T2M", cells)
    assert len(rows) == len(cells) and rep["downloaded"] == len(cells) and rep["requests"] == 1
    assert len(f.boxes) == 1 and not f.points
    # the same content asked again, in another order and through a point inside it: nothing fetched
    rows2, rep2 = st.power("T2M", list(reversed(cells)) + [(3.1, 9.0)])
    assert rep2["from_store"] == len(cells) and rep2["downloaded"] == 0 and len(f.boxes) == 1
    assert rows2[cell_key(2.0, 8.125)] == rows[cell_key(2.0, 8.125)]
    # a new store on the same files (a server restart) still knows it
    st2 = _store(tmp_path, f)
    assert st2.power("T2M", cells)[1]["downloaded"] == 0 and len(f.boxes) == 1


def test_only_the_missing_cells_are_fetched(tmp_path):
    f = Fake()
    st = _store(tmp_path, f)
    first = cells_in_box("T2M", 2, 5, 8, 11)
    st.power("T2M", first)
    wider = cells_in_box("T2M", 2, 5, 8, 12.5)  # three more columns (11.25, 11.875, 12.5) of 7 rows
    _rows, rep = st.power("T2M", wider)
    new = sorted(set(map(lambda c: cell_key(*c), wider)) - set(map(lambda c: cell_key(*c), first)))
    assert rep["downloaded"] == len(new) == 21 and rep["from_store"] == len(first)
    fetched = f.fetched()
    assert len(fetched) == len(set(fetched)), "a cell was fetched twice"
    assert sorted(fetched) == sorted(set(map(lambda c: cell_key(*c), wider)))


def test_another_variable_is_another_data_set(tmp_path):
    f = Fake()
    st = _store(tmp_path, f)
    cells = cells_in_box("T2M", 2, 5, 8, 11)
    st.power("T2M", cells)
    assert st.power("PRECTOTCORR", cells)[1]["downloaded"] == len(cells)


def test_a_lost_download_is_refused_not_downloaded_again(tmp_path):
    f = Fake()
    st = _store(tmp_path, f)
    cells = [(3.0, 9.375)]
    st.power("T2M", cells)
    (tmp_path / "power" / "T2M.json").unlink()  # someone deleted the store file
    st = _store(tmp_path, f)
    rows, rep = st.power("T2M", cells)
    assert not rows and rep["refused"] and len(f.points) == 1
    rows, rep = st.power("T2M", cells, force=True)  # the operator's way
    assert rows and len(f.points) == 2


def test_two_questions_at_once_make_one_download(tmp_path):
    f = Fake(delay=0.2)
    st = _store(tmp_path, f)
    cells = [(4.0, 10.0), (4.5, 10.0)]
    out = []
    ts = [threading.Thread(target=lambda: out.append(st.power("T2M", cells)[1])) for _ in range(3)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert len(f.points) == 2 and sum(r["downloaded"] for r in out) == 2


def test_the_budget_per_hour_and_per_import(tmp_path, monkeypatch):
    f = Fake()
    now = [1000.0]
    st = _store(tmp_path, f, clock=lambda: now[0])
    monkeypatch.setitem(datastore.PER_HOUR, "power", 3)
    st.power("T2M", [(2.0, 8.125), (3.0, 10.0)])  # two scattered cells: two point requests
    with pytest.raises(GuardError):
        st.power("T2M", [(5.0, 12.5), (6.0, 13.75)])
    assert len(f.points) == 2
    now[0] += 3601
    st.power("T2M", [(5.0, 12.5), (6.0, 13.75)])
    assert len(f.points) == 4
    with pytest.raises(GuardError):  # too many scattered cells for one import
        st.power("T2M", [(-30.0 + 2 * i, 20.0 + 2 * i) for i in range(datastore.MAX_REQUESTS + 1)])


def test_imerg_and_modis_once_per_pixel_and_window(tmp_path):
    calls = {"imerg": 0, "modis": 0}

    def imerg(lat, lon, offline=False):
        calls["imerg"] += 1
        return {(2001, 1): 1.0}

    def modis(what, lat, lon, offline=False):
        calls["modis"] += 1
        return {2001: {"npp": 0.5}}

    st = DataStore(tmp_path, imerg_point=imerg, modis_fetch=modis, seed=False)
    st.imerg(4.12, 9.71)
    st.imerg(4.18, 9.79)  # the same 0.1° pixel
    assert calls["imerg"] == 1
    st.imerg(4.21, 9.71)
    assert calls["imerg"] == 2
    st.modis("npp", 4.0, 10.0)
    st.modis("npp", 4.01, 10.01)  # within 3 km of the same cell centre: the same window
    assert calls["modis"] == 1
    st.modis("cover", 4.0, 10.0)
    assert calls["modis"] == 2
    led = st.ledger()
    assert [e["source"] for e in led] == ["imerg", "imerg", "modis", "modis"]


def test_the_grid_and_the_meridian():
    assert cells_in_box("T2M", 2, 13, 8, 16.5)[0] == (2.0, 8.125)
    assert len(cells_in_box("T2M", 2, 13, 8, 16.5)) == 23 * 14
    assert cells_in_box("ALLSKY_SRF_ALB", 2, 13, 8, 16.5)[0] == (2.5, 8.5)
    assert cell_key(12.0, -0.0) == cell_key(12.0, 0.0) == "12.000,0.000"
    blocks = datastore.rectangles(cells_in_box("T2M", 2, 5, 8, 11) + [(6.0, 8.125)], "T2M")
    assert sorted(len(b) for b in blocks) == [1, 35]
