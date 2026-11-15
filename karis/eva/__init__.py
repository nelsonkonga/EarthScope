"""Eva — a decision model built from molettes (statistical dials) and their decision dials.

The core is domain-agnostic: it only knows watchers, ticks, perspectives, actions and
feedback. Domains (eva/envs/) implement ``Env``."""

from .agent import Eva
from .config import EvaConfig
from .env import Agent, Env, RandomAgent, run_episode

__all__ = ["Eva", "EvaConfig", "Env", "Agent", "RandomAgent", "run_episode"]
