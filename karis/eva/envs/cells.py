"""Places read through time, then named — a domain.

Each sample is a place (a cell of a map) described by a few measured variables: some change from
one period to the next (their values in periods 0..P-1), the others do not. Eva reads a place:
at each « lire » the reading moves one period forward, every sensor showing its variable in that
period, the static sensors their constant value. After the last period she answers one of two
names and gets +1 or −1.

The sensors only report levels (quantiles chosen beforehand on places whose name is not used),
and nothing here says what a variable is: only its name, as a watcher. Which variables and which
of their changes go with which name is for Eva to find.
"""

from __future__ import annotations

import numpy as np

from ..env import Env

OUT = "·"  # a period the variable was not measured in
ANSWER = "réponse"


def levels(values: np.ndarray, n: int = 8) -> np.ndarray:
    """Equal-population edges of a variable. A variable that mostly sits at its lowest value (often
    0) gets one level for that value and the other levels by quantiles of the rest, so its rare
    changes are still told apart."""
    v = values[np.isfinite(values)]
    lo = v.min()
    if np.mean(v == lo) > 1 / n and (v > lo).sum() >= n:
        rest = v[v > lo]
        return np.unique(np.r_[np.nextafter(lo, np.inf), np.quantile(rest, np.linspace(0, 1, n)[1:-1])])
    return np.unique(np.quantile(v, np.linspace(0, 1, n + 1)[1:-1]))


class PlaceReadings(Env):
    """``series[name]``: array (places, periods), NaN = not measured; ``static[name]``: array
    (places,); ``edges[name]``: the levels of each variable; ``labels``: the name of each place
    (one of ``answers``), only used for the feedback."""

    perspectives = 1

    def __init__(self, series: dict, static: dict, edges: dict, labels, ids, answers: tuple,
                 order: str = "random"):
        self.answers, self.ids, self.order = tuple(answers), list(ids), order
        self.labels = labels
        self.periods = next(iter(series.values())).shape[1] if series else 1
        self.steps = self.periods - 1
        q = {}
        for k, a in series.items():
            lv = np.digitize(a, edges[k]).astype(object)
            lv[~np.isfinite(a)] = OUT
            q[k] = lv
        self.qs = q
        self.qc = {k: np.digitize(a, edges[k]) for k, a in static.items()}
        self.k = 0
        self.i = self.ids[0]
        self.t = 0
        self.answer = None

    def reset(self, rng=None) -> None:
        if self.order == "random" and rng is not None:  # every place once per pass, shuffled
            if self.k % len(self.ids) == 0:
                self.perm = list(self.ids)
                rng.shuffle(self.perm)
            self.i = self.perm[self.k % len(self.ids)]
        else:
            self.i = self.ids[self.k % len(self.ids)]
        self.k += 1
        self.t = 0
        self.answer = None

    def acting(self) -> int:
        return 0

    def actions(self) -> list:
        if self.answer is not None:
            return []
        return ["lire"] if self.t < self.steps else list(self.answers)

    def step(self, action) -> None:
        if action == "lire":
            assert self.t < self.steps
            self.t += 1
        else:
            assert self.t >= self.steps and action in self.answers
            self.answer = action

    def done(self) -> bool:
        return self.answer is not None

    def _obs(self, t: int, answer) -> dict:
        o = {k: (v if v == OUT else int(v)) for k, v in ((k, a[self.i, t]) for k, a in self.qs.items())}
        o.update({k: int(a[self.i]) for k, a in self.qc.items()})
        o[ANSWER] = answer or "?"
        return o

    def observe(self, p: int) -> dict:
        return self._obs(self.t, self.answer)

    def final_feedback(self, p: int) -> float:
        if self.answer is None:
            return 0.0
        return 1.0 if self.answer == self.labels[self.i] else -1.0

    def afterstate(self, action, p: int):
        if action == "lire":
            return self._obs(self.t + 1, None), None
        return self._obs(self.t, action), None  # the name is not known before answering

    def clone(self) -> "PlaceReadings":
        e = PlaceReadings.__new__(PlaceReadings)
        e.__dict__.update(self.__dict__)
        return e
