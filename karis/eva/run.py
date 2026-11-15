"""Generic training loop (domain-agnostic)."""

from __future__ import annotations

import random
import time
from typing import Callable

from .agent import Eva
from .env import Agent, Env, run_episode


def train(
    eva: Eva,
    make_env: Callable[[], Env],
    episodes: int,
    others: list[Agent] | None = None,
    alone: float = 1.0,
    seed: int = 0,
    log_every: int = 0,
    log: Callable[[str], None] = print,
) -> None:
    """Run ``episodes`` learning episodes. With probability ``alone`` (or when there are
    no ``others``) Eva holds every perspective of the environment; otherwise she holds
    one perspective drawn at random and agents drawn from ``others`` hold the rest."""
    rng = random.Random(seed)
    env = make_env()
    eva.training = True
    t0 = time.time()
    for ep in range(1, episodes + 1):
        n = env.perspectives
        if n == 1 or not others or rng.random() < alone:
            agents: list[Agent] = [eva] * n
        else:
            agents = [rng.choice(others) for _ in range(n)]
            agents[rng.randrange(n)] = eva
        run_episode(env, agents, rng)
        if log_every and ep % log_every == 0:
            log(f"  episode {ep}/{episodes}  |err|={eva.last_error:.3f}  {eva.stats()}  {time.time() - t0:.1f}s")
