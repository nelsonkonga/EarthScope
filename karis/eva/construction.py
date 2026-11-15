"""Construction elements: molettes that describe how the current state is built.

A curve is not described point by point: its derivatives tell how to build it. Likewise
the molettes here do not describe the base state (each watcher's value); they describe the
*elements of construction* of the current state.

- An *event* is a transition of a watcher, ``(watcher, old, new)``: the first derivative of
  the state, a construction step.
- A *construction element* is a set of events that are built together: within one episode
  they happen together more often than chance (correlation = time of occurrence, nothing
  else; no order, no position).
- Its molette has a *magnitude*, read from the current state: how many of its events hold
  (the watcher is at the event's new value), and how many can no longer happen
  (their watcher went to another value: the construction is blocked). It goes up and down by steps, so it
  has real transitions (k -> k+1), a time molette (how long it stays at k) and higher
  derivatives (how its rhythm changes), like every channel.
- An element followed by another event significantly often grows (``E + b``); an element
  whose association is no longer significant dissolves, with the elements built on it.

Nothing here knows what the events mean.
"""

from __future__ import annotations

import math
from collections import defaultdict
from functools import lru_cache

Event = tuple  # (watcher, old, new)


@lru_cache(maxsize=None)
def element_name(E: frozenset) -> tuple:
    """Channel name of a construction element (kept apart from the other channels)."""
    return ("~elem", tuple(sorted(E, key=repr)))


class Summary:
    """A molette over a class of elements with the same shape of dynamics (same number of
    steps, same values reached by them — opaque symbols): its value is how many of them stand
    open at ``done`` steps (none impossible). What is learned of one element of the class
    holds for all: e.g. a step that brings two of them to ``done`` at once."""

    __slots__ = ("cls", "done", "members")

    def __init__(self, cls, done: int, members=()):
        self.cls, self.done, self.members = cls, done, tuple(members)

    def __hash__(self):
        return hash(("~class", self.cls, self.done))

    def __eq__(self, other):
        return isinstance(other, Summary) and other.cls == self.cls and other.done == self.done

    def __repr__(self):
        return f"Summary({sorted(self.cls[1])}x{self.cls[0]}@{self.done})"

    def __getstate__(self):
        return (self.cls, self.done, self.members)

    def __setstate__(self, st):
        self.cls, self.done, self.members = st


class MTrans:
    """A meta-transition molette: the transition molettes of two elements that change
    together (at the same tick). Its position is the pair of their values while both are
    live; what it judges is their joint transitions (both moving at once), whose
    distribution tells what is standard and what is out of norm."""

    __slots__ = ("pair",)

    def __init__(self, pair: tuple):
        self.pair = pair

    def __hash__(self):
        return hash(("~mtrans", self.pair))

    def __eq__(self, other):
        return isinstance(other, MTrans) and other.pair == self.pair

    def __repr__(self):
        return f"MTrans({len(self.pair)})"

    def __getstate__(self):
        return self.pair

    def __setstate__(self, st):
        self.pair = st


def element_class(E: frozenset) -> tuple:
    """The shape of an element's dynamics: how many steps, which values they reach."""
    return (len(E), frozenset(e[2] for e in E))


@lru_cache(maxsize=None)
def unit_name(key) -> tuple:
    """Channel name of a unit: an element, or a meta molette over two units whose
    transitions happen together (discovered, see ``PairTracker``)."""
    if isinstance(key, frozenset):
        return element_name(key)
    if isinstance(key, Summary):
        return ("~class", key.cls, key.done)
    if isinstance(key, MTrans):
        return ("~mtrans", tuple(unit_name(k)[1] for k in key.pair))
    return ("~meta", tuple(unit_name(k)[1] for k in key))


def unit_value(key, obs: dict):
    """An element's magnitude, or the joint value of a meta molette's members."""
    if isinstance(key, frozenset):
        return magnitude(key, obs)
    if isinstance(key, Summary):
        return min(3, sum(1 for E in key.members if magnitude(E, obs) == (key.done, 0)))
    if isinstance(key, MTrans):
        return tuple(unit_value(k, obs) for k in key.pair)
    return tuple(unit_value(k, obs) for k in key)


def unit_values(units, obs: dict) -> dict:
    """The value of every unit in one state, each element's magnitude computed once."""
    memo: dict = {}

    def val(k):
        v = memo.get(k)
        if v is None:
            if isinstance(k, frozenset):
                v = magnitude(k, obs)
            elif isinstance(k, Summary):
                v = min(3, sum(1 for E in k.members if val(E) == (k.done, 0)))
            elif isinstance(k, MTrans):
                v = tuple(val(x) for x in k.pair)
            else:
                v = tuple(val(x) for x in k)
            memo[k] = v
        return v

    return {k: val(k) for k in units}


def present(key, v) -> bool:
    """Part of what the current state is built of: an element with at least one step done,
    a meta molette whose members are all present."""
    if isinstance(key, frozenset):
        return v[0] > 0
    if isinstance(key, Summary):
        return v > 0
    if isinstance(key, MTrans):
        return all(present(k, x) for k, x in zip(key.pair, v))
    return all(present(k, x) for k, x in zip(key, v))


def members(key) -> set:
    """The elements a unit is made of."""
    if isinstance(key, str):  # a raw watcher
        return set()
    if isinstance(key, frozenset):
        return {key}
    if isinstance(key, Summary):
        return set()
    if isinstance(key, MTrans):
        return set().union(*(members(k) for k in key.pair))
    return set().union(*(members(k) for k in key))


class PairTracker:
    """Which units transition at the same tick more often than chance (lift, z): their
    dynamics are correlated, a meta molette over them follows their joint dynamics."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.ticks = 0.0
        self.n: dict = defaultdict(float)
        self.co: dict = defaultdict(float)

    def observe(self, moved: list) -> None:
        self.ticks += 1
        for a in moved:
            self.n[a] += 1
        for i, a in enumerate(moved):
            for b in moved[i + 1 :]:
                self.co[_pair(a, b)] += 1

    def stats(self, pair) -> tuple[float, float, float]:
        a, b = pair
        e = self.n.get(a, 0.0) * self.n.get(b, 0.0) / max(1.0, self.ticks)
        c = self.co.get(pair, 0.0)
        if e <= 0:
            return c, 0.0, 0.0
        return c, c / e, (c - e) / math.sqrt(e)

    def candidates(self, existing: set) -> list:
        cfg, out = self.cfg, []
        for pair, c in self.co.items():
            if c < cfg.meta_min_count or pair in existing:
                continue
            a, b = pair
            ma, mb = members(a), members(b)
            if ma <= mb or mb <= ma:
                continue  # one is part of the other: they move together trivially
            _, lift, z = self.stats(pair)
            if lift >= cfg.meta_min_lift and z >= cfg.meta_z:
                out.append((z, pair))
        out.sort(key=lambda r: -r[0])
        return out

    def forget(self, dead) -> None:
        for d in (self.n, self.co):
            for k in list(d):
                if k in dead or (isinstance(k, tuple) and any(x in dead for x in k)):
                    del d[k]

    def decay(self, factor: float) -> None:
        if factor >= 1.0:
            return
        self.ticks *= factor
        for d in (self.n, self.co):
            for k in list(d):
                d[k] *= factor
                if d[k] < 0.5:
                    del d[k]


def _pair(a, b) -> tuple:
    return (a, b) if repr(a) <= repr(b) else (b, a)


def magnitude(E, obs: dict) -> tuple[int, int]:
    """Where the construction of E stands in the current state: ``(done, impossible)``.

    Read from the state itself (the integral of the construction), not from what was seen
    happening: dropped into any state, Eva reads the same elements.
    ``done``: events of E whose result holds (the watcher is at the event's new value);
    ``impossible``: events of E whose watcher has left the old value for another one than
    the event's (that step can no longer be built: the element is blocked)."""
    done = impossible = 0
    for w, old, new in E:
        v = obs.get(w)
        if v == new:
            done += 1
        elif v != old:
            impossible += 1
    return done, impossible


def _watchers(E) -> set:
    return {e[0] for e in E}


class ConstructionTracker:
    """Counts, over episodes, which events are built together."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.episodes = 0.0
        self.n: dict = defaultdict(float)  # frozenset (element or single event) -> episodes where all happened
        self.co: dict = defaultdict(float)  # (frozenset E, event b) -> episodes where E and b happened

    def observe(self, occurred: set, elements) -> None:
        """One finished episode (one perspective): the events that happened in it."""
        self.episodes += 1
        R = list(occurred)
        for e in R:
            self.n[frozenset((e,))] += 1
        for i, a in enumerate(R):
            for b in R:
                if a is not b and a[0] != b[0]:
                    self.co[(frozenset((a,)), b)] += 1
        for E in elements:
            if E <= occurred:
                self.n[E] += 1
                ws = _watchers(E)
                for b in R:
                    if b[0] not in ws:
                        self.co[(E, b)] += 1

    def stats(self, E: frozenset, b) -> tuple[float, float, float]:
        """(count, lift, z) of "b is built together with E" against independence."""
        nE, nb = self.n.get(E, 0.0), self.n.get(frozenset((b,)), 0.0)
        expected = nE * nb / max(1.0, self.episodes)
        c = self.co.get((E, b), 0.0)
        if expected <= 0:
            return c, 0.0, 0.0
        return c, c / expected, (c - expected) / math.sqrt(expected)

    def candidates(self, existing: set) -> list:
        """Significant associations not yet elements, best first: (z, element, parent)."""
        cfg = self.cfg
        out, seen = [], set()
        for (E, b), c in self.co.items():
            if c < cfg.meta_min_count:
                continue
            U = E | {b}
            if len(U) > cfg.elem_max_size or U in existing or U in seen:
                continue
            _, lift, z = self.stats(E, b)
            if lift >= cfg.meta_min_lift and z >= cfg.meta_z:
                seen.add(U)
                out.append((z, U, (E, b)))
        out.sort(key=lambda r: -r[0])
        return out

    def decay(self, factor: float) -> None:
        if factor >= 1.0:
            return
        self.episodes *= factor
        for d in (self.n, self.co):
            for k in list(d):
                d[k] *= factor
                if d[k] < 0.5:
                    del d[k]

    def size(self) -> int:
        return len(self.n) + len(self.co)


def live_value(v, two_sided: bool = False) -> bool:
    """An element's magnitude that is part of the state and still constructible (seen from
    both sides: one side has built in it and the other has not)."""
    if two_sided:
        return (v[0] > 0) != (v[1] > 0)
    return v[0] > 0 and v[1] == 0


def footprint(E: frozenset) -> frozenset:
    """The watchers of an element with their starting values: the construction, whichever
    side builds it."""
    return frozenset((w, old) for w, old, _n in E)
