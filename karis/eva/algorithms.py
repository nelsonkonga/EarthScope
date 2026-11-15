"""Algorithmes de décision (n14).

No search: Eva never simulates how the environment would respond to her action. All
foresight lives in the molettes:

- the **energy profile**: where the statistical molettes (standard x time, and the meta
  molettes) expect themselves to be in the next ticks, projected by ``Channel.project``;
- the **decision profile**: what the decision molettes want, i.e. their scores.

An action is chosen because its projected profile is the closest to what the model wants,
with the least movement of the molettes (n11).

Methods:
- ``greedy``  : horizon 0, the profile of the afterstate only;
- ``profile`` : horizon ``cfg.horizon`` ticks; closeness measured either as the expected
  score of the projected profile (``profile_metric='value'``) or as the KL divergence
  between each projected molette and the distribution it wants
  (``softmax(score / tau)``, ``profile_metric='kl'``).
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field

from .molettes import Channel, bucket


@dataclass
class Cand:
    action: object
    value: float
    cost: float
    feats: list
    after: dict
    changed: tuple
    final: float | None
    trace: dict = field(default_factory=dict)
    key: tuple | None = None  # lexicographic choice (levels algorithm)

    @property
    def score(self) -> float:
        return self.value - self.cost


def evaluate(eva, env, p: int, before: dict) -> list[Cand]:
    """Afterstate scoring: decision molettes + known final feedback + least action."""
    cfg, dec, obs = eva.cfg, eva.dec, eva.obs
    out = []
    for a in env.actions():
        after, final = env.afterstate(a, p)
        if getattr(cfg, "time_net", False) and cfg.construction:  # the time part decides
            feats = dec.time_features(before, after)
            changed = tuple(k for k, v in after.items() if before.get(k) != v)
            v = final if (final is not None and cfg.use_final) else dec.combine_time([(f, 1.0, 0) for f in feats])
        else:
            feats, changed = dec.features(p, before, after)
            v = final if (final is not None and cfg.use_final) else dec.value(feats)
        cost = 0.0
        if cfg.beta:
            cost = cfg.beta * cfg.action_scale * obs.action(p, after, cfg.action_mode)
        out.append(Cand(a, v, cost, feats, after, changed, final))
    return out


def greedy(eva, env, p, before):
    return evaluate(eva, env, p, before)


# --------------------------------------------------------------------- profiles
def _joint(marginals: list[dict], prune: float = 1e-3) -> dict:
    """Product of member marginals (for decision metas without a statistical channel)."""
    combos = {(): 1.0}
    for m in marginals:
        nxt = {}
        for k, p in combos.items():
            for v, q in m.items():
                pq = p * q
                if pq >= prune:
                    nxt[k + (v,)] = pq
        combos = nxt
    return combos


def _expected_value(eva, states: dict, marg: dict) -> float:
    """Score the decision molettes give to a projected (probabilistic) profile."""
    w, cfg, dec = eva.dec.w, eva.cfg, eva.dec
    total = 0.0
    for name, m in marg.items():
        if isinstance(name, tuple):
            continue
        for v, p in m.items():
            total += p * w.get(("p", name, v), 0.0)
        if cfg.time_features:
            for (v, d), p in states[name].items():
                total += p * w.get(("t", name, v, bucket(d) if d else 0), 0.0)
    for S in dec.metas:
        if S in marg:
            joint = marg[S]
            if cfg.time_features:
                for (v, d), p in states[S].items():
                    total += p * w.get(("mt", S, v, bucket(d) if d else 0), 0.0)
        else:
            joint = _joint([marg.get(m, {}) for m in S])
        for v, p in joint.items():
            total += p * w.get(("m", S, v), 0.0)
    return total


def _kl_to_wanted(eva, marg: dict) -> float:
    """Sum over molettes of KL(projected || wanted), wanted = softmax(score / tau)."""
    w, tau, obs = eva.dec.w, eva.cfg.tau, eva.obs
    total = 0.0
    for name, m in marg.items():
        if isinstance(name, tuple):
            continue
        ch = obs.channels.get(name)
        support = set(m) | (ch.trans.alphabet if ch else set())
        scores = {v: w.get(("p", name, v), 0.0) / tau for v in support}
        mx = max(scores.values())
        z = sum(math.exp(s - mx) for s in scores.values())
        for v, p in m.items():
            if p > 0:
                logq = scores[v] - mx - math.log(z)
                total += p * (math.log(p) - logq)
    return total


def profile(eva, env, p, before):
    """Project every molette ``cfg.horizon`` ticks after the action and keep the action
    whose projected profile is closest to what the decision molettes want."""
    cfg, obs = eva.cfg, eva.obs
    cands = evaluate(eva, env, p, before)
    if cfg.horizon <= 0:
        return cands
    if cfg.construction:
        obs.focus(before)
        return _profile_construction(eva, p, cands)
    names = [n for n in list(before.keys()) + list(obs.metas) if n in obs.channels and obs.in_net(n)]
    for c in cands:
        if c.final is not None and cfg.use_final:
            continue
        states = {}
        for n in names:
            v, d = obs.dwell_after(p, n, obs.value(n, c.after))
            states[n] = {(v, d): 1.0}
        const = sum(eva.dec.w.get(f, 0.0) for f in c.feats if f[0] == "c")
        acc, wsum, energy, dist = c.value, 1.0, 0.0, 0.0
        for t in range(1, cfg.horizon + 1):
            states = {n: obs.channels[n].project(s) for n, s in states.items()}
            marg = {n: Channel.marginal(s) for n, s in states.items()}
            energy += sum(Channel.entropy(m) for n, m in marg.items() if not isinstance(n, tuple))
            wt = cfg.horizon_decay**t
            if cfg.profile_metric == "kl":
                dist += wt * _kl_to_wanted(eva, marg)
            else:
                ev = _expected_value(eva, states, marg) + const
                acc += wt * (math.tanh(ev) if cfg.squash else ev)
                wsum += wt
        if cfg.profile_metric == "kl":
            c.value = c.value - cfg.tau * dist
        else:
            c.value = acc / wsum
        if cfg.beta:
            c.cost += cfg.beta * cfg.action_scale * energy
        c.trace = {"energy": energy, "kl": dist}
    return cands


def _profile_construction(eva, p, cands):
    """Decision profile over the construction elements: each element's molettes (its
    transitions and its time molette) project where it will stand in the next ticks; the
    note of an action is the mean, over now and the projected ticks, of what the decision
    molettes say of those magnitudes. Nothing is simulated."""
    from .construction import present, unit_name, unit_values

    cfg, obs = eva.cfg, eva.obs
    note = eva.dec.note
    tf = cfg.time_features
    units = obs.eval_set()
    time_net = getattr(cfg, "time_net", False)
    touched = set()  # what some move changes: projected for every move (it moves or it stays)
    if time_net:
        for c in cands:
            for f in c.feats or ():
                if f[0] == "c" and f[2] != f[3]:
                    touched.add(f[1])
    for c in cands:
        if c.final is not None and cfg.use_final:
            continue
        if time_net:  # the time part decides; the space part only judges the position
            els = obs.elements
            c.value = _time_net(eva, p, c, els, unit_values(els, c.after), touched)
            continue
        const = sum(note(f) for f in c.feats if f[0] == "ev")
        states = {}
        vals = unit_values(units, c.after)
        for E in units:
            name = unit_name(E)
            if name in obs.channels:
                states[E] = {obs.dwell_after(p, name, vals[E]): 1.0}
        acc, wsum = c.value, 1.0
        tn = cfg.transition_notes
        absent = cfg.absent_notes
        net_items = [(f, 1.0) for f in c.feats] if cfg.backup == "converge" else None
        for t in range(1, cfg.horizon + 1):
            ev = const
            for E, st in states.items():
                ch = obs.channels[unit_name(E)]
                st, trans = _project_with_transitions(ch, st) if tn else (ch.project(st), ())
                states[E] = st
                if net_items is not None:  # gathered, then factorised as one net
                    wt = cfg.horizon_decay**t
                    net_items.extend((("c", E, m0, m), wt * q) for (m0, m), q in trans)
                    for (m, d), q in st.items():
                        if absent or present(E, m):
                            net_items.append((("e", E, m), wt * q))
                            if tf:
                                net_items.append((("et", E, m, bucket(d) if d else 0), wt * q))
                    continue
                for (m0, m), q in trans:  # the standard transitions expected, and their notes
                    ev += q * note(("c", E, m0, m))
                for (m, d), q in st.items():
                    if absent or present(E, m):
                        ev += q * note(("e", E, m))
                        if tf:
                            ev += q * note(("et", E, m, bucket(d) if d else 0))
            wt = cfg.horizon_decay**t
            if net_items is not None:
                continue
            acc += wt * (math.tanh(ev) if cfg.squash and cfg.backup != "converge" else ev)
            wsum += wt
        c.value = eva.dec.combine(net_items) if net_items is not None else acc / wsum
    return cands


def _is_meta_base(k) -> bool:
    return isinstance(k, tuple) and bool(k) and not isinstance(k[0], str)


def _time_net(eva, p, c, units, vals, touched=None) -> float:
    """The time part of the net after a move: the transitions it makes (its own and the
    meta-transitions it triggers), then the standard transition each molette expects next
    (read from its transition molette with its time molette), meta-transitions included.
    The space part (notes of the values) is left out: it only judges the position. The
    molettes the move leaves as they are expect the same thing whatever the move: they are
    the same for every candidate and are not recomputed."""
    from .construction import unit_name

    obs = eva.obs
    cs = obs.cursors.get(p, {})

    def moved(name, v, key=None) -> bool:  # what some move changes (the rest is the same for all)
        if touched is not None and key in touched:
            return True
        cur = cs.get(name)
        return cur is None or not cur.started or cur.pos != v

    def proj(ch, name, key, v):
        st, trans = _project_with_transitions(ch, {obs.dwell_after(p, name, v): 1.0})
        out = [(("c", key, m0, m), q, 1) for (m0, m), q in trans]
        stay = 1.0 - sum(q for _t, q in trans)
        if stay > 1e-3:
            out.append((("c", key, v, v), stay, 1))  # the standard may be to stay
        return out

    items = [(f, 1.0, 0) for f in c.feats if (f[0] == "c" and not _is_meta_base(f[1])) or f[0] == "mt"]
    changed = set()
    for E in units:  # the elements' expected transitions
        if not isinstance(E, frozenset):
            continue
        name = unit_name(E)
        ch = obs.channels.get(name)
        if ch is None or not moved(name, vals[E], E):
            continue
        changed.add(E)
        items.extend(proj(ch, name, E, vals[E]))
    for k, v in c.after.items():  # the raw watchers' expected transitions
        if isinstance(k, str) and k in obs.channels and moved(k, v, k):
            items.extend(proj(obs.channels[k], k, k, v))
    if getattr(eva.cfg, "meta_transitions", False):
        from .construction import unit_value
        for mt in obs.live_mtrans(c.after):  # joint transitions expected (both move at once)
            if not (mt.pair[0] in changed or mt.pair[1] in changed):
                continue
            name = unit_name(mt)
            ch = obs.channels.get(name)
            if ch is None:
                continue
            joint = tuple(vals[x] if x in vals else unit_value(x, c.after) for x in mt.pair)
            _, trans = _project_with_transitions(ch, {obs.dwell_after(p, name, joint): 1.0})
            for ((x0, y0), (x1, y1)), q in trans:
                if x0 != x1 and y0 != y1:
                    items.append((("mt", mt, (x0, x1), (y0, y1)), q, 1))
    return eva.dec.combine_time(items)


def _project_with_transitions(ch, states: dict, prune: float = 1e-3):
    """``Channel.project`` that also returns the transitions it expects, ``((from, to),
    probability)``: the standard molette (read with the time molette) says what follows."""
    from .molettes import bucket as _b

    out: dict = defaultdict(float)
    trans: dict = defaultdict(float)
    cap = ch.cfg.dwell_cap
    td = getattr(ch, "trans_d", None)
    for (v, d), p in states.items():
        h = ch.time.h(v, d + 1) if ch.time.ev.get(v) else 0.0
        if h < 1.0:
            out[(v, min(d + 1, cap))] += p * (1.0 - h)
        if h <= 0.0:
            continue
        row = None
        if td is not None:
            key = (v, _b(d + 1))
            n = td.totals.get(key, 0)
            if n >= ch.cfg.trans_by_dwell_min:
                row = td.counts[key]
        if row is None:
            row = ch.trans.counts.get(v)
            if not row:
                continue
            n = ch.trans.totals[v]
        for x, cnt in row.items():
            q = p * h * cnt / n
            if q >= prune:
                out[(x, 0)] += q
                trans[(v, x)] += q
    z = sum(out.values()) or 1.0
    return ({k: q / z for k, q in out.items() if q / z >= prune},
            [(k, q / z) for k, q in trans.items()])


def energy(eva, env, p, before):
    """The user's principle: the energy constraint reduces the computation.

    1. For every action, the cheap part only: the afterstate and how much it would move
       the molettes (standard, time and every higher time derivative, meta included).
    2. Evaluate the decision molettes on the least-energy share of the actions only
       (``energy_budget``); if none of them tips positive (note > ``energy_threshold``),
       widen the share (x2) until one does or all have been evaluated.
    3. Among the actions that tip positive, keep the one that spends the least energy
       (``energy_pick="least"``) — or the best note within the evaluated share ("best").
    Actions never evaluated keep no features (their decision molettes were not consulted).
    """
    cfg, dec, obs = eva.cfg, eva.dec, eva.obs
    cands = []
    for a in env.actions():
        after, final = env.afterstate(a, p)
        e = obs.action(p, after, cfg.action_mode)
        cands.append(Cand(a, -math.inf, 0.0, None, after, (), final, trace={"energy": e}))
    cands.sort(key=lambda c: c.trace["energy"])
    n = len(cands)
    k = max(1, math.ceil(cfg.energy_budget * n))
    done = 0
    while True:
        for c in cands[done:k]:
            c.feats, c.changed = dec.features(p, before, c.after)
            c.value = c.final if (c.final is not None and cfg.use_final) else dec.value(c.feats)
        done = k
        positive = [c for c in cands[:k] if c.value > cfg.energy_threshold]
        if positive or k >= n:
            break
        k = min(n, 2 * k)
    pool = positive or cands[:k]
    keep = set(map(id, pool))
    for c in cands[:k]:
        if id(c) not in keep:
            c.cost = math.inf
        elif cfg.energy_pick == "least" and positive:
            c.cost = c.value + c.trace["energy"]  # score = -energy
        else:
            c.cost = cfg.beta * cfg.action_scale * c.trace["energy"]
        c.trace["evaluated"] = k
    return cands


def ensure_features(eva, c: Cand, p: int, before: dict) -> None:
    """An action never evaluated (energy filter) still gets its features if it is taken
    (exploration), so that it can learn."""
    if c.feats is None:
        c.feats, c.changed = eva.dec.features(p, before, c.after)
        c.value = c.final if (c.final is not None and eva.cfg.use_final) else eva.dec.value(c.feats)


def _aggregate(notes: list[float], how: str) -> float:
    if not notes:
        return 0.0
    if how == "mean":
        return sum(notes) / len(notes)
    if how == "min":
        return min(notes)
    if how == "extreme":  # the firmest belief decides
        return max(notes, key=abs)
    return sum(notes)


def levels(eva, env, p, before):
    """The user's rule: gain first, energy second; among all the decision molettes,
    maximise the highest-level ones in the current situation.

    An action that ends the episode is decided by its final feedback before anything else.
    Otherwise each action gets a key compared lexicographically: the notes of its decision
    molettes of the highest level (most watchers) first — only those judged at least
    ``level_min_seen`` times count; a level with none falls back to the level below —
    aggregated (``level_agg``) and rounded to ``level_tol``; on a tie, the level below;
    on a final tie, the least energy."""
    cfg, dec, obs = eva.cfg, eva.dec, eva.obs
    cands = evaluate(eva, env, p, before)
    w, seen, k = dec.w, dec.seen, cfg.level_min_seen
    per, top = [], 1
    for c in cands:
        by: dict = {}
        for f in c.feats:
            if seen.get(f, 0) < k:
                continue
            lv = len(f[1]) if f[0] in ("m", "mt") else 1
            by.setdefault(lv, []).append(w.get(f, 0.0))
        per.append(by)
        if by:
            top = max(top, max(by))
    for c, by in zip(cands, per):
        if c.final is not None and cfg.use_final:
            c.key = (1, c.final)
            continue
        key, fallback = [], 0.0
        levels_up = [_aggregate(by[lv], cfg.level_agg) if lv in by else None for lv in range(1, top + 1)]
        for i, v in enumerate(levels_up):  # back off: a missing level takes the level below
            if v is None:
                levels_up[i] = fallback
            else:
                fallback = v
        for v in reversed(levels_up):
            key.append(round(v / cfg.level_tol))
        c.key = (0, *key)
    best = max(c.key for c in cands)
    for c in cands:
        if c.key == best:
            energy = obs.action(p, c.after, cfg.action_mode)
            c.trace["energy"] = energy
            c.key = c.key + (-energy,)
        else:
            c.key = c.key + (-math.inf,)
    return cands


def majority(eva, env, p, before):
    """The user's rule for judging a move: it must make the net positive in general — the
    largest share of the net's decision molettes, standard AND time ("filet espace-temps"),
    positive. With ``cfg.net`` the features are already those of the net only.

    Key, compared lexicographically: an action that ends the episode by its final feedback
    first; then the number of positive decision molettes (note > ``positive_threshold``);
    then the overall lean (sum of the notes); on a final tie, the least energy."""
    cfg, dec, obs = eva.cfg, eva.dec, eva.obs
    cands = evaluate(eva, env, p, before)
    w, thr = dec.w, cfg.positive_threshold
    for c in cands:
        if c.final is not None and cfg.use_final:
            c.key = (1, c.final, 0.0)
            continue
        notes = [w.get(f, 0.0) for f in c.feats]
        if cfg.majority_weighted:  # the share of the net's lean that is positive
            mass = sum(abs(v) for v in notes)
            share = sum(v for v in notes if v > thr) / mass if mass else 0.0
        else:
            positive = sum(1 for v in notes if v > thr)
            share = positive / len(notes) if notes else 0.0
        c.trace["positive_share"] = share
        c.key = (0, round(share, 6), round(sum(notes), 6))
    best = max(c.key for c in cands)
    for c in cands:
        if c.key == best:
            energy = obs.action(p, c.after, cfg.action_mode)
            c.trace["energy"] = energy
            c.key = c.key + (-energy,)
        else:
            c.key = c.key + (-math.inf,)
    return cands


ALGORITHMS = {"greedy": greedy, "profile": profile, "energy": energy, "levels": levels, "majority": majority}
