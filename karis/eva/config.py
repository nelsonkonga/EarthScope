"""All of Eva's knobs in one place."""

from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass
class EvaConfig:
    # --- molettes standard / temps / N-temps (n6, n7, n13)
    dwell_cap: int = 32  # durations above are merged (time molette)
    run_cap: int = 16  # same for the upper rhythm levels
    max_time_depth: int = 3  # 1 = time molette only, 2 = + 2-molette, ...
    min_level_events: int = 30  # transitions a level needs before the next one is created
    ctx_min_support: int = 8  # counts needed before the 2-molette conditions the hazard

    # --- méta molettes standard / temps (n9, n12)
    meta_window: int = 2  # co-change within this many ticks (1 = same tick, 2 = + the next)
    meta_min_count: int = 20
    # Significance (meta_z) decides; the lift only asks for a material effect (+25 %):
    # a watcher that changes rarely cannot show a large lift even when strongly linked.
    meta_min_lift: float = 1.25
    meta_z: float = 4.0
    meta_max_arity: int = 3
    max_meta_channels: int = 64
    meta_check_every: int = 200  # ticks between correlation scans
    meta_decay: float = 0.98  # correlation counts are multiplied by this at each scan (forgetting)
    meta_dissolve_z: float = 1.0  # a correlation molette dissolves below this significance

    # --- moindre action (n11)
    beta: float = 0.0  # weight of the action term in the decision score
    action_mode: str = "surprise"  # surprise | displacement | shift
    action_scale: float = 0.05  # action is multiplied by this before beta (bits -> score)

    # --- molettes de décision (n8)
    alpha: float = 0.3  # normalised step (V moves by alpha * error)
    alpha_decay: float = 3000.0  # >0: step = alpha / (1 + episodes / alpha_decay), so notes settle
    alpha_min: float = 0.01
    lam: float = 0.7  # lambda-return; 1.0 = pure final result
    gamma: float = 1.0  # discount (0 for per-step tasks such as language)
    # How decision molettes learn at the end of an episode:
    #  "belief" (the user's rule) = every decision tilts toward what followed it, no credit
    #           assignment, tilt modulated by the prior belief (neutral notes move most);
    #  "max"    = target = feedback + best note at the same perspective's next decision
    #           (TD / Q-learning: a form of credit assignment, kept for comparison);
    #  "lambda" = lambda-return of what was actually done;
    #  "independent" = each decision molette is its own estimate of the outcome and tilts
    #           toward it with its own belief (the user's rule, read literally).
    backup: str = "belief"
    # backup "converge": each decision molette is its own estimate of the outcome; it tilts by
    # converge_alpha * (1 - note^2)^resistance * (R - note): never divided among the molettes,
    # never shrinking with data; only its own belief resists change (a molette with no data
    # stands at the mean outcome: it says nothing)
    converge_alpha: float = 0.05
    # the net of a decision (backup "converge"): only the molettes with an impact of their own
    # on the result (|note - mean| >= attention) enter it; a meta molette in the net replaces
    # its members (the same dynamics is not counted twice); the move whose net is the most
    # positive is chosen
    attention: float = 0.2
    resistance: float = 1.0  # belief modulation: tilt x (1 - V^2)^resistance (0 = none)
    squash: bool = True  # note of a decision = tanh(sum of notes), in (-1, 1)
    # Every standard and time molette has its decision molette (the user's spec).
    time_features: bool = True  # decision molettes of the time molettes
    rhythm_features: bool = False  # decision molettes of the N-time molettes
    change_features: bool = False

    # --- méta molettes de décision (n10)
    meta_decisions: bool = True
    md_min_count: int = 12
    md_z: float = 2.5
    md_min_effect: float = 0.15
    md_max_arity: int = 3
    max_meta_decisions: int = 160
    md_max_candidates: int = 200_000  # candidate statistics kept before pruning
    md_context: tuple[str, ...] | None = None  # watchers usable as context (None = all)
    md_direct_triples_upto: int = 12  # with <= this many watchers, test triples directly
    md_max_union: int = 0  # >0: also test unions of two meta decisions sharing a watcher (compromise of compromises) up to this size
    md_prune_every: int = 1500  # >0: every N episodes drop the useless meta decisions
    md_prune_ratio: float = 0.3  # useless = utility (max |note|) < ratio x the best one
    md_block_for: int = 6000  # a pruned combination cannot be reborn for this many episodes

    # --- algorithme de décision (n14)
    # No search: foresight only through the energy and decision profiles.
    algo: str = "profile"  # greedy | profile | energy | levels | majority — used to play
    train_algo: str = "greedy"  # used while training (6x cheaper, learns as well)
    horizon: int = 1  # ticks the molettes are projected after the action (profile)
    horizon_decay: float = 1.0  # weight of tick t is decay**t
    profile_metric: str = "value"  # value | kl
    tau: float = 0.2  # temperature of the wanted distribution (kl)
    epsilon: float = 0.3  # exploration while training
    epsilon_decay: float = 0.0  # >0: epsilon / (1 + episodes / epsilon_decay)
    epsilon_min: float = 0.02
    use_final: bool = True  # an action that ends the episode is scored by its final feedback
    # energy algorithm (the energy constraint reduces the set of actions evaluated)
    energy_budget: float = 0.34  # share of the actions (least energy first) evaluated at first
    energy_threshold: float = 0.0  # "tips positive" = note above this
    energy_pick: str = "least"  # least: least energy among the positive; best: best note
    # levels algorithm (gain first: highest-level decision molettes first, energy last)
    level_agg: str = "mean"  # sum | mean | min | extreme
    level_min_seen: int = 20  # an entry counts in its level once judged this many times
    # majority algorithm (the move must make the net mostly positive, space and time)
    positive_threshold: float = 0.0
    majority_weighted: bool = False  # share of the lean that is positive instead of a count
    level_tol: float = 0.02  # notes closer than this are a tie at that level

    # --- filet (net): a cover of the watchers by what is judged important — each strongly
    # correlated group by its correlation molette, every other watcher as a singleton. Only
    # the net is evaluated: energy, projection, transition and decision molettes; the
    # decision takes the action whose net decision molettes lean most toward good.
    net: bool = False
    # a combination born from feedback (correlated with the outcome) enters the net at birth
    # with its statistical molettes, on probation; it leaves it when pruning finds it useless
    net_from_feedback: bool = False
    # --- time axis of the net: chain molettes over successive transitions (sequences.py)
    sequences: bool = False
    seq_window: int = 4  # B "follows" A if it happens within this many ticks after it
    seq_max_len: int = 3
    max_chains: int = 48
    # --- construction elements (construction.py): the molettes describe how the current
    # state is built (sets of transitions built together, with a magnitude), not the base
    # state; the watchers are only sensors. Replaces the net by the elements.
    construction: bool = False
    elem_max_size: int = 3
    max_elements: int = 64
    elem_check_every: int = 50  # episodes (per perspective) between scans
    # meta decision molettes on construction: a set of events whose joint presence the
    # outcome judges differently from what its parts say becomes an element (feedback)
    elem_from_feedback: bool = False
    max_feedback_elements: int = 96
    elem_fb_z: float = 4.0  # many sets are tested: significance as strict as the correlations'
    elem_fb_min_count: int = 30
    # every configuration observed during the episode (not only Eva's afterstates) tilts
    # toward the result: e.g. the state after the other side's move
    learn_observed: bool = False
    # decision molettes of the transitions of the elements: every transition the world
    # brings (the other side's move included) tilts toward the result, and the decision
    # profile reads the note of the standard transition each element expects next
    transition_notes: bool = False
    # the standard molette conditioned on the time molette: P(next | position, time spent)
    # (used by the projection when it has seen enough of that moment)
    trans_by_dwell: bool = False
    trans_by_dwell_min: int = 10
    # smoothing of the time molettes: "half" (toward 1/2 per tick) or "mean" (toward the
    # position's own mean rate of change: unbiased for slow dynamics, see checks/curve_derivatives.py)
    hazard_prior: str = "half"
    # discovery of the dynamics to follow: units (elements, then meta molettes) whose
    # transitions happen at the same tick more than chance get a meta molette over them,
    # with its transitions, time molette, derivatives and decision molettes; recursively
    elem_metas: bool = False
    max_elem_metas: int = 96
    meta_track: int = 48  # units watched for joint transitions: the most useful ones
    # how a meta molette over units is born: "feedback" (units moved by the same step whose
    # joint value the outcome judges apart from their parts: correlation of decision
    # molettes) or "timing" (units transitioning at the same tick more than chance)
    meta_birth: str = "feedback"
    # the net of the construction: only the ``net_size`` most useful units (plus those on
    # probation since their birth) are evaluated — features, projection, energy; 0 = all
    net_size: int = 0
    # class molettes: for each shape of element dynamics, how many elements stand open at
    # each number of steps done (what is learned of one element holds for its whole class)
    class_molettes: bool = False
    # meta molettes born at the moment two elements progress at the same tick and stay
    # constructible (``live_meta_min`` times): they start following the joint dynamics; the
    # net of a decision also holds the meta molettes live in the state shown at that instant
    # (both members started and still constructible): the net is not static
    # base molettes discovered from the dynamics (never from the outcome): a set of steps is
    # a construction element when its completion changes the dynamics that follow out of
    # norm — here, after it no molette moves any more (the episode stops) — at least
    # ``dyn_min_ends`` times and in ``dyn_ratio`` of its completions
    elem_from_dynamics: bool = False
    # a construction seen from both sides: two sets of steps on the same watchers from the
    # same starting values are one element (one side's steps are the other's blocks); it is
    # part of the state as soon as either side has built in it, and live while one side only
    two_sided: bool = False
    dyn_min_ends: int = 10
    dyn_ratio: float = 0.9
    dyn_max_cand: int = 30000
    live_metas: bool = False
    live_meta_min: int = 5
    # meta-transition molettes: the transition molettes of two live elements that change at
    # the same tick (``mt_min`` times) form a meta-transition; its decision molettes judge
    # their joint transitions
    meta_transitions: bool = False
    mt_min: int = 5
    # the space part of the net (notes of the current values) only judges the position; a
    # move is chosen for the time part: the transitions it makes and the standard ones that
    # follow (meta-transitions factorising their members)
    time_net: bool = False
    # what a transition says in the time net: the change it brings (its note minus the note
    # of the state it leaves); a molette that stays then says nothing
    time_impact: bool = False
    net_probation: int = 300  # episodes a newborn unit is evaluated before it must be useful
    # discovery of the base molettes (discovery.py): a raw numeric watcher is watched for
    # ``discover_ticks`` ticks, then Eva chooses its grain and context by herself
    # how the notes of a decision's molettes are combined: "sum" or "mean" (independent
    # notes each estimate the outcome: their mean does not favour moves that merely make
    # more molettes present)
    note_agg: str = "sum"
    # every unit of the net gives exactly one note, its "nothing built" state included: all
    # candidates are compared on the same molettes (no bias toward moves that merely make
    # more molettes present)
    absent_notes: bool = False
    # a transition molette learns the same way whoever brought the transition: Eva's own
    # transitions tilt as one group (their own belief, their own step), like the world's,
    # instead of being diluted among the state notes of the decision
    trans_symmetric: bool = False
    discover: bool = False
    discover_ticks: int = 5000
    discover_min_dwell: float = 8.0

    # --- molettes de dynamique (eva/dynamics.py, the user's theory of 2026-11-09): every
    # molette captures a dynamic (its norm and its extremes), transitions of transitions up
    # to ``dyn_degrees``, meta molettes at every degree, decision molettes on every reading
    model: str = "dynamics"  # dynamics (eva/dynamics.py, the default) | molettes (channels, observer, decision bank: the earlier model)
    dyn_degrees: int = 3  # 1 = values, 2 = + transitions, 3 = + transitions of transitions
    dyn_extreme_z: float = 2.0  # a transition is out of norm when its surprise is this many spreads above the typical one
    dyn_elements: bool = True  # discover construction elements from the dynamics
    dyn_step: float = 0.05  # constant step of a decision molette (never divided, never shrinking)
    dyn_check_every: int = 25  # episodes between births of elements (and of metas if periodic)
    dyn_meta_min: int = 10  # co-changes before a meta molette can be born
    # "spontaneous": a meta molette is born at the tick its co-changes pass the test (count,
    # lift, z); "periodic": only at the check every dyn_check_every episodes (before 2026-11-10)
    dyn_meta_birth: str = "spontaneous"
    # the end is an event (the user's Blink note): a departure never seen without the end that
    # follows it (a mated king leaving the board) is worth that end; the dynamic minimax sees
    # it coming (quiet dynamics aimed at it, a piece with nowhere to go and no one to step in)
    dyn_ends: bool = True
    # the end carries its distance (the user's Blink rule « le plus proche de la victoire, le plus
    # loin possible de la victoire adverse »): outcome x (1 - T / (2 (T + norm length))).
    # Off: against Stockfish it gave the own pieces negative values — a long game ends with
    # fewer pieces whatever they are worth, so final counts and length are confounded (RESULTS § 11)
    dyn_end_distance: bool = False
    # piece values (count gradients) read each level's note against how far it could have
    # moved with its evidence: a constant outcome gives no value. Off: against an opponent
    # Eva always loses to, it removes every value (no false one, but none at all) (RESULTS § 11)
    dyn_debias: bool = False
    # with the dynamic minimax, the decision molettes (readings, transitions, types, meta
    # molettes, field) break its ties; False: ties are broken at random (an ablation)
    dyn_tiebreak: bool = True
    # the decision molettes judge whether each dynamic of the minimax is good or bad (user,
    # 2026-11-10: all of them, not only the transitions'): Eva's action and each response of
    # the tree are read as the judge reads an action; False: they only break the minimax's ties
    dyn_minimax_notes: bool = True
    # the domain's signals (captures, promotions...: the only thing imported from its logic) give
    # each reading a local outcome: the end + the signals within dyn_signal_window ticks after it
    dyn_signals: bool = True
    dyn_signal_window: int = 4
    # "issue" (the default before 2026-11-11): a reading tilts toward the end of the episode + the
    # signals within dyn_signal_window ticks after it; "plaisir" (default; the user, 2026-11-11:
    # signals tell what is pleasant, victory is one of them, they go to every decision molette by
    # the same rule): every signal credits every
    # molette that intervened before it appeared — a reading tilts toward the end + every signal
    # after its first occurrence (no window): the generalisation of the end crediting every reading
    dyn_signal_mode: str = "plaisir"
    # what a reading tilts toward (the end and every signal after it): "clip" to [-1, 1] (before
    # 2026-11-13: it flattened the signals of every mated game), "none" (as it is), "tanh" (bounded,
    # its order kept) — RESULTS.md § 32
    dyn_target_bound: str = "clip"
    # « le tableau statique raconte une histoire »: with a layout, the field's own transitions
    # (neighbour pairs, three in a row, along each lattice direction) are readings too
    dyn_story: bool = False
    # attention in the move judge (the user, 2026-11-11: « plus une molette est neutre moins sa voix
    # doit compter »): the weight of a note's voice is how far from neutral it is against what a
    # neutral molette shows after as many tilts (instead of |note|^dyn_power)
    dyn_attention_judge: bool = False
    # a capture is worth what the decision molette of its departure event says ("event", learned
    # from the signals), the signal that came with that event ("signal": its immediate pleasure —
    # the dynamic minimax builds the continuation itself; with the "plaisir" crediting the event's
    # note also holds what followed, a recapture included, and the minimax counted it twice:
    # RESULTS.md § 19; the default) or the gradient of the count molettes ("count", before the signals)
    dyn_capture_value: str = "signal"
    dyn_max_metas: int = 128  # meta molettes per degree
    dyn_elem_pool: bool = True  # the same construction built by any side shares its evidence
    dyn_field: bool = True  # field derivatives (atomic events, relations) when the environment gives a layout
    # « la réponse arrive après une lecture » (user, 2026-11-10): when the perspective begins an
    # episode with steps of its own without a choice (it reads), the choices that follow are judged
    # by notes joining each reading to the transition the candidate makes. In games every step of
    # one's own is a choice, and the world's moves are not a reading: unchanged
    dyn_reading: bool = True
    # each candidate judged after a reading is read against the norm of what the reading says of
    # it; that norm follows its drift over ~1/dyn_reading_norm episodes (RESULTS.md § 17)
    dyn_reading_norm: float = 0.01
    # attention when pooling the notes joined to a reading (the user, 2026-11-11: « plus une molette
    # est neutre, moins sa voix doit compter »): "neutrality" — weight = how far from neutral the note
    # is against what a neutral molette shows after as many tilts, to the power dyn_power;
    # "+saillance" — and what is ordinary within the reading itself (the same pattern seen by many
    # sensors) counts less; "extremes" — weight |note|^dyn_power (before 2026-11-11);
    # "neutrality-1" — only what goes beyond the neutral spread counts. RESULTS.md § 18
    dyn_attention: str = "neutrality+saillance"
    dyn_field_value: str = "count"  # count: gradient of the count molette's note | event: note of the departure
    dyn_field_decision: str = "minimax"  # minimax: the dynamic minimax decides | items: captures and danger as readings
    dyn_depth: int = 3  # dynamic minimax: steps of capture dynamics followed (world, Eva, world...)
    dyn_breadth: int = 8  # dynamic minimax: capture dynamics considered per step (the most valuable)
    dyn_field_danger: str = "possible"  # possible: the extreme (seen to happen) | norm: the relation's probability
    # « un tableau statique peut tout aussi contenir des transitions de dynamiques » (the user,
    # 2026-11-11): the dynamic minimax also reads in a static field the dynamics that another one's
    # occurrence would change — a line of capture held shut by one piece opens when it leaves (a
    # piece that cannot leave without exposing another: the pin; a departure that unmasks a capture),
    # and one displacement can create several capture dynamics at once (a double threat): the
    # world's quiet dynamics that make such a transition are among its responses. RESULTS.md § 20
    dyn_lines: bool = True
    # one dynamic seen in several contexts, learned per symbol: a symbol seen making most of its
    # displacements both ways (Δ and −Δ: the same transition read backwards, « les transitions doivent
    # être symétriques ») makes each both ways; a symbol whose captures were seen to be its
    # displacements (onto an occupied watcher by the same Δ as onto an empty one) captures by every
    # displacement it was seen to make and moves by every one it captured with; a displacement seen
    # at 1, 2, 3 successive distances along a lattice line goes on along it. A pawn's are none of
    # these: nothing is extended. A queen need not have been seen taking along every line. RESULTS.md § 20
    # True is a reference only: the user's order (2026-11-12) is never to give Eva domain rules.
    # "heatmap" (default): the same, found instead of written — the user's definition of a dynamic
    # (2026-11-12, eva/heatmaps.py): each symbol's displacements are a heatmap, its concentrations the
    # molettes, and the transformations proven between them (mirrors, rotations, the identity, the
    # step along a line) the transition molettes; what they imply is added. After 12 games it finds
    # what the rules by hand (True) find on two Evas, not on a third (rare queen captures); with fewer
    # games it needs more evidence. RESULTS.md § 21
    dyn_same_dynamic: bool | str = "heatmap"
    # what Eva discovers once looked at closer — nothing named, counted on everything (RESULTS.md § 22,
    # 214 → 202 and 241 → 199 centipawns lost on hard positions): a cell out of norm happened
    # but needs its cause — it is not placed on the field (heatmap mode)
    dyn_norm_only: bool = True
    # a displacement depends on the place it is made from only where the heatmap of its places says
    # so (it would have been seen elsewhere, and never was): the pawn's two steps, from its first row
    dyn_place: bool = True
    # a relation of the field (symbol y within symbol x's capture dynamics) that a side met before its
    # move and never left after it, where chance expected it, becomes out of norm little by little: a
    # move making it is not one of that side's dynamics (nothing names it: Eva found the rule of check)
    dyn_never: bool = False  # the user (2026-11-12): « ce n'est pas être rare qui doit dissuader » — refusals do
    dyn_meta_compete: bool = False  # budget full: a clearly more significant meta molette replaces the weakest
    dyn_meta_arity: int = 4  # most base dynamics a meta molette joins (2 = pairs only)
    dyn_space: bool = False  # the values' notes (space part) also choose; else they only judge
    dyn_project: bool = True  # the dynamics the molettes expect the world to make next
    dyn_alive: bool = True  # a dynamic whose norm says it can no longer move says nothing of the future
    dyn_types: str = "both"  # off | both | type: readings also (or only) read by the molette of their type of dynamics
    dyn_type_norm: bool = True  # the type of dynamics also has its own norm (what the world does next)
    dyn_relative: bool = False  # a reading says what it brings beyond what the molette's own norm expected
    # a decision molette learns what follows its dynamic beyond the norm of what follows any dynamic
    # (the running mean of the targets): against a world that always wins, absolute notes slid to the
    # common level, the frequent first — they measured frequency, not value (RESULTS.md § 23)
    dyn_outcome_norm: bool = True  # the user chose it (2026-11-12) after the measures of RESULTS.md § 23
    # the norm a note is read against is the norm of what follows any dynamic at the same moment of the
    # episode (its tick): one norm for all made early dynamics look bad and late ones good
    dyn_norm_by_tick: bool = True
    dyn_freeze_notes: bool = False  # diagnosis only: decision molettes never move (observation still learns)
    # only the decision molettes whose note is proven beyond chance take part in a decision (the others
    # are silent; learning is unchanged): « un sous-ensemble des molettes est activé » (RESULTS.md § 31)
    dyn_proven: bool = False
    # exploration while training (``epsilon``): "random" any action; "anchored" — when the norm of
    # outcomes is not favourable, beyond the norm of one base molette of a good anchor (a meta molette
    # or a known transition), the rest kept in norm, among the actions judged near the best
    # (``Dynamics.explore``); a favourable norm explores at random as before; "space" — the same, in the
    # space of changes (``Dynamics.explore_space``): anchors are the heat layer's unions and intersections,
    # a variant is one displacement beyond its heatmap's norm into a zone an anchor holds in its norm, the
    # others in theirs; prudence = within a note's noise of the best; anchored as often as the norm is
    # unfavourable (``unfavourable``), at random otherwise (RESULTS.md § 23)
    dyn_explore: str = "random"
    # decision molettes on what a move does to the field's relations (symbol y within symbol x's
    # capture dynamics: the kinds it creates, the kinds it ends) — space-free, so what one game
    # teaches holds on every square (RESULTS.md § 23)
    dyn_relations: bool = False
    # « dans la maille, pour chaque molette créée elle a aussi sa molette de décision qui au début est
    # juste une moyenne des molettes de décision des molettes qui l'ont engendrée » (the user,
    # 2026-11-13): the decision molette of a meta molette (an intersection) is born with the mean of the
    # notes of the two dynamics it was born from, at the same reading, then tilts on its own. False: it
    # is born neutral (0), as before. RESULTS.md § 36. The user's final choice (2026-11-14, after § 37):
    # « quand une méta molette est créée elle n'hérite plus la décision de ses parents, de telle sorte
    # qu'elles commencent à l'équilibre ; plus une molette de décision est neutre, moins elle a
    # d'impact sur le résultat final »: False (every created molette, intersection or union, starts at
    # 0 and weighs |note|^dyn_power in the pool, nothing at birth). RESULTS.md § 38
    dyn_birth_note: bool = False
    # « le mur est juste une molette découverte et notée négativement » (the user, 2026-11-13): the
    # relation dynamics that one move makes together more often than chance (the meta molettes' test:
    # count, lift, z) get a meta molette over them, an intersection, then intersections of
    # intersections up to ``dyn_meta_arity`` members. Its decision molette is noted as the relations
    # are (every signal after it) and takes part in the decision when a move makes all its members
    # (activated). Nothing says which ones lead to a wall: their notes do. RESULTS.md § 36
    dyn_relation_metas: bool = False
    dyn_relation_metas_max: int = 4096  # relation meta molettes at most (one note each)
    # « deux dynamiques qui viennent toujours ensemble, c'est une union prouvée qui s'est simplifiée en
    # un objet unique, et non une intersection » (the user, 2026-11-14): relation dynamics never seen
    # one without the other (``dyn_meta_min`` times at least) become one object, ``("RU", members)``,
    # born with the mean of their notes, noted once and voting once; no intersection is born between
    # them. One of them made without the others: the union was not proven, it dissolves. RESULTS.md § 37
    dyn_relation_unions: bool = False
    # « la voix d'une intersection compte seulement pour ce qu'elle ajoute à ses parents » (the user,
    # 2026-11-14: information relative, Ockham's razor): a meta molette's decision molette (an
    # intersection of cells, of relations) votes with its note minus the mean of its parents' notes; a
    # newborn one says nothing. False: with its whole note (which repeats its parents). RESULTS.md § 37
    dyn_meta_relative: bool = False
    dyn_risk: float = 0.0  # weight of the worst possible next dynamic against the norm's expectation
    dyn_measure: str = "pool"  # sum | mean | pool | worst: how the readings are combined
    dyn_power: float = 2.0  # pool: weight of a reading = |note|^power (extremes weigh most)

    seed: int = 0

    def as_dict(self) -> dict:
        return asdict(self)
