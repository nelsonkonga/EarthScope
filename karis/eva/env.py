"""The only contract between Eva and a domain (n4 — généraliser l'architecture).

Agnostic vocabulary: an environment shows *watchers* (``observe``: name -> hashable value,
as seen from a *perspective*), asks one perspective at a time for an *action*, and gives
*feedback* — after each step, and once more when the *episode* is done.

A domain may have several perspectives acting in turn (Eva can hold one or several of
them, other agents the rest) or a single one. Nothing in Eva's core knows what a domain
is about.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Hashable


class Env(ABC):
    perspectives: int = 1  # how many points of view act in this environment

    @abstractmethod
    def reset(self, rng=None) -> None: ...

    @abstractmethod
    def acting(self) -> int:
        """The perspective whose action is needed now."""

    @abstractmethod
    def actions(self) -> list: ...

    @abstractmethod
    def step(self, action) -> None: ...

    @abstractmethod
    def done(self) -> bool: ...

    @abstractmethod
    def observe(self, p: int) -> dict[str, Hashable]: ...

    @abstractmethod
    def clone(self) -> "Env": ...

    def feedback(self, p: int) -> float:
        """Feedback perspective ``p`` received from the last step (default: none)."""
        return 0.0

    def final_feedback(self, p: int) -> float:
        """Feedback for ``p`` when the episode is done (default: none)."""
        return 0.0

    def layout(self) -> dict | None:
        """Where the sensors are, if they have positions: watcher -> coordinates (a tuple
        of numbers). Not a rule of the domain, only the geometry of what is observed, like
        the arrangement of a retina. Default: none (watchers are only names)."""
        return None

    def afterstate(self, action, p: int) -> tuple[dict, float | None]:
        """What ``p`` would observe right after ``action``, before the environment
        responds; and the final feedback if this action ends the episode, else None."""
        e = self.clone()
        e.step(action)
        return e.observe(p), (e.final_feedback(p) if e.done() else None)


class Agent:
    """Anything that can hold a perspective. Eva and the reference agents implement it."""

    learns = False

    def begin(self, p: int, env: Env) -> None:
        pass

    def act(self, env: Env, p: int):
        raise NotImplementedError

    def tick(self, p: int, env: Env) -> None:
        pass

    def end(self, p: int, env: Env) -> None:
        pass

    def learn(self) -> None:
        pass


class RandomAgent(Agent):
    def __init__(self, seed: int = 0):
        import random

        self.rng = random.Random(seed)

    def act(self, env: Env, p: int):
        return self.rng.choice(env.actions())


def run_episode(env: Env, agents: list[Agent], rng=None, learn: bool = True) -> list[float]:
    """Run one episode; ``agents[i]`` holds perspective i (one agent may hold several).
    Returns the total feedback of each perspective."""
    env.reset(rng)
    totals = [0.0] * env.perspectives
    unique = []
    for p, a in enumerate(agents):
        a.begin(p, env)
        if a not in unique:
            unique.append(a)
    while not env.done():
        p = env.acting()
        action = agents[p].act(env, p)
        env.step(action)
        for q, a in enumerate(agents):
            totals[q] += env.feedback(q)
            a.tick(q, env)
    for q, a in enumerate(agents):
        totals[q] += env.final_feedback(q)
        a.end(q, env)
    if learn:
        for a in unique:
            if a.learns:
                a.learn()
    return totals
