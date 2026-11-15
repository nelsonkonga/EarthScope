"""The shape of a numeric watcher read along an axis — Eva as a curve approximator (2026-11-13).

The user (2026-11-13): « fais qu'Eva devienne un approximateur de courbe : plus on lui donne de
points, plus sa dynamique épouse la forme de la courbe » — « elle doit découvrir les dynamiques,
les méta dynamiques (intersection) et les transitions de dynamique (union) ; l'intersection est
analogue à la différence (différentiel) et l'union à l'intégration » — « elle doit prédire là où il
y a 0 point, en créant sa part de points à partir de ce qui existe » — « les grands niveaux de méta
molettes combinés aux molettes de transition, qui ont aussi leurs méta molettes, auraient dû rendre
le bruit inutile » — then: « on devrait combiner l'union et l'intersection » and « il faut
généraliser pour que les méta molettes et molettes de transition de degré N se créent
dynamiquement au besoin ».

Then, on the grid: « les méta molettes à N degrés, ce sont les intersections, des intersections,
des intersections encore jusqu'à degré N — un axe vertical ; sur l'axe horizontal, les molettes de
transition à N degrés : l'union des unions, des unions encore ; entre les deux plans, des
intersections d'unions, des unions d'intersections » — the cells existing where needed — and « il
faut aussi traiter les intersections de transitions de dynamiques ».

Readings ``(place, value)`` arrive in any order; nothing tells Eva what they are. They are placed on
a lattice (both coordinates read on the span they cover, positions in cells, not rounded), the
finest at which neighbouring readings along the axis still warm each other (Chebyshev ≤ 2·RADIUS).

The grid of molettes
    Vertical — meta molettes of degree k, k intersections. The readings intersected with themselves
    shifted by a change v hold the pairs that differ by v: f(x + Δx) − f(x) = Δy. The norm of all
    the differences of a dynamic (each pair weighted by Δx²) is its differential (degree 1); the
    intersection of that intersection, the differences of the differentials, is degree 2 (f''); and
    so on up to degree N.
    Horizontal — transition molettes, unions of unions: level j joins two neighbouring molettes of
    level j − 1 (2, 4, 8… readings; overlapping by half, so that no boundary is privileged). A union
    always exists; its verdict (``judge``) is what its two halves say of each other.
    Between the planes — every union carries the intersections it needs (intersections of a union:
    the differential of a long stretch, where the noise is already averaged), and the halves of a
    union are judged on all of them where they meet (unions of intersections).

The verdict of a union starts at the degree its halves already hold (a line: value and differential):
    - each half's norm — its value and every intersection it carries — lies within the other's: it
      *holds*, one dynamic, the integral of the two;
    - they differ beyond chance (CHANCE, Bonferroni over the tests): the next degree is read — a meta
      molette of one more intersection — created only on positive evidence: the union proves its new
      terms, its readings stay within the noise, and it truly simplifies its two halves (fewer
      numbers than they need, ``_simplifies``). A degree is created only where it is needed;
    - no degree reconciles them: it *breaks*, a transition between dynamics;
    - one half has no direction yet (still a point): *undecided*, and the level above is read anyway.
    The uncertainty of a norm is the ordinary noise over what so many readings can pin down; it
    shrinks as 1/√n, and high levels see through the noise. The noise is measured where it is: around
    her dynamics, persistence included (``_persistent_noise``, ROUNDS). Each reading is answered by
    the highest union holding it before a proven transition.

Every molette is kept as sums of its readings' powers in its own frame (centred on its span, scaled
to it): two halves join by adding their sums, re-expressed in the frame of the union; when a higher
degree is needed, the sums are extended from its readings.

Transitions of dynamics, and their intersections
    Each transition between two consecutive dynamics is read as a reading (``transitions``): where
    they meet, how much each intersection jumps there, its kind (the lowest one that jumps beyond
    chance) and the intersections above it that go on across (the dynamics it is linked to). The
    transitions of one kind, intersected with themselves shifted by 1, 2… (``meta``), have a dynamic
    of their own where they meet themselves, proven by two such pairs: it foresees the transitions
    she has not seen (``foreseen``).

Where there are no readings (a gap out of the norm of the gaps, before the first, after the last),
she creates her own points, one per ordinary step. When one dynamic holds both sides of a void and no
regular transition lies in it, its union across it is the integral: the points are its own.
Otherwise (a transition in the void, before the first reading, after the last) each one comes from
the one before: forward from one side, backward from the other (transitions read both ways), blended
across the void; the change of slope from the proven cells of (value, slope), else from the
transition between the dynamics on both sides; crossing a regular transition (seen or foreseen),
value, differential and its differential jump as they do there. ``draw`` integrates her dynamic
alone from the first reading.
"""

from __future__ import annotations

import math
from bisect import bisect_right
from math import comb

from statistics import NormalDist

from .heatmaps import CHANCE, HOLD, RADIUS, Z


def z_chance(tests: int = 1, among: int = 1) -> float:
    """How far apart, in spreads, two norms must be for chance to put them there less often than
    CHANCE — two-sided, over ``tests`` tests at each of ``among`` places (Bonferroni)."""
    return NormalDist().inv_cdf(1 - CHANCE / (2 * tests * max(1, among)))


BREAK = z_chance(2)  # the transition between two lines: value and differential (2.81 spreads)
ROUNDS = 1  # readings again with the noise found around the dynamics (persistence); more rounds cost the
#   curves read from few points (RESULTS § 27: 2 rounds, sine at 32 points 17.6 → 21.7 %)
K0 = 2  # degrees every meta molette's sums hold from the start; more are added where a degree is needed
COND = 1e10  # a degree the sums cannot pin down any more (condition number): a limit of the numbers, not of the curve


def chance_tail(k: int, n: int, p: float) -> float:
    """P(at least k of n land by chance on a share p of the space) — eva.heatmaps.chance_tail, in
    logarithms so that long dynamics (thousands of changes) do not overflow."""
    if k <= 0:
        return 1.0
    p = min(max(p, 1e-12), 1.0)
    if p >= 1.0:
        return 1.0
    lp, lq = math.log(p), math.log1p(-p)
    terms = [math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1) + i * lp + (n - i) * lq
             for i in range(k, n + 1)]
    m = max(terms)
    return math.exp(m) * sum(math.exp(t - m) for t in terms)


# ------------------------------------------- small exact arithmetic (mirrored in checks/curve_shape.js)
def _powers(v: float, k: int) -> list[float]:
    """1, v, v², … v^k by repeated products (the same numbers in every language)."""
    out = [1.0]
    for _ in range(k):
        out.append(out[-1] * v)
    return out


def _falling(k: int, j: int) -> float:
    """k (k − 1) … (k − j + 1): what the j-th derivative leaves of the power k."""
    out = 1.0
    for i in range(j):
        out *= k - i
    return out


def _reframe(sums: list[float], a: float, b: float) -> list[float]:
    """Sums Σ u^k (or Σ u^k·y) re-expressed in a frame where v = a·u + b:
    Σ v^k = Σ_j C(k, j) a^j b^(k−j) Σ u^j."""
    K = len(sums) - 1
    pa, pb = _powers(a, K), _powers(b, K)
    out = []
    for k in range(K + 1):
        acc = 0.0
        for j in range(k + 1):
            acc += comb(k, j) * pa[j] * pb[k - j] * sums[j]
        out.append(acc)
    return out


def _invert(A: list[list[float]]):
    """The inverse of a small symmetric matrix (Gauss–Jordan, partial pivoting), or None when it
    cannot be pinned down (singular, or its condition number beyond COND)."""
    n = len(A)
    M = [list(A[i]) + [1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    for c in range(n):
        p = c
        for r in range(c + 1, n):
            if abs(M[r][c]) > abs(M[p][c]):
                p = r
        if M[p][c] == 0.0:
            return None
        M[c], M[p] = M[p], M[c]
        piv = M[c][c]
        M[c] = [v / piv for v in M[c]]
        for r in range(n):
            f = M[r][c]
            if r != c and f != 0.0:
                M[r] = [x - f * y for x, y in zip(M[r], M[c])]
    inv = [row[n:] for row in M]
    na = ni = 0.0
    for i in range(n):
        ra = ri = 0.0
        for j in range(n):
            ra += abs(A[i][j])
            ri += abs(inv[i][j])
        na, ni = max(na, ra), max(ni, ri)
    return inv if na * ni <= COND else None


class Piece:
    """Readings ``lo``..``hi`` (indices along the axis) read as one dynamic, from the sums of their
    powers in its own frame (v = (x − centre) / half-span, so |v| ≤ 1): Σ v^k up to 2K and Σ v^k·y
    up to K, K the degrees its sums hold. Two halves join by adding their sums re-expressed in the
    frame of the union. ``deg`` is the degree it is read at, ``state`` its verdict as a meta
    molette over its two halves ("holds", "breaks" or "undecided")."""

    __slots__ = ("lo", "hi", "xa", "xb", "M", "Y", "deg", "state", "fits")

    def __init__(self, lo, hi, xa, xb, M, Y):
        self.lo, self.hi, self.xa, self.xb, self.M, self.Y = lo, hi, xa, xb, M, Y
        self.deg = 0
        self.state = None
        self.fits = {}

    @classmethod
    def reading(cls, i, x, y):
        return cls(i, i, x, x, [1.0] + [0.0] * (2 * K0), [y] + [0.0] * K0)

    @property
    def c(self) -> float:
        return (self.xa + self.xb) / 2

    @property
    def h(self) -> float:
        return (self.xb - self.xa) / 2 or 1.0

    @property
    def cap(self) -> int:
        return len(self.Y) - 1

    def join(self, other) -> "Piece":
        a, b = self, other
        J = Piece(a.lo, b.hi, a.xa, b.xb, None, None)
        K = min(a.cap, b.cap)
        c, h = J.c, J.h
        ma = _reframe(a.M[:2 * K + 1], a.h / h, (a.c - c) / h)
        mb = _reframe(b.M[:2 * K + 1], b.h / h, (b.c - c) / h)
        ya = _reframe(a.Y[:K + 1], a.h / h, (a.c - c) / h)
        yb = _reframe(b.Y[:K + 1], b.h / h, (b.c - c) / h)
        J.M = [p + q for p, q in zip(ma, mb)]
        J.Y = [p + q for p, q in zip(ya, yb)]
        return J

    @property
    def n(self) -> float:
        return self.M[0]

    @property
    def size(self) -> int:
        return self.hi - self.lo + 1

    @property
    def Sxx(self) -> float:
        return max(self.M[2] - self.M[1] * self.M[1] / self.M[0], 0.0) * self.h * self.h

    @property
    def mean(self) -> float:
        """Where its readings stand on average along the axis (cells)."""
        return self.c + self.h * self.M[1] / self.M[0]


class Shape:
    """The dynamics of one numeric watcher read along an axis, and the curve they draw."""

    def __init__(self, points, grain: float | None = None, degree: int | None = None):
        """``degree``: the highest degree read — the level of the question asked (a trend per decade:
        1); by default none, every degree is created where it is needed."""
        self.max_degree = degree
        pts = sorted((float(x), float(y)) for x, y in points)
        if len(pts) < 2:
            raise ValueError("at least two readings")
        self.xs = [p[0] for p in pts]
        self.ys = [p[1] for p in pts]
        self.x0, self.y0 = self.xs[0], min(self.ys)
        self.sx = (self.xs[-1] - self.xs[0]) or 1.0
        self.sy = (max(self.ys) - self.y0) or 1.0
        xn = [(x - self.x0) / self.sx for x in self.xs]
        yn = [(y - self.y0) / self.sy for y in self.ys]
        self.grain = grain or self._grain(xn, yn)
        g = self.grain
        # positions in cells, not rounded to them: the grain sets how far the kernel warms (what
        # "near" means), it does not move the readings
        self.cx = [v / g for v in xn]
        self.cy = [v / g for v in yn]
        self.rows = int(1 / g) + 1
        self.noise = self._noise()
        self.best = self._levels()  # each reading's meta molette: the highest holding it
        n = len(self.xs)
        self.fit = self._fits()
        # what remains around her dynamics, and how persistent it is: a reading that resembles the
        # one before beyond what the dynamics explain means fewer independent readings than there
        # seem — the noise is measured where it is, and the levels are read again with it
        self.persistence = 0.0
        for _ in range(ROUNDS):  # read again while the noise found keeps growing (a first reading that
            sd = self._persistent_noise()  # follows the noise leaves too little around it)
            if sd <= self.noise * 1.01:
                break
            self.noise = sd
            self.best = self._levels()
            self.fit = self._fits()
        self.pieces = self._segments()
        # the dynamic answering each reading carries its differential and its transitions. An undecided
        # meta molette is still a reading of the dynamic there, unless a void lies inside it (nothing
        # there joins its two sides); a reading still a point, or held only across a void, takes the
        # dynamic of the nearest reading along the axis that has one — on its own side of the void
        gaps = self.vgaps = self._proven_voids()
        proven = [self.directed(W) and (W.state == "holds" or gaps[W.hi] == gaps[W.lo]) for W in self.best]
        before, after, last = [None] * n, [None] * n, None
        for i in range(n):
            last = i if proven[i] else last
            before[i] = last
        last = None
        for i in range(n - 1, -1, -1):
            last = i if proven[i] else last
            after[i] = last
        first = next((W for W in self.best if self.directed(W)), None)
        self.answer = []
        for i in range(n):
            a, b = before[i], after[i]
            if proven[i]:
                j = i
            elif a is None or (b is not None and self.xs[b] - self.xs[i] < self.xs[i] - self.xs[a]):
                j = b
            else:
                j = a
            W = self.best[j] if j is not None else self.best[i]
            self.answer.append(W if self.directed(W) or first is None else first)
        # the molettes active at a reading are the unions holding it: inside, the highest answers (what
        # it reads: bias matters); at the two ends, from which she carries the dynamic into what she has
        # not seen, the surest of them answers (what it carries: certainty matters; the edge of a union
        # of high degree is where it is least known)
        for i in (0, n - 1):
            if self.active[i]:
                self.answer[i] = min(self.active[i], key=lambda W, i=i: self._pin(W, i))
        self.slopes = [self.slope(self.answer[i], self.xs[i]) for i in range(n)]
        self.carry = list(self.slopes)
        self.curv = [self.curvature(self.answer[i], self.xs[i]) for i in range(n)]
        self.degrees = [self.read_degree(W) if self.directed(W) else 0 for W in self.answer]
        self.qs = [(W.lo, W.hi) if self.directed(W) else None for W in self.answer]
        self.samples = self._sightings()
        self._field()
        # the transitions between her dynamics, read as readings, and their own meta molettes
        self.transitions = self._dynamic_transitions()
        self.meta = self._meta_transitions()

    # ------------------------------------------------------------------ the lattice
    @staticmethod
    def _grain(xn, yn) -> float:
        """The finest lattice at which neighbouring readings along the axis still warm each other
        (median Chebyshev distance ≤ 2·RADIUS cells)."""
        best = 0.5
        for k in range(1, 15):
            g = 2.0 ** -k
            d = sorted(max(abs(math.floor(xn[i + 1] / g) - math.floor(xn[i] / g)),
                           abs(math.floor(yn[i + 1] / g) - math.floor(yn[i] / g))) for i in range(len(xn) - 1))
            if d[len(d) // 2] > 2 * RADIUS:
                break
            best = g
        return best

    def spacing(self) -> float:
        """The ordinary step between neighbouring readings (median)."""
        d = sorted(b - a for a, b in zip(self.xs, self.xs[1:]) if b > a)
        return d[len(d) // 2] if d else self.sx

    def _proven_voids(self) -> list[int]:
        """Proven voids, counted along the readings (prefix sums): a gap chance would leave less often
        than CHANCE among all the gaps, were the readings at random places along the axis —
        (n − 1)·(1 − g/L)^(n − 1) < CHANCE. Ordinary large gaps (random places leave many) are not."""
        n, L = len(self.xs), self.xs[-1] - self.xs[0]
        out = [0]
        for i in range(n - 1):
            g = (self.xs[i + 1] - self.xs[i]) / L if L > 0 else 0.0
            hole = 0
            if 0 < g < 1:
                q, k = 1.0 - g, n - 1
                pk = 1.0
                for _ in range(k):
                    pk *= q
                hole = 1 if k * pk < CHANCE else 0
            out.append(out[-1] + hole)
        return out

    def void(self) -> float:
        """A void: a gap between neighbouring readings out of the norm of the gaps (beyond Z
        spreads) — readings at random places leave gaps of every size, most of them ordinary."""
        d = [b - a for a, b in zip(self.xs, self.xs[1:])]
        if not d:
            return self.sx
        mu = sum(d) / len(d)
        sd = math.sqrt(sum((v - mu) ** 2 for v in d) / len(d))
        return mu + Z * sd

    # ------------------------------------------- intersections, unions, their levels
    def _noise(self) -> float:
        """The spread every dynamic has at least, in cells: the ordinary departure of a reading from
        the line joining its two neighbours (the median departure, read as a spread: × 1.4826, ÷ √1.5
        for what one reading's noise makes of it), and never less than the kernel (half a cell): what
        is ordinary in the readings themselves."""
        cx, cy = self.cx, self.cy
        ds = []
        for i in range(1, len(cx) - 1):
            span = cx[i + 1] - cx[i - 1]
            if span <= 0:
                continue
            t = (cx[i] - cx[i - 1]) / span
            ds.append(abs(cy[i] - (cy[i - 1] + t * (cy[i + 1] - cy[i - 1]))))
        if not ds:
            return RADIUS / 2
        ds.sort()
        sigma = 1.4826 * ds[len(ds) // 2] / math.sqrt(1.5)  # the ordinary departure (median), as a spread
        return max(sigma, RADIUS / 2)

    def _grow(self, P: Piece, K: int) -> None:
        """P's sums extended to K degrees, from its readings (in its own frame)."""
        c, h = P.c, P.h
        M, Y = [0.0] * (2 * K + 1), [0.0] * (K + 1)
        for i in range(P.lo, P.hi + 1):
            pw = _powers((self.cx[i] - c) / h, 2 * K)
            for k in range(2 * K + 1):
                M[k] += pw[k]
            for k in range(K + 1):
                Y[k] += pw[k] * self.cy[i]
        P.M, P.Y = M, Y

    def _fit(self, P: Piece, d: int):
        """P read at degree d: its coefficients (in its frame) and what pins them down (the inverse of
        its sums), or None when its readings cannot fix that many (fewer than d + 1, or the numbers
        give up)."""
        if d in P.fits:
            return P.fits[d]
        f = None
        if P.n >= d + 1:
            if P.cap < d:
                self._grow(P, d)
            Gi = _invert([[P.M[i + j] for j in range(d + 1)] for i in range(d + 1)])
            if Gi is not None:
                coef = []
                for i in range(d + 1):
                    acc = 0.0
                    for j in range(d + 1):
                        acc += Gi[i][j] * P.Y[j]
                    coef.append(acc)
                f = (coef, Gi)
        P.fits[d] = f
        return f

    def _basis(self, P: Piece, x: float, j: int, d: int) -> list[float]:
        """What the j-th derivative at x (cells) takes from each of P's d + 1 coefficients."""
        h = P.h
        pw = _powers((x - P.c) / h, d)
        hj = 1.0
        for _ in range(j):
            hj *= h
        return [0.0 if k < j else _falling(k, j) * pw[k - j] / hj for k in range(d + 1)]

    def _deriv(self, P: Piece, x: float, j: int, d: int) -> float:
        """P's j-th derivative at x (cells), read at degree d (0: its value)."""
        coef = self._fit(P, d)[0]
        g = self._basis(P, x, j, d)
        acc = 0.0
        for k in range(d + 1):
            acc += coef[k] * g[k]
        return acc

    def _var(self, P: Piece, x: float, j: int, d: int) -> float:
        """How uncertain P's j-th derivative at x is, per unit of noise² (what its readings pin down)."""
        Gi = self._fit(P, d)[1]
        g = self._basis(P, x, j, d)
        acc = 0.0
        for a in range(d + 1):
            for b in range(d + 1):
                acc += g[a] * Gi[a][b] * g[b]
        return acc

    @staticmethod
    def _held(P: Piece) -> int:
        """The degree a meta molette already holds (a line, at least, once it has a direction)."""
        return max(1, P.deg) if P.state != "breaks" else 1

    def judge(self, A: Piece, B: Piece, U: Piece | None = None, among: int = 1) -> tuple[str, int]:
        """What two neighbouring dynamics say of each other, union and intersection together, from the
        degree they already hold: where they meet, each one's value, differential and transitions lie
        within the other's norm; the union reads their readings as well as they do themselves; its
        readings lie within the ordinary noise — chance would break any of these less often than
        CHANCE (Bonferroni over the tests and the ``among`` places judged alike). If not, the next
        degree is read: a meta molette of one more intersection, created only if the union proves it
        (its new terms out of the norm of chance) and truly simplifies its halves (``_simplifies``).
        A union describes its halves with fewer numbers than they need, or it is a transition.
        Returns (verdict, degree)."""
        start = max(self._held(A), self._held(B))
        if not (self.directed(A) and self.directed(B)):
            return "undecided", start
        U = U if U is not None else A.join(B)
        ha, hb = self._held_degree(A), self._held_degree(B)
        start = max(ha, hb)
        xm = (self.cx[A.hi] + self.cx[B.lo]) / 2
        d = start
        while True:
            # a union simplifies its two halves: fewer numbers than the two of them (d + 1 against
            # ha + hb + 2), or it is not a union — a transition between two dynamics
            k = ha + hb + 1 - d
            if (k < 1 or (self.max_degree is not None and d > self.max_degree)
                    or self._fit(A, d) is None or self._fit(B, d) is None or self._fit(U, d) is None):
                return "breaks", start  # no degree its readings can pin down (or the question asks) reconciles them
            zmax = 0.0  # where the halves meet: each one's value, differential and transitions in the other's norm
            for j in range(d + 1):
                se = self.noise * math.sqrt(self._var(A, xm, j, d) + self._var(B, xm, j, d))
                dz = abs(self._deriv(A, xm, j, d) - self._deriv(B, xm, j, d))
                zmax = max(zmax, dz / se if se > 0 else (math.inf if dz > 0 else 0.0))
            if d == start == 1:
                # two lines whose norms agree where they meet (value and differential) are one line
                if zmax <= z_chance(d + 1, among):
                    return "holds", d
            elif d == start:
                # two curved dynamics may agree where they meet and still not be one (alike halves of a
                # pattern that repeats): the union must also read its readings within the noise
                tests = d + 2
                one = NormalDist().inv_cdf(1 - CHANCE / (tests * max(1, among)))
                if zmax <= z_chance(tests, among) and self._chance_left(self._rss(U, d), U.n - (d + 1), one):
                    return "holds", d
            else:
                # a new degree is created only on positive evidence (one family, Bonferroni: the d + 1
                # norms where they meet, and the union's readings within the ordinary noise): the union
                # proves its new terms and truly simplifies its halves (``_simplifies``)
                tests = d + 2
                one = NormalDist().inv_cdf(1 - CHANCE / (tests * max(1, among)))
                ru, ra, rb = self._rss(U, d), self._rss(A, ha), self._rss(B, hb)
                if (zmax <= z_chance(tests, among) and self._simplifies(ru - ra - rb, k, U.n)
                        and self._proven(U, start, d, among) and self._chance_left(ru, U.n - (d + 1), one)):
                    return "holds", d
            d += 1

    def _simplifies(self, extra: float, k: int, n: float) -> bool:
        """Is the union worth the k numbers it saves on its two halves: what it reads worse than they do
        (``extra``, a sum of squares) is no more than ln(n) of noise² per number saved — the price of a
        number among n readings (Schwarz's criterion, BIC). Creating a degree needs this positive
        evidence; where a bend and a break read alike, the break stays."""
        return max(extra, 0.0) / (self.noise * self.noise) <= k * math.log(n)

    def _held_degree(self, P: Piece) -> int:
        """The degree P holds, lowered to one its readings can pin down."""
        d = self._held(P)
        while d > 1 and self._fit(P, d) is None:
            d -= 1
        return d

    def _rss(self, P: Piece, d: int) -> float:
        """What remains of P's readings around its norm at degree d (sum of squares, cells²)."""
        key = -1 - d  # kept beside its fits
        if key in P.fits:
            return P.fits[key]
        coef = self._fit(P, d)[0]
        c, h = P.c, P.h
        rss = 0.0
        for i in range(P.lo, P.hi + 1):
            pw = _powers((self.cx[i] - c) / h, d)
            f = 0.0
            for j in range(d + 1):
                f += coef[j] * pw[j]
            e = self.cy[i] - f
            rss += e * e
        P.fits[key] = rss
        return rss

    def _chance_left(self, ss: float, k: float, z: float) -> bool:
        """Is a sum of squares over k independent readings' worth no more than the ordinary noise
        leaves by chance (χ²_k read as a normal: Wilson–Hilferty, one-sided threshold z)?"""
        if k < 1:
            return True
        x = max(ss, 0.0) / (self.noise * self.noise) / k
        w = 2 / (9 * k)
        return (x ** (1 / 3) - (1 - w)) / math.sqrt(w) <= z

    def _proven(self, U: Piece, start: int, d: int, among: int) -> bool:
        """Does the union need the degrees above ``start``: is one of its new terms out of what chance
        gives it (Bonferroni over them)?"""
        f = self._fit(U, d)
        if f is None:
            return False
        coef, Gi = f
        z = z_chance(d - start, among)
        for j in range(start + 1, d + 1):
            se = self.noise * math.sqrt(max(Gi[j][j], 0.0))
            if se > 0 and abs(coef[j]) / se > z:
                return True
        return False

    def verdict(self, A: Piece, B: Piece) -> str:
        return self.judge(A, B)[0]

    def directed(self, P: Piece) -> bool:
        """A dynamic has a direction only once its readings span at least one cell along the axis;
        before that it is still a point, as a reading alone."""
        return P.n >= 2 and P.Sxx > 0 and self.cx[P.hi] - self.cx[P.lo] >= RADIUS

    def _levels(self) -> list[Piece]:
        """Levels of meta molettes: each joins two neighbouring ones of the level below (overlapping
        by half) and is judged by what its halves say of each other. Each reading keeps the highest
        meta molette holding it (a holding one first, else an undecided one, the most central)
        until every one around it breaks: a proven transition."""
        n = len(self.xs)
        prev = {i: Piece.reading(i, self.cx[i], self.cy[i]) for i in range(n)}
        self.readings = dict(prev)
        best = [prev[i] for i in range(n)]
        alive = [True] * n
        self.levels = 0
        # the molettes active at each reading: every union that holds it, at every level
        self.active = [[] for _ in range(n)]
        s = 2
        while s // 2 < n and any(alive):
            half = s // 2
            stride = max(1, half)
            cur = {}
            for lo in range(0, n, stride):
                A, B = prev.get(lo), prev.get(lo + half)
                if A is None or B is None:
                    continue
                W = A.join(B)
                W.state, W.deg = self.judge(A, B, W)
                cur[lo] = W
            if not cur:
                break
            self.levels += 1
            for i in range(n):
                if not alive[i]:
                    continue
                k = i // stride
                cands = [cur[lo] for lo in {k * stride, (k - 1) * stride} if lo in cur and lo <= i <= cur[lo].hi]
                if not cands:
                    continue
                order = sorted(cands, key=lambda W: (abs((W.lo + W.hi) / 2 - i), W.lo))
                if all(W.state == "breaks" for W in order):
                    alive[i] = False  # every meta molette around it breaks: a transition
                    continue
                held = ([W for W in order if W.state == "holds" and self.directed(W)]
                        or [W for W in order if W.state == "undecided" and self.directed(W)])
                # else still a point: the level above is read; the higher answers it, but an undecided meta
                # molette never replaces one that holds (nothing proves its union)
                if held and (not self.directed(best[i]) or held[0].state == "holds" or best[i].state != "holds"):
                    best[i] = held[0]
                for W in order:
                    if W.state == "holds" and self.directed(W):
                        self.active[i].append(W)
            prev = cur
            s *= 2
        return best

    def _pin(self, W: Piece, i: int) -> float:
        """How uncertain W's differential is at reading i (per unit of noise²)."""
        return self._var(W, self.cx[i], 1, self.read_degree(W))

    def _fits(self) -> list[float]:
        """Each reading's value: of the molettes active there, the highest union holding it (a point
        is its own value)."""
        return [self.line(self.best[i], self.xs[i]) for i in range(len(self.xs))]

    def _span(self, lo, hi) -> Piece:
        """A new piece holding readings lo..hi (the readings themselves are never changed)."""
        R = self.readings[lo]
        P = Piece(lo, lo, R.xa, R.xb, list(R.M), list(R.Y))
        for i in range(lo + 1, hi + 1):
            P = P.join(self.readings[i])
        return P

    def _persistent_noise(self) -> float:
        """The spread of the readings around her dynamics, in cells, as many independent readings
        would show it: × √((1 + φ) / (1 − φ)), φ the lag-1 correlation of what remains (its
        small-sample bias corrected: + (1 + 3φ) / n), at least 0 and at most 0.95."""
        n = len(self.xs)
        if n < 4:
            return 0.0
        # around her dynamics (the highest union holding each reading), not around each reading's surest
        # answer: a small union near a reading follows its noise
        dyn = [self.line(self.best[i], self.xs[i]) for i in range(n)]
        r = [self.cy[i] - (dyn[i] - self.y0) / self.sy / self.grain for i in range(n)]
        mu = sum(r) / n
        r = [v - mu for v in r]
        ss = sum(v * v for v in r)
        if ss <= 0:
            return 0.0
        phi = sum(a * b for a, b in zip(r, r[1:])) / ss
        phi = min(max(phi + (1 + 3 * phi) / n, 0.0), 0.95)
        self.persistence = phi
        return math.sqrt(ss / (n - 1)) * math.sqrt((1 + phi) / (1 - phi))

    def _segments(self) -> list[Piece]:
        """The dynamics: consecutive readings answered by the same meta molette (read at its degree),
        joined to the next ones while their union holds; where it breaks, a transition."""
        n = len(self.xs)
        groups, lo = [], 0
        for i in range(1, n + 1):
            if i == n or self.best[i] is not self.best[lo]:
                groups.append((lo, i - 1))
                lo = i
        # each boundary between groups is one test among them all: a transition is proven when
        # chance would put the two norms that far apart less often than CHANCE over all of them
        among = max(1, len(groups) - 1)
        out = []
        for a, b in groups:
            G = self._span(a, b)
            W = self.best[a]
            G.state, G.deg = "holds", (self._held(W) if self.directed(W) else 1)
            if out:
                verdict, d = self.judge(out[-1], G, None, among)
                if verdict != "breaks":
                    J = out[-1].join(G)
                    J.state, J.deg = "holds", d
                    out[-1] = J
                    continue
            out.append(G)
        return out

    # --------------------------------------------------------- in the readings' units
    def read_degree(self, P: Piece) -> int:
        """The degree P is read at: its own, or the highest below it its readings can pin down."""
        d = max(1, P.deg)
        while d > 1 and self._fit(P, d) is None:
            d -= 1
        return d

    def _col(self, x: float) -> float:
        return (x - self.x0) / self.sx / self.grain

    def line(self, P: Piece, x: float) -> float:
        """Where the dynamic P stands at x (its norm: its readings carried along its differential
        and its transitions)."""
        if not self.directed(P):
            return P.Y[0] / P.M[0] * self.grain * self.sy + self.y0
        return self.y0 + self._deriv(P, self._col(x), 0, self.read_degree(P)) * self.grain * self.sy

    def slope(self, P: Piece, x: float | None = None) -> float:
        """P's differential at x (by default where its readings stand on average)."""
        if not self.directed(P):
            return 0.0
        col = P.mean if x is None else self._col(x)
        return self._deriv(P, col, 1, self.read_degree(P)) * self.sy / self.sx

    def curvature(self, P: Piece, x: float) -> float:
        """P's transition at x (f''): 0 for a dynamic read as a line."""
        if not self.directed(P):
            return 0.0
        d = self.read_degree(P)
        if d < 2:
            return 0.0
        return self._deriv(P, self._col(x), 2, d) * self.sy / (self.sx * self.sx * self.grain)

    # ------------------------------------------- transitions of dynamics, and their meta molettes
    def derivative(self, P: Piece, x: float, k: int) -> float:
        """P's k-th intersection at x — 0: its value, 1: its differential, 2: the differential of its
        differential… — in the readings' units (0 above the degree it is read at)."""
        if not self.directed(P):
            return P.Y[0] / P.M[0] * self.grain * self.sy + self.y0 if k == 0 else 0.0
        d = self.read_degree(P)
        if k > d:
            return 0.0
        v = self._deriv(P, self._col(x), k, d)
        return self.y0 + v * self.grain * self.sy if k == 0 else v * self._unit(k)

    def _spread(self, P: Piece, x: float, k: int) -> float:
        """How uncertain P's k-th intersection at x is, in the readings' units."""
        if not self.directed(P):
            return self.noise * self.grain * self.sy if k == 0 else 0.0
        d = self.read_degree(P)
        if k > d:
            return 0.0
        e = self.noise * math.sqrt(max(self._var(P, self._col(x), k, d), 0.0))
        return e * self.grain * self.sy if k == 0 else e * self._unit(k)

    def _unit(self, k: int) -> float:
        """From cells to the readings' units for a k-th intersection: sy / (sx^k · grain^(k − 1))."""
        sxk, gk = 1.0, 1.0
        for _ in range(k):
            sxk *= self.sx
        for _ in range(k - 1):
            gk *= self.grain
        return self.sy / (sxk * gk)

    def meeting(self, A: Piece, B: Piece, steps: int = 200) -> float:
        """Where two dynamics meet (the union is the integral): of the places where they cross between
        their readings, the nearest to the boundary between them; else that boundary."""
        lo, hi = self.xs[A.lo], self.xs[B.hi]
        mid = (self.xs[A.hi] + self.xs[B.lo]) / 2
        ts = [lo + (hi - lo) * k / steps for k in range(steps + 1)]
        ds = [self.line(A, t) - self.line(B, t) for t in ts]
        best = None
        for i in range(steps):
            t0, t1, d0, d1 = ts[i], ts[i + 1], ds[i], ds[i + 1]
            if d0 == 0.0:
                c = t0
            elif d0 * d1 < 0:
                for _ in range(60):  # halve the bracket until it is a point
                    tm = (t0 + t1) / 2
                    dm = self.line(A, tm) - self.line(B, tm)
                    if (dm < 0) == (d0 < 0):
                        t0, d0 = tm, dm
                    else:
                        t1 = tm
                c = (t0 + t1) / 2
            else:
                continue
            if best is None or abs(c - mid) < abs(best - mid):
                best = c
        if ds[-1] == 0.0 and (best is None or abs(ts[-1] - mid) < abs(best - mid)):
            best = ts[-1]
        return mid if best is None else best

    def _dynamic_transitions(self) -> list[dict]:
        """Each transition between two consecutive dynamics, read as a reading: where they meet, how
        much each intersection jumps there (value, differential, its differential…) and how sure that
        is; its kind is the lowest one that jumps beyond chance; the ones above it that go on across
        are the dynamics it is linked to."""
        # what is a dynamic of its own: at least the smallest union that can be judged (two directed
        # halves of two readings), longer than the cells that warm each other (2·RADIUS along the
        # axis), no void inside it (nothing there joins its two sides), not lying whole inside one
        # undecided meta molette (its readings are that molette's, across the transition) — else it is
        # part of the transition around it
        gaps = self.vgaps

        def inside(P):  # all its readings answered by one undecided meta molette that holds it whole
            W = self.best[P.lo]
            return (W.state != "holds" and W.lo <= P.lo and P.hi <= W.hi
                    and all(self.best[i] is W for i in range(P.lo, P.hi + 1)))

        ps = [P for P in self.pieces if P.size >= 4 and self.directed(P) and gaps[P.hi] == gaps[P.lo]
              and self.cx[P.hi] - self.cx[P.lo] >= 2 * RADIUS and not inside(P)]
        # two transitions that warm each other (closer than 2·RADIUS cells along the axis) are one: the
        # dynamic between them is part of it
        near = 2 * RADIUS * self.grain * self.sx
        ats = [self.meeting(A, B) for A, B in zip(ps, ps[1:])]
        i = 1
        while i < len(ats):
            if ats[i] - ats[i - 1] < near:
                del ps[i]  # the dynamic between transitions i - 1 and i
                ats[i - 1:i + 1] = [self.meeting(ps[i - 1], ps[i])]
                i = max(1, i - 1)
            else:
                i += 1
        out = [self._transition(A, B, at) for (A, B), at in zip(zip(ps, ps[1:]), ats)]
        # one transition cut in two: a dynamic shorter than half of each of its neighbours, between two
        # transitions, is part of the transition between them (a turn not resolved exactly)
        i = 1
        while i < len(out):
            a, b, P = out[i - 1], out[i], ps[i]
            if (a["kind"] is not None and b["kind"] is not None
                    and 2 * P.size < ps[i - 1].size and 2 * P.size < ps[i + 1].size):
                del ps[i]
                out[i - 1:i + 1] = [self._transition(ps[i - 1], ps[i], self.meeting(ps[i - 1], ps[i]))]
                i = max(1, i - 1)
            else:
                i += 1
        return out

    def _transition(self, A: Piece, B: Piece, at: float) -> dict:
        """The transition from dynamic A to dynamic B, read where they meet."""
        K = max(self.read_degree(A), self.read_degree(B))
        jumps, spreads = [], []
        for k in range(K + 1):
            jumps.append(self.derivative(B, at, k) - self.derivative(A, at, k))
            ea, eb = self._spread(A, at, k), self._spread(B, at, k)
            spreads.append(math.sqrt(ea * ea + eb * eb))
        z = z_chance(K + 1)
        moved = [abs(j) > z * e for j, e in zip(jumps, spreads)]
        kind = next((k for k in range(K + 1) if moved[k]), None)
        return {"at": at, "kind": kind, "jumps": jumps, "spreads": spreads,
                "linked": [k for k in range(K + 1) if kind is not None and k > kind and not moved[k]]}

    def _meta_transitions(self) -> list[dict]:
        """The transitions' own meta molettes, kind by kind (like intersects with like: a turn with
        turns, a jump of value with jumps of value): the transitions intersected with themselves
        shifted by L (1, 2, …). Where each one meets the one L before it — every jump within the
        other's norm, places a steady step apart (within the cells that warm each other) — the
        transitions of that kind have a dynamic, proven by two such pairs at least. The smallest L."""
        tol = 2 * RADIUS * self.grain * self.sx
        kinds = sorted({t["kind"] for t in self.transitions if t["kind"] is not None})
        found = []
        for kind in kinds:
            meta = self._meta_of([t for t in self.transitions if t["kind"] == kind], tol)
            if meta:
                found.append(meta)
        return found

    def _meta_of(self, T: list[dict], tol: float) -> dict | None:
        """The smallest shift L at which transitions of one kind meet themselves (see _meta_transitions)."""
        m = len(T)
        for L in range(1, m):
            if m - L < 2:
                break
            pairs = list(zip(T, T[L:]))
            gaps, tot = [b["at"] - a["at"] for a, b in pairs], 0.0
            for g in gaps:
                tot += g
            step = tot / len(gaps)
            if step <= 0 or any(abs(g - step) > tol for g in gaps):
                continue
            same = True
            for a, b in pairs:
                K = min(len(a["jumps"]), len(b["jumps"]))
                z = z_chance(K)
                for k in range(K):
                    # within chance, or within the cells that warm each other in that intersection
                    e = math.sqrt(a["spreads"][k] * a["spreads"][k] + b["spreads"][k] * b["spreads"][k])
                    near = 2 * RADIUS * (self.grain * self.sy if k == 0 else self._unit(k))
                    if abs(a["jumps"][k] - b["jumps"][k]) > z * e + near:
                        same = False
                        break
                if not same:
                    break
            if same:
                return {"lag": L, "step": step, "seen": T}
        return None

    def foreseen(self, lo: float, hi: float) -> list[dict]:
        """The transitions she has not seen, from the dynamic of her transitions: beyond the last one,
        each is the one L before it a step further; before the first, the one L after it a step back."""
        out = []
        for meta in self.meta:
            L, step = meta["lag"], meta["step"]
            ext, k = list(meta["seen"]), 0
            while k < 10000:
                t = dict(ext[-L], at=ext[-L]["at"] + step)
                if t["at"] > hi:
                    break
                ext.append(t)
                out.append(t)
                k += 1
            ext, k = list(meta["seen"]), 0
            while k < 10000:
                t = dict(ext[L - 1], at=ext[L - 1]["at"] - step)
                if t["at"] < lo:
                    break
                ext.insert(0, t)
                out.append(t)
                k += 1
        return sorted(out, key=lambda t: t["at"])

    # ------------------------------------------------- degree 3: the dynamic's dynamic
    def _sightings(self) -> list[tuple]:
        """Every reading as a sighting of the state (value, slope) and of how the slope changes
        there (f'', the transition of the dynamic answering it); a sighting is that dynamic."""
        return [(self.xs[i], self.fit[i], self.carry[i], self.curv[i], self.qs[i])
                for i in range(len(self.xs)) if self.qs[i] is not None]

    def _field(self) -> None:
        """The heatmap of the dynamic's changes on the (value, slope) lattice: in each cell, the norm
        of the changes of slope seen there. A cell is proven when two distinct passages that agree
        went through it; the grain is the finest at which most sightings (HOLD) fall in proven
        cells."""
        ss = [s for _, _, s, _, _ in self.samples]
        self.s_scale = max((abs(s) for s in ss), default=1.0) or 1.0
        by_q = {}
        for _, _, _, a, q in self.samples:
            by_q[q] = a
        qs = sorted(by_q)
        ds = [abs(by_q[j] - by_q[i]) for i, j in zip(qs, qs[1:])]
        if ds:
            mu = sum(ds) / len(ds)
            sd = math.sqrt(sum((d - mu) ** 2 for d in ds) / len(ds))
            ds = [d for d in ds if d <= mu + Z * sd] or ds
        self.f_width = max(ds) if ds else 0.0

        def agree(vs):
            return len(vs) >= 2 and max(vs) - min(vs) <= 2 * self.f_width

        def cells_at(g):
            # a sighting is one passage through a cell: the readings, in order along the axis, entering it
            # (a dynamic of high degree passes through the same state again on each of its returns)
            cells: dict = {}
            prev, k = None, 0
            for _, y, s, a, _q in self.samples:
                c = self._phase(y, s, g)
                if c != prev:
                    k += 1
                    prev = c
                cells.setdefault(c, {})[k] = a
            return cells

        best = None
        for k in range(1, 9):
            g = 2.0 ** -k
            cells = cells_at(g)
            tot = sum(len(v) for v in cells.values())
            proven = sum(len(v) for v in cells.values() if agree(list(v.values())))
            if tot and proven >= HOLD * tot:
                best = (g, cells)
            elif best is not None:
                break
        self.pgrain, raw = best if best is not None else (0.5, cells_at(0.5))
        self.field = {}
        for c, by in raw.items():
            vs = list(by.values())
            if not agree(vs):
                continue
            self.field[c] = (sum(vs) / len(vs), len(vs))

    def _phase(self, y: float, s: float, g: float) -> tuple:
        return (math.floor((y - self.y0) / self.sy / g), math.floor(s / self.s_scale / g))

    def change(self, y: float, s: float, default: float = 0.0) -> float:
        """How the slope changes in the state (value, slope): the norm of its cell, else of its warm
        neighbours (within RADIUS), else ``default``."""
        c = self._phase(y, s, self.pgrain)
        if c in self.field:
            return self.field[c][0]
        tot = w = 0.0
        for dy in range(-RADIUS, RADIUS + 1):
            for ds in range(-RADIUS, RADIUS + 1):
                v = self.field.get((c[0] + dy, c[1] + ds))
                if v:
                    tot += v[0] * v[1]
                    w += v[1]
        return tot / w if w else default

    def integrate(self, x: float, y: float, s: float, to: float, n: int, default: float = 0.0,
                  events=()) -> list[tuple]:
        """Her own points from (x, y, slope s) to ``to``, n of them, each from the one before
        (midpoint rule); backwards when ``to`` < x — the same transitions read from the other side.
        ``events``: transitions of dynamics on the way; crossing one, the value, the differential and
        its differential jump as they do there (backwards: the other way)."""
        out = [(x, y)]
        n = max(n, 1)
        h = (to - x) / n
        ahead = sorted((t for t in events if min(x, to) < t["at"] < max(x, to)),
                       key=lambda t: t["at"], reverse=h < 0)
        e = 0
        for _ in range(n):
            a1 = self.change(y, s, default)
            ym, sm = y + s * h / 2, s + a1 * h / 2
            a2 = self.change(ym, sm, default)
            y, s, x = y + sm * h, s + a2 * h, x + h
            while e < len(ahead) and (ahead[e]["at"] <= x if h > 0 else ahead[e]["at"] >= x):
                J, sign = ahead[e]["jumps"], 1.0 if h > 0 else -1.0
                y += sign * J[0] if len(J) > 0 else 0.0
                s += sign * J[1] if len(J) > 1 else 0.0
                default += sign * J[2] if len(J) > 2 else 0.0
                e += 1
            out.append((x, y))
        return out

    def _steps(self, length: float) -> int:
        return max(2, min(4000, math.ceil(abs(length) / self.spacing())))

    def _bridge(self, xa, ya, sa, xb, yb, sb, events=()) -> list[tuple]:
        """A void: her own points, one per ordinary step, forward from one side, backward from the
        other, blended across the void; the transitions of dynamics in it crossed both ways."""
        n = self._steps(xb - xa)
        across = (sb - sa) / (xb - xa)  # the transition between the two dynamics, spread over the void
        if events:
            across = 0.0  # the transitions in the void carry the change themselves
        fw = self.integrate(xa, ya, sa, xb, n, across, events)
        bw = list(reversed(self.integrate(xb, yb, sb, xa, n, across, events)))
        return [(x, (1 - k / n) * y1 + k / n * y2) for k, ((x, y1), (_, y2)) in enumerate(zip(fw, bw))]

    # ---------------------------------------------------------- what she draws
    def read(self, lo: float | None = None, hi: float | None = None) -> list[tuple]:
        """Her answer everywhere: at each reading, what the meta molette answering it says; in the
        voids (and before the first reading, after the last), the points she creates there.
        ``self.created`` keeps the points created in voids."""
        n = len(self.xs)
        wide = self.void()
        out, self.created = [], []
        # the transitions that have a dynamic of their own (seen in a meta molette of transitions, or
        # foreseen by it where she has nothing): a lone transition is not proven against a union that
        # holds, a regular one is
        events = [t for m in self.meta for t in m["seen"]] + self.foreseen(self.xs[0] if lo is None else lo,
                                                                          self.xs[-1] if hi is None else hi)
        if lo is not None and lo < self.xs[0]:
            pts = list(reversed(self.integrate(self.xs[0], self.fit[0], self.carry[0], lo,
                                               self._steps(self.xs[0] - lo), self.curv[0], events)))[:-1]
            out += pts
            if self.xs[0] - lo > wide:
                self.created += pts
        for i in range(n):
            out.append((self.xs[i], self.fit[i]))
            if i + 1 < n and self.xs[i + 1] - self.xs[i] > wide:
                W = self.answer[i]
                inner = [t for t in events if self.xs[i] < t["at"] < self.xs[i + 1]]
                if not inner and W is self.answer[i + 1] and W.state == "holds" and self.directed(W):
                    # one dynamic holds both sides: its union across the void is the integral — her points
                    # there are its own
                    xa, xb = self.xs[i], self.xs[i + 1]
                    k = self._steps(xb - xa)
                    pts = [(x, self.line(W, x)) for x in (xa + (xb - xa) * j / k for j in range(1, k))]
                else:  # a transition in the void: created from both sides, each continuing its dynamic
                    pts = self._bridge(self.xs[i], self.fit[i], self.carry[i],
                                       self.xs[i + 1], self.fit[i + 1], self.carry[i + 1], inner)[1:-1]
                out += pts
                self.created += pts
        if hi is not None and hi > self.xs[-1]:
            pts = self.integrate(self.xs[-1], self.fit[-1], self.carry[-1], hi,
                                 self._steps(hi - self.xs[-1]), self.curv[-1], events)[1:]
            out += pts
            if hi - self.xs[-1] > wide:
                self.created += pts
        return out

    def draw(self, hi: float | None = None, steps: int = 2000) -> list[tuple]:
        """Her dynamic alone: from the first reading (its value and slope), the dynamic of the
        dynamic integrated — no other reading consulted."""
        hi = self.xs[-1] if hi is None else hi
        return self.integrate(self.xs[0], self.fit[0], self.carry[0], hi, steps, self.curv[0])

    @staticmethod
    def value(curve: list[tuple], x: float) -> float:
        """A drawn curve at ``x`` (linear between its points, flat beyond its ends)."""
        xs = [p[0] for p in curve]
        i = bisect_right(xs, x)
        if i == 0:
            return curve[0][1]
        if i >= len(curve):
            return curve[-1][1]
        (x0, y0), (x1, y1) = curve[i - 1], curve[i]
        return y0 if x1 == x0 else y0 + (y1 - y0) * (x - x0) / (x1 - x0)

    # ---------------------------------------------------------------- derivatives
    def speeds(self) -> list[tuple]:
        """f' at every reading: the differential of the dynamic answering it."""
        return list(zip(self.xs, self.slopes))

    def accels(self) -> list[tuple]:
        """f'' at every reading: the transition of the dynamic answering it (0 where it is a line)."""
        return list(zip(self.xs, self.curv))

    def summary(self) -> dict:
        ps = [P for P in self.pieces if P.size >= 2]
        sizes = sorted(self.best[i].size for i in range(len(self.xs)))
        degs = sorted(self.degrees)
        return {
            "readings": len(self.xs),
            "grain": self.grain,
            "dynamics": len(ps),
            "transitions": max(0, len(ps) - 1),
            "levels": self.levels,
            "scale": sizes[len(sizes) // 2],  # readings in the meta molette answering a reading (median)
            "degree": degs[len(degs) // 2],  # the degree of the dynamic answering a reading (median)
            "max_degree": degs[-1],
            "meta_transitions": [(m["seen"][0]["kind"], m["lag"]) for m in self.meta],  # (kind, shift at which they repeat)
            "field_cells": len(self.field),
            "phase_grain": self.pgrain,
        }
