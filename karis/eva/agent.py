"""Eva: the observer (statistical molettes) + the decision bank + an algorithm.

Eva may hold one or several perspectives of an environment at once; each perspective has
its own cursors and its own trajectory, the molettes are shared.
"""

from __future__ import annotations

import pickle
import random
from pathlib import Path

from .algorithms import ALGORITHMS, ensure_features
from .config import EvaConfig
from .decision import DecisionBank, Record
from .dynamics import Dynamics
from .env import Agent, Env
from .observer import Observer


class Eva(Agent):
    learns = True

    def __init__(self, cfg: EvaConfig | None = None):
        self.cfg = cfg or EvaConfig()
        self.rng = random.Random(self.cfg.seed)
        self.obs = Observer(self.cfg)
        self.dec = DecisionBank(self.cfg, self.obs)
        self.traj: dict[int, list[Record]] = {}
        self.seq: list[tuple[int, Record]] = []  # every decision of the episode, in order
        self.training = True
        self.ttraj: dict[int, list] = {}  # perspective -> transitions the world brought
        self.last_obs: dict[int, dict] = {}
        self.episodes = 0
        self.last_error = 0.0
        self.dyn = Dynamics(self.cfg) if self.cfg.model == "dynamics" else None

    # ------------------------------------------------------------- Agent API
    def begin(self, p: int, env: Env) -> None:
        if self.dyn is not None:
            self.dyn.begin(p, env.observe(p), layout=env.layout())
            return
        now = env.observe(p)
        self.obs.begin(p, now)
        if not self.traj:
            self.seq = []
            self.ttraj = {}
        self.traj[p] = []
        self.ttraj[p] = []
        self.last_obs[p] = now

    def act(self, env: Env, p: int):
        if self.dyn is not None:
            return self._act_dynamics(env, p)
        before = env.observe(p)
        algo = self.cfg.train_algo if self.training else self.cfg.algo
        cands = ALGORITHMS[algo](self, env, p, before)
        explored = self.training and self.rng.random() < self._epsilon()
        if explored:
            c = self.rng.choice(cands)
        elif any(x.key is not None for x in cands):
            best = max(x.key for x in cands if x.key is not None)
            c = self.rng.choice([x for x in cands if x.key == best])
        else:
            best = max(c.score for c in cands)
            c = self.rng.choice([c for c in cands if c.score >= best - 1e-9])
        ensure_features(self, c, p, before)
        if getattr(self.cfg, "time_net", False) and self.cfg.construction:
            c.feats, c.changed = self.dec.features(p, before, c.after)  # the move taken: space too
        rec = Record(c.feats, c.after, c.changed, value=c.value)
        if self.cfg.construction and self.cfg.elem_metas and self.training:
            rec.extra["before"] = before
        if self.training:
            rec.extra["explored"] = explored
            rec.extra["alts"] = [(x.feats, x.final if self.cfg.use_final else None) for x in cands if x.feats is not None]
            self.seq.append((p, rec))
        self.traj.setdefault(p, []).append(rec)
        return c.action

    def _act_dynamics(self, env: Env, p: int):
        acts = env.actions()
        tr = self.dyn.track.get(p)
        if tr is None:
            self.dyn.begin(p, env.observe(p), layout=env.layout())
            tr = self.dyn.track[p]
        choice = len(acts) > 1
        cands = rscores = None
        if choice and self.dyn.reads(p):  # the choice follows a reading: the reading decides
            cands = [env.afterstate(a, p) for a in acts]
            rscores = self.dyn.reading_scores(p, cands)
        explore = self.training and self.rng.random() < self._epsilon()
        mode = self.cfg.dyn_explore
        anchored = False
        if explore and choice:
            if mode == "anchored":
                anchored = not self.dyn.norm_favourable()
            elif mode == "space":  # anchored as often as the norm is unfavourable, else at random
                anchored = self.rng.random() < self.dyn.unfavourable()
        if explore and not anchored:
            a = self.rng.choice(acts)
        else:
            cl = None
            if not choice:  # nothing to choose: the perspective reads
                scores = [0.0]
            else:
                cl = cands or [env.afterstate(a, p) for a in acts]
                scores = self.dyn.judge(p, cl)
            if rscores is None:
                best = max(scores)
                a = self.rng.choice([x for x, s in zip(acts, scores) if s >= best - 1e-9])
            else:  # the reading first; the readings the action makes now only break ties
                best_r = max(rscores)
                tied = [i for i, r in enumerate(rscores) if r >= best_r - 1e-9]
                best = max(scores[i] for i in tied)
                a = self.rng.choice([acts[i] for i in tied if scores[i] >= best - 1e-9])
            if anchored:  # the norm is not favourable: beyond the norm of a good dynamic, prudently
                i = (self.dyn.explore_space if mode == "space" else self.dyn.explore)(p, cl, scores)
                if i is not None:
                    a = acts[i]
        if choice:
            self.dyn.chose(p, acts.index(a) if rscores is not None else None)
        else:
            tr.reading_step = True  # a step of its own without a choice: it reads
        tr.acted = True
        tr.tried = env.afterstate(a, p)[0] if self.dyn.layout is not None else None  # what it should make
        return a

    def tick(self, p: int, env: Env) -> None:
        if self.dyn is not None:
            self.dyn.tick(p, env.observe(p), env.feedback(p), learn=self.training)
            return
        now = env.observe(p)
        self.obs.tick(p, now)
        t = self.traj.get(p)
        if self.cfg.construction and self.cfg.transition_notes and self.training:
            ref = self.last_obs.get(p, now)
            if not (t and t[-1].after == now):  # not Eva's own move: the world moved
                feats = self.dec.transition_features(ref, now)
                moved = tuple(k for k, v in now.items() if ref.get(k) != v)
                if feats or moved:
                    rec = Record(feats, dict(now), moved)
                    rec.extra["before"] = ref
                    self.ttraj.setdefault(p, []).append(rec)
        self.last_obs[p] = now
        if t and self.training and self.cfg.learn_observed and t[-1].after != now:
            # a configuration Eva did not choose (the world moved): its decision molettes
            # tilt toward the result too; it is learned, never used to choose
            prev = t[-1].after
            feats, _ = self.dec.features(p, now, now)
            rec = Record(feats, dict(now), tuple(k for k, v in now.items() if prev.get(k) != v))
            rec.extra["observed"] = True
            t.append(rec)
        if t:
            t[-1].reward += env.feedback(p)

    def end(self, p: int, env: Env) -> None:
        if self.dyn is not None:
            self.dyn.end(p, env.final_feedback(p), learn=self.training)
            return
        t = self.traj.get(p)
        if t:
            t[-1].reward += env.final_feedback(p)
        self.obs.end(p)

    def learn(self) -> None:
        if self.dyn is not None:
            if self.training:
                self.dyn.learn()
                self.episodes += 1
            self.dyn.track = {}
            return
        if not self.training:
            self.traj = {}
            return
        cfg = self.cfg
        if cfg.alpha_decay > 0:
            self.dec.alpha = max(cfg.alpha_min, cfg.alpha / (1 + self.episodes / cfg.alpha_decay))
        else:
            self.dec.alpha = cfg.alpha
        if cfg.backup == "max":
            errs = [self.dec.learn_max(self.seq)]
        elif cfg.backup == "independent":
            errs = [self.dec.learn_independent(t) for t in self.traj.values() if t]
        elif cfg.backup == "converge":
            errs = [self.dec.learn_converge(t) for t in self.traj.values() if t]
        elif cfg.backup == "belief_each":
            errs = [self.dec.learn_belief_each(t) for t in self.traj.values() if t]
        elif cfg.backup == "belief":
            errs = [self.dec.learn_belief(t) for t in self.traj.values() if t]
        else:
            errs = [self.dec.learn(t) for t in self.traj.values() if t]
        if cfg.construction and cfg.transition_notes:
            for q, recs in self.ttraj.items():
                R = sum(r.reward for r in self.traj.get(q, []))
                self.dec.learn_transitions(recs, R)
            self.ttraj = {}
        self.seq = []
        self.last_error = sum(errs) / len(errs) if errs else 0.0
        self.episodes += 1
        self.dec.episode = self.episodes
        if cfg.meta_decisions:
            self.dec.grow()
        if cfg.construction and cfg.elem_from_feedback:
            self.dec.grow_elements()
        if cfg.construction and (cfg.elem_metas or cfg.net_size) and self.episodes % cfg.elem_check_every == 0:
            recent = [k for k, b in self.dec.elem_born.items() if self.episodes - b < cfg.net_probation]
            self.obs.track(self.dec.unit_utility(), recent)
        if cfg.construction and cfg.live_metas:
            for m in self.obs.emetas:  # born during the episode (at the instant they co-moved)
                self.dec.elem_born.setdefault(m, self.episodes)
        if cfg.construction and cfg.elem_metas:
            if cfg.meta_birth == "feedback":
                self.dec.grow_unit_metas()
        if cfg.md_prune_every and self.episodes % cfg.md_prune_every == 0:
            self.dec.prune()
            if cfg.construction and cfg.elem_from_feedback:
                self.dec.prune_elements()
            if cfg.construction and ((cfg.elem_metas and cfg.meta_birth == "feedback") or cfg.live_metas):
                self.dec.prune_unit_metas()
        self.traj = {}

    def _epsilon(self) -> float:
        cfg = self.cfg
        if cfg.epsilon_decay > 0:
            return max(cfg.epsilon_min, cfg.epsilon / (1 + self.episodes / cfg.epsilon_decay))
        return cfg.epsilon

    # ---------------------------------------------------------------- misc
    def stats(self) -> dict:
        """What Eva holds, to keep an eye on the resources."""
        if self.dyn is not None:
            return {"episodes": self.episodes, **self.dyn.stats()}
        chans = self.obs.channels.values()
        return {
            "episodes": self.episodes,
            "channels": sum(1 for c in chans if c.members is None),
            "meta_channels": len(self.obs.metas),
            "meta_channels_dissolved": self.obs.dissolved,
            "max_time_depth": max((c.depth() for c in chans), default=0),
            "statistical_entries": self.obs.size(),
            "decision_entries": self.dec.size(),
            "meta_decisions": len(self.dec.metas),
            "meta_decisions_from_feedback": self.dec.created_from_feedback,
            "meta_decisions_from_stats": self.dec.created_from_stats,
            "meta_decisions_pruned": self.dec.pruned,
            "construction_elements": len(self.obs.elements),
            "construction_elements_dissolved": self.obs.elements_dissolved,
            "discovered_meta_molettes": len(self.obs.emetas),
        }

    def save(self, path: str | Path) -> None:
        listeners, dissolvers = self.obs.listeners, self.obs.dissolve_listeners
        self.obs.listeners, self.obs.dissolve_listeners = [], []
        try:
            with open(path, "wb") as f:
                pickle.dump(self, f)
        finally:
            self.obs.listeners, self.obs.dissolve_listeners = listeners, dissolvers

    @staticmethod
    def load(path: str | Path) -> "Eva":
        with open(path, "rb") as f:
            eva = pickle.load(f)
        eva.__dict__.setdefault("dyn", None)
        eva.obs.listeners = [eva.dec._on_observer_meta]
        eva.obs.dissolve_listeners = [eva.dec._on_observer_dissolve]
        return eva
