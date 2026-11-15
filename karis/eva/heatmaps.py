"""Heatmaps of dynamics — one definition of a dynamic for every domain (the user, 2026-11-12).

« Je définirais la dynamique un peu comme une heatmap, et les endroits de concentration seront
les molettes. […] les molettes sont les dynamiques, les métamolettes sont l'intersection des
dynamiques, et les molettes de transition sont un genre de pont pour l'union des dynamiques.
[…] avec assez de preuve de l'union de 2 heatmaps on les simplifie en une transition. »

A dynamic is a heatmap: mass on the cells of a space, a cell being a tuple of integers (a
displacement on a lattice, a change of value…) and its mass how often it was seen. The space is
the space of the *changes*, never the place where they happen: the same molette is recognised
anywhere. A field is read by placing each molette where its symbol stands, like a stamp (a
convolution); nothing is learned place by place.

Molettes — the concentrations of a heatmap
    Every seen cell warms its neighbours (a kernel of radius ``RADIUS``): the concentrations
    are the warm regions, seen cells joined when their warmth meets (every coordinate differs by
    at most 2·RADIUS) — a dynamic seen at distances 1, 3, 5, 7 and not yet at 2, 4, 6 is one
    concentration, not four. Inside a
    concentration a cell is in the norm when its mass is typical of the others' (log mass,
    leave-one-out z within ±Z), out of norm otherwise: a rare cell, or a hotspot.

Transition molettes — bridges: the union of two dynamics simplified into a transformation
    « Si je vois ça, je dois forcément voir ça. » A transformation T of the space carries a
    concentration A onto a concentration B of a heatmap (A's own included: a symmetry of the
    dynamic) when the cells of A's norm land, through T, on that heatmap's norm: most of them
    (``HOLD``), more than chance would put there (its share of the space, binomial tail below
    ``CHANCE``), and the others not where it is warm — its heat at a cell is its expected mass
    there, so a miss where it is warm means it would have been seen there were it the same
    dynamic (summed heat above ``VETO``: P < CHANCE). The reading goes to the whole heatmap,
    not to one of its concentrations: an unseen cell can cut one dynamic into fragments.
    Transitions are symmetric: the bridge read backwards is T⁻¹ from B into A's heatmap. When
    both readings hold and one is sure (the lower bound of its share, Wilson z = 1, reaches
    ``HOLD``), the two are one dynamic seen through T — the union is simplified into
    the transition: B must also hold T(A) and A must hold T⁻¹(B), the cells they were never
    seen at but that the transition implies (closed transitively). Only the norm travels: an
    out-of-norm cell happened, but is not the dynamic's shape. One reading alone is an
    inclusion (a dynamic inside another, not the reverse): it implies nothing.
    The transformations are the space's own, the same for any lattice: the signed permutations
    of the coordinates (mirrors and rotations; the identity: the same dynamic in two contexts)
    and the step along the cell's line, d → d ± d/gcd(d) (a change that goes on). What goes on
    is the same dynamic: the step joins a concentration to itself only (between two, one step
    of shift is almost the identity, with weaker evidence).
    Calibrated against the rules of chess (used only to judge, Eva never sees them): a queen
    seen 63 % of the time along a rook's lines lands 17/27 in the rook's heatmap — but the rook
    is warm on the queen's diagonals and was never seen there: vetoed. A king seen taking only
    forward, inside its displacements: its misses fall where its captures are cold: one dynamic.
    On 5 Evas trained 2 to 12 games, no false cell implied; after 12, nothing missing.

Types of transitions — the transition heatmaps
    A concentration's transition heatmap: mass on the transformations (keyed as tuples of
    integers) by the evidence each carried from it. Their sum is the layer's transition heatmap:
    its cells are the types of transitions, its concentrations families of types.

Meta molettes — intersections
    Where two or more concentrations of different heatmaps share cells: a meta molette over
    them, its cells holding the smallest of the members' masses, with its own norm and
    out-of-norm. They exist for transition heatmaps too: the transformations several dynamics
    share.

Degrees — types of types
    The layer above takes the transition heatmaps as its heatmaps; its transformations act on
    transformations by conjugation (S·T·S⁻¹: the same transition seen in a mirrored or turned
    frame): its bridges join transition heatmaps of the first degree. Conjugates of the
    lattice's transformations are lattice transformations, so the hierarchy closes there: a
    third degree would read the same cells as the second.
"""

from __future__ import annotations

import math
from collections import defaultdict
from itertools import permutations, product

RADIUS = 1  # each seen cell warms the cells within this distance (Chebyshev)
Z = 2.0  # a cell is out of norm beyond Z spreads of its concentration's log masses
SPREAD = 1.0  # floor of that spread: masses within a factor e of each other are never out of norm
HOLD = 0.6  # a bridge holds when this share of the source's cells lands where the target was seen
CHANCE = 0.01  # … and chance (the target's share of the space) would put that many there less often
ARITY = 4  # most concentrations a meta molette joins
VETO = math.log(1 / CHANCE)  # a reading whose misses fall where the target is this warm (summed
#   heat: its expected mass there) is contradicted — it would have been seen there (P < CHANCE)
STEP_ACROSS = False  # the step along a line also bridges two different concentrations


def wilson_low(k: float, n: float, z: float = 1.96) -> float:
    """Lower bound of the proportion k / n (Wilson, 95 %): "almost always" needs evidence."""
    if n <= 0:
        return 0.0
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - r) / d


def chance_tail(k: int, n: int, p: float) -> float:
    """P(at least k of n land by chance on cells holding a share p of the space)."""
    if k <= 0:
        return 1.0
    p = min(max(p, 1e-12), 1.0)
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1))


AXES = "xyzwvu"


class Transform:
    """A transformation of the space: a signed permutation of the coordinates (``y_i = sign_i ·
    c_perm(i)``), or the step along the cell's line (``step`` +1: one more, −1: one less)."""

    __slots__ = ("perm", "signs", "step", "key", "name")

    def __init__(self, perm, signs, step: int = 0):
        self.perm, self.signs, self.step = tuple(perm), tuple(signs), step
        n = len(self.perm)
        m = [0] * (n * n)
        for i, (j, s) in enumerate(zip(self.perm, self.signs)):
            m[i * n + j] = s
        self.key = tuple(m) + (step,)
        if step:
            self.name = "along" if step > 0 else "back"
        else:
            ax = [AXES[j] if j < len(AXES) else f"x{j}" for j in range(n)]
            self.name = "(" + ",".join(("-" if s < 0 else "") + ax[j] for j, s in zip(self.perm, self.signs)) + ")"

    @property
    def identity(self) -> bool:
        return not self.step and self.perm == tuple(range(len(self.perm))) and min(self.signs) > 0

    def __call__(self, c):
        if self.step:
            g = math.gcd(*map(abs, c))
            if not g:
                return None
            out = tuple(x + self.step * (x // g) for x in c)
            return out if any(out) else None
        return tuple(s * c[j] for j, s in zip(self.perm, self.signs))

    def inverse(self) -> "Transform":
        if self.step:
            return Transform(self.perm, self.signs, -self.step)
        perm, signs = [0] * len(self.perm), [1] * len(self.perm)
        for i, (j, s) in enumerate(zip(self.perm, self.signs)):
            perm[j], signs[j] = i, s
        return Transform(perm, signs)

    def __repr__(self) -> str:
        return self.name


def lattice_transforms(n: int) -> list:
    """The transformations every lattice of dimension n has: its 2ⁿ·n! signed permutations
    (the identity first) and the step along a line, both ways."""
    out = [Transform(p, s) for p in permutations(range(n)) for s in product((1, -1), repeat=n)]
    out.sort(key=lambda t: (not t.identity, t.key))
    return out + [Transform(range(n), (1,) * n, 1), Transform(range(n), (1,) * n, -1)]


class Conjugation:
    """A transformation of transformations (degree 2): T ↦ S·T·S⁻¹ on their keys."""

    __slots__ = ("s", "n", "name", "key", "step")

    def __init__(self, s: Transform):
        self.s, self.n, self.step = s, len(s.perm), 0
        self.name, self.key = "conj " + s.name, s.key

    @property
    def identity(self) -> bool:
        return self.s.identity

    def __call__(self, key):
        n = self.n
        if len(key) != n * n + 1:
            return None
        S = [[0] * n for _ in range(n)]
        for i, (j, sg) in enumerate(zip(self.s.perm, self.s.signs)):
            S[i][j] = sg
        M = [list(key[i * n:(i + 1) * n]) for i in range(n)]
        SM = [[sum(S[i][k] * M[k][j] for k in range(n)) for j in range(n)] for i in range(n)]
        out = [sum(SM[i][k] * S[j][k] for k in range(n)) for i in range(n) for j in range(n)]  # · Sᵀ
        return tuple(out) + (key[-1],)

    def inverse(self) -> "Conjugation":
        return Conjugation(self.s.inverse())

    def __repr__(self) -> str:
        return self.name


def components(cells) -> list[set]:
    """The concentrations: seen cells joined when their warmth meets (Chebyshev ≤ 2·RADIUS)."""
    left, out = set(cells), []
    if not left:
        return out
    n = len(next(iter(left)))
    r = 2 * RADIUS
    offs = [o for o in product(range(-r, r + 1), repeat=n) if any(o)]
    while left:
        c = left.pop()
        comp, todo = {c}, [c]
        while todo:
            x = todo.pop()
            for o in offs:
                y = tuple(a + b for a, b in zip(x, o))
                if y in left:
                    left.remove(y)
                    comp.add(y)
                    todo.append(y)
        out.append(comp)
    return out


def norm_split(cells: dict) -> tuple[dict, set, set]:
    """Leave-one-out z of every cell's log mass against the others': the norm and the out-of-norm."""
    logs = {c: math.log1p(m) for c, m in cells.items()}
    z = {}
    tot, sq, n = sum(logs.values()), sum(v * v for v in logs.values()), len(logs)
    for c, v in logs.items():
        if n < 2:
            z[c] = 0.0
            continue
        mu = (tot - v) / (n - 1)
        var = max((sq - v * v) / (n - 1) - mu * mu, 0.0)
        z[c] = (v - mu) / max(math.sqrt(var), SPREAD)
    norm = {c for c, x in z.items() if abs(x) <= Z}
    return z, norm, set(cells) - norm


class Concentration:
    """A molette: one concentration of a heatmap, its norm and its out-of-norm; ``implied`` holds
    the cells its transitions say it must also hold (never seen)."""

    def __init__(self, source, cells: dict):
        self.source, self.cells = source, dict(cells)
        self.z, self.norm, self.out = norm_split(self.cells)
        self.implied: set = set()
        self.whole = False  # the whole heatmap, read as one (it has several concentrations)

    @property
    def mass(self) -> float:
        return sum(self.cells.values())

    def all(self) -> set:
        return set(self.cells) | self.implied

    def shape(self) -> set:
        """What a transition carries: the norm and what is implied (not the out-of-norm)."""
        return self.norm | self.implied

    def __repr__(self) -> str:
        return f"<{self.source} {len(self.cells)} cells>"


class Bridge:
    """A transition molette: T carries A onto B (``hits`` of ``tries`` of A's norm land in B's
    norm); ``back`` is the same bridge read backwards (T⁻¹ from B to A), None if it fails."""

    __slots__ = ("a", "t", "b", "hits", "tries", "back")

    def __init__(self, a, t, b, hits, tries):
        self.a, self.t, self.b, self.hits, self.tries, self.back = a, t, b, hits, tries, None

    @property
    def union(self) -> bool:
        return self.back is not None

    def __repr__(self) -> str:
        return f"{self.a.source}→{self.b.source} by {self.t.name} {self.hits}/{self.tries}" + (" ⇄" if self.union else "")


class Meta:
    """A meta molette: the intersection of concentrations of different heatmaps."""

    def __init__(self, members: tuple, cells: dict):
        self.members, self.cells = members, cells
        self.z, self.norm, self.out = norm_split(cells)

    def __repr__(self) -> str:
        return " ∩ ".join(str(m.source) for m in self.members) + f" ({len(self.cells)} cells)"


class Layer:
    """One degree: heatmaps → molettes (concentrations), meta molettes (intersections),
    transition molettes (bridges) and what they imply, and the transition heatmaps that are the
    heatmaps of the degree above."""

    def __init__(self, heatmaps: dict, transforms: list, bound=None, degree: int = 1, metas: bool = True):
        self.degree, self.transforms, self.bound = degree, transforms, bound
        self.heatmaps = {name: {c: m for c, m in h.items() if m > 0} for name, h in heatmaps.items()}
        self.heatmaps = {k: h for k, h in self.heatmaps.items() if h}
        self.molettes: list[Concentration] = []
        # what a transition can carry: each concentration, and each heatmap whole when it has
        # several (an unseen cell can cut one dynamic into fragments: a bishop's diagonal seen at
        # 2 and 3 squares, never at 1, is apart from the rest of its star)
        self.groups: list[Concentration] = []
        for name, h in self.heatmaps.items():
            mine = [Concentration(name, {c: h[c] for c in comp}) for comp in sorted(components(h), key=lambda s: sorted(s))]
            self.molettes.extend(mine)
            self.groups.extend(mine)
            if len(mine) > 1:
                whole = Concentration(name, h)
                whole.norm = set().union(*(m.norm for m in mine))
                whole.out = set(h) - whole.norm
                whole.whole = True
                self.groups.append(whole)
        if bound is not None:
            self.volume = math.prod(hi - lo + 1 for lo, hi in bound)
        else:
            self.volume = max(len({c for h in self.heatmaps.values() for c in h}), 1)
        self.bridges = self._bridges()
        self._close()
        self.metas = self._metas() if metas else []

    def _inside(self, c) -> bool:
        return self.bound is None or all(lo <= x <= hi for x, (lo, hi) in zip(c, self.bound))

    def _reading(self, A, t, B):
        """(hits, tries, heat) of t carrying A's norm onto B's (a cell t leaves in place, in A's
        own heatmap, carries no evidence); heat: how warm B is, summed, where A's cells land and
        B was never seen (warm: B would have been seen there, were it the same dynamic).
        Read in A's own heatmap, the cell c the evidence comes from does not warm its own
        landing place: evidence cannot contradict itself (2026-11-12: a queen's diagonals seen
        to 5 squares were vetoed from going on, 4.625 against 4.605, by the heat of their own
        last cells — RESULTS.md § 25)."""
        tries = hits = 0
        heat = 0.0
        own = A.source == B.source
        for c in A.norm:
            y = t(c)
            if y is None or not self._inside(y) or (own and y == c):
                continue
            tries += 1
            if y in B.norm:
                hits += 1
            else:
                heat += self._warmth(B, y, c if own else None)
        return hits, tries, heat

    def _warmth(self, B, y, skip=None) -> float:
        """B's heat at y: the mean mass of its cells around y (the kernel), y and ``skip`` (the
        cell the evidence comes from) excluded."""
        n = len(y)
        offs = self.__dict__.get("_offs")
        if offs is None:
            offs = self._offs = [o for o in product(range(-RADIUS, RADIUS + 1), repeat=n) if any(o)]
        tot = 0
        for o in offs:
            z = tuple(a + b for a, b in zip(y, o))
            if z != skip:
                tot += B.cells.get(z, 0)
        return tot / max(len(offs), 1)

    def _holds(self, hits, tries, B, heat) -> bool:
        return (tries > 0 and hits >= HOLD * tries and heat <= VETO
                and chance_tail(hits, tries, len(B.norm) / self.volume) < CHANCE)

    @staticmethod
    def _sure(hits, tries) -> bool:
        return wilson_low(hits, tries, 1.0) >= HOLD

    def _bridges(self) -> list:
        index = defaultdict(set)  # cell → groups whose norm holds it
        for k, g in enumerate(self.groups):
            for c in g.norm:
                index[c].add(k)
        inv = {t.key: t.inverse() for t in self.transforms}
        out = []
        for A in self.groups:
            for t in self.transforms:
                targets = set()
                for y in map(t, A.norm):
                    if y is not None:
                        targets |= index.get(y, set())
                for k in sorted(targets):
                    B = self.groups[k]
                    own = A.source == B.source
                    if (A is B and t.identity) or (own and A is not B and (t.identity or A.whole or B.whole)):
                        continue  # a fragment is not bridged to its own heatmap's whole
                    if A is not B and t.step and not STEP_ACROSS:
                        continue
                    hits, tries, heat = self._reading(A, t, B)
                    if not self._holds(hits, tries, B, heat):
                        continue
                    br = Bridge(A, t, B, hits, tries)
                    u = inv[t.key]
                    bh, bt, bheat = self._reading(B, u, A)
                    if self._holds(bh, bt, A, bheat) and (self._sure(hits, tries) or self._sure(bh, bt)):
                        br.back = (u, bh, bt)
                    out.append(br)
        return out

    def _close(self) -> None:
        """The union simplified into its transition: each side holds the other seen through it,
        transitively, inside the space's bounds (what a heatmap holds is shared by all its groups)."""
        unions = [b for b in self.bridges if b.union]
        changed = True
        while changed:
            changed = False
            for b in unions:
                for src, t, dst in ((b.a, b.t, b.b), (b.b, b.back[0], b.a)):
                    have = self.cells(dst.source)
                    for c in self._shape(src):
                        y = t(c)
                        if y is not None and y not in have and self._inside(y):
                            dst.implied.add(y)
                            have.add(y)
                            changed = True

    def _shape(self, g) -> set:
        """What a transition carries from a group: its norm and what its heatmap is implied to
        hold (all of it for a whole heatmap; around a concentration, only what touches it)."""
        imp = set().union(*(x.implied for x in self.groups if x.source == g.source))
        if g.whole:
            return g.norm | imp
        return g.norm | g.implied

    def _metas(self) -> list:
        """Intersections of concentrations of different heatmaps (≥ 2 shared cells), grown to
        ``ARITY`` members; one meta molette per distinct intersection (its fewest members)."""
        ms = self.molettes
        index = defaultdict(set)
        for k, m in enumerate(ms):
            for c in m.cells:
                index[c].add(k)
        found: dict = {}
        frontier = []
        for i, A in enumerate(ms):
            others = set().union(*(index[c] for c in A.cells)) - {i}
            for j in sorted(others):
                if j > i and ms[j].source != A.source:
                    common = set(A.cells) & set(ms[j].cells)
                    if len(common) >= 2:
                        frontier.append(((i, j), frozenset(common)))
        for _arity in range(2, ARITY + 1):
            nxt = []
            for members, common in frontier:
                if common not in found or len(found[common]) > len(members):
                    found[common] = members
                if len(members) == ARITY:
                    continue
                srcs = {ms[k].source for k in members}
                cand = set().union(*(index[c] for c in common)) - set(members)
                for k in sorted(cand):
                    if k > max(members) and ms[k].source not in srcs:
                        both = common & ms[k].cells.keys()
                        if len(both) >= 2:
                            nxt.append((members + (k,), frozenset(both)))
            frontier = nxt
        out = []
        for common, members in found.items():
            mm = tuple(ms[k] for k in members)
            out.append(Meta(mm, {c: min(m.cells[c] for m in mm) for c in common}))
        out.sort(key=lambda m: (-len(m.cells), -sum(m.cells.values())))
        return out

    # ------------------------------------------------------------ reading the layer
    def cells(self, name) -> set:
        """Everything the heatmap ``name`` holds: seen, and implied by its transitions."""
        return set().union(*(g.all() for g in self.groups if g.source == name)) if name in self.heatmaps else set()

    def implied(self, name) -> set:
        return self.cells(name) - set(self.heatmaps.get(name, ()))

    def transition_heatmaps(self) -> dict:
        """Each concentration's transition heatmap: mass on the transformations that carry it
        (by their hits), the unions only."""
        out: dict = {}
        for b in self.bridges:
            if b.union:
                h = out.setdefault((b.a.source, "whole" if b.a.whole else min(b.a.cells)), {})
                h[b.t.key] = h.get(b.t.key, 0) + b.hits
        return out

    def symmetries(self, name) -> list:
        """The transformations that carry the heatmap ``name`` onto itself (unions within it):
        the type of the dynamic."""
        names = {t.key: t.name for t in self.transforms}
        keys = {b.t.key for b in self.bridges if b.union and b.a.source == name == b.b.source}
        return [names[k] for k in sorted(keys)]

    def types(self) -> dict:
        """The layer's transition heatmap: every transformation by the evidence it carried."""
        tot: dict = defaultdict(float)
        names = {t.key: t.name for t in self.transforms}
        for b in self.bridges:
            if b.union:
                tot[names[b.t.key]] += b.hits
        return dict(sorted(tot.items(), key=lambda x: -x[1]))

    def above(self) -> "Layer":
        """The degree above: the transition heatmaps as heatmaps, transformed by conjugation."""
        base = [t for t in self.transforms if isinstance(t, Transform) and not t.step]
        return Layer(self.transition_heatmaps(), [Conjugation(s) for s in base], None, self.degree + 1)
