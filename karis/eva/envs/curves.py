"""Curves — a domain without actions: points of a curve, given to Eva one after another.

Eva receives readings ``(x, y)`` in a random order along the axis and nothing else; the curve,
its formula and its derivatives live here only to judge what her dynamic draws
(``checks/curve_approx.py``). ``noise`` adds a Gaussian error to every value (a share of the
curve's range).

New curves (``add_curve``): a formula of x (numbers, + − × ÷ ^, the usual functions of ``math``),
its range, and where the judge leaves a void; kept in ``data/curves/custom.json`` and loaded with
the others. The formula is read by a small evaluator that accepts nothing else (no code).
"""

from __future__ import annotations

import ast
import json
import math
import random
from pathlib import Path

CUSTOM = Path(__file__).resolve().parents[2] / "data" / "curves" / "custom.json"

# name -> (f, axis range); kept simple and varied: a periodic curve that passes through the same
# values both ways, a monotone one, one bump between two rising tails, an oscillation that dies out
CURVES = {
    "sinus": (math.sin, (0.0, 4 * math.pi)),
    "sigmoide": (lambda x: 1 / (1 + math.exp(-x)), (-6.0, 6.0)),
    "cubique": (lambda x: x ** 3 - 2 * x, (-2.0, 2.0)),
    "amortie": (lambda x: math.exp(-x / 4) * math.sin(2 * x), (0.0, 12.0)),
    # a sharp turn at every integer: transitions of dynamics that repeat (their own meta molettes)
    "triangle": (lambda x: abs((x % 3) - 1.5), (0.0, 9.8)),
}


# where the judge removes every reading, to see whether her dynamic predicts where she has none: a
# void holding a top or a bottom of the curve (the sigmoid: its steep middle), and the last tenth
VOIDS = {"sinus": (6.6, 9.1), "sigmoide": (-1.0, 2.0), "cubique": (0.3, 1.3), "amortie": (4.8, 6.0),
         "triangle": (5.4, 6.6)}
END = 0.9


def f(name: str):
    return CURVES[name][0]


def bounds(name: str) -> tuple[float, float]:
    return CURVES[name][1]


def span(name: str, n: int = 2000) -> float:
    """The curve's range of values (to read errors as a share of it)."""
    fn, (a, b) = CURVES[name]
    ys = [fn(a + (b - a) * k / (n - 1)) for k in range(n)]
    return max(ys) - min(ys)


def stream(name: str, n: int, seed: int = 0, noise: float = 0.0) -> list[tuple[float, float]]:
    """``n`` readings at places drawn uniformly along the axis, in the order they are given:
    the first ``k`` of them are what Eva has after ``k`` readings."""
    fn, (a, b) = CURVES[name]
    rng = random.Random(seed)
    sd = noise * span(name)
    out = []
    for _ in range(n):
        x = rng.uniform(a, b)
        out.append((x, fn(x) + (rng.gauss(0.0, sd) if sd else 0.0)))
    return out


def derivative(name: str, x: float, order: int = 1, h: float = 1e-4) -> float:
    """True f' or f'' (central differences), for judging only."""
    fn = CURVES[name][0]
    if order == 1:
        return (fn(x + h) - fn(x - h)) / (2 * h)
    return (fn(x + h) - 2 * fn(x) + fn(x - h)) / (h * h)


def end(name: str) -> float:
    a, b = CURVES[name][1]
    return a + END * (b - a)


def with_voids(name: str, n: int, seed: int = 0, noise: float = 0.0) -> list[tuple[float, float]]:
    """The same stream with no reading in the void nor after ``end``: the first ``n`` that remain."""
    h0, h1 = VOIDS[name]
    out = [p for p in stream(name, 4 * n + 64, seed, noise) if not h0 <= p[0] <= h1 and p[0] <= end(name)]
    return out[:n]


# ------------------------------------------------------------------ new curves
FUNCS = {k: getattr(math, k) for k in ("sin", "cos", "tan", "asin", "acos", "atan", "sinh", "cosh", "tanh",
                                       "exp", "log", "log10", "log2", "sqrt", "floor", "ceil")}
FUNCS.update(abs=abs, min=min, max=max, ln=math.log)
CONSTS = {"pi": math.pi, "e": math.e, "tau": math.tau}
OPS = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b, ast.Mult: lambda a, b: a * b,
       ast.Div: lambda a, b: a / b, ast.Pow: lambda a, b: a ** b, ast.Mod: lambda a, b: a % b}


def formula(expr: str):
    """f(x) from a formula; only x, numbers, + − × ÷ ^ %, the functions of FUNCS and the constants
    pi, e, tau are accepted (ValueError otherwise)."""
    tree = ast.parse(expr.replace("^", "**").replace("×", "*").replace("−", "-").replace("÷", "/"), mode="eval")

    def check(n):
        if isinstance(n, ast.Expression):
            check(n.body)
        elif isinstance(n, ast.BinOp) and type(n.op) in OPS:
            check(n.left)
            check(n.right)
        elif isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.UAdd, ast.USub)):
            check(n.operand)
        elif isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in FUNCS and not n.keywords:
            for a in n.args:
                check(a)
        elif isinstance(n, ast.Name) and (n.id == "x" or n.id in CONSTS):
            pass
        elif isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool):
            pass
        else:
            raise ValueError(f"« {ast.unparse(n)} » n'est pas permis : x, nombres, + - * / ^ %, "
                             f"{', '.join(sorted(FUNCS))}, pi, e, tau")

    check(tree)

    def ev(n, x):
        if isinstance(n, ast.Expression):
            return ev(n.body, x)
        if isinstance(n, ast.BinOp):
            return OPS[type(n.op)](ev(n.left, x), ev(n.right, x))
        if isinstance(n, ast.UnaryOp):
            v = ev(n.operand, x)
            return -v if isinstance(n.op, ast.USub) else v
        if isinstance(n, ast.Call):
            return FUNCS[n.func.id](*(ev(a, x) for a in n.args))
        if isinstance(n, ast.Name):
            return x if n.id == "x" else CONSTS[n.id]
        return float(n.value)

    return lambda x: float(ev(tree, x))


EXPRS = {"sinus": "sin(x)", "sigmoide": "1 / (1 + exp(-x))", "cubique": "x^3 - 2*x", "amortie": "exp(-x/4) * sin(2*x)",
         "triangle": "abs((x % 3) - 1.5)"}


def add_curve(name: str, expr: str, a: float, b: float, void=None, save: bool = True) -> str:
    """A new curve: its formula of x on [a, b]; ``void`` the interval the judge empties (default:
    the middle sixth of the range). Checked on 2 000 places (finite, not constant). Returns the
    name it is kept under."""
    name = " ".join(str(name).split())[:40] or expr[:40]
    if "|" in name:
        raise ValueError("le nom ne peut pas contenir « | »")
    a, b = float(a), float(b)
    if not (math.isfinite(a) and math.isfinite(b) and b > a):
        raise ValueError("il faut a < b")
    fn = formula(expr)
    ys = []
    for k in range(2000):
        try:
            y = fn(a + (b - a) * k / 1999)
        except (ValueError, ZeroDivisionError, OverflowError) as err:
            raise ValueError(f"la formule n'est pas définie partout sur [{a}, {b}] ({err})") from None
        if not math.isfinite(y):
            raise ValueError(f"la formule n'est pas finie partout sur [{a}, {b}]")
        ys.append(y)
    if max(ys) - min(ys) <= 1e-12 * max(1.0, abs(max(ys))):
        raise ValueError("la courbe est constante")
    if void is None:
        void = (a + (b - a) * 5 / 12, a + (b - a) * 7 / 12)
    h0, h1 = sorted(float(v) for v in void)
    if not (a < h0 < h1 < a + END * (b - a)):
        raise ValueError(f"le vide doit être dans ]{a}, {a + END * (b - a):.4g}[")
    CURVES[name] = (fn, (a, b))
    VOIDS[name] = (h0, h1)
    EXPRS[name] = expr
    if save:
        saved = [c for c in _load() if c["name"] != name]
        saved.append({"name": name, "expr": expr, "a": a, "b": b, "void": [h0, h1]})
        CUSTOM.parent.mkdir(parents=True, exist_ok=True)
        CUSTOM.write_text(json.dumps(saved, ensure_ascii=False, indent=1))
    return name


def _load() -> list:
    try:
        return json.loads(CUSTOM.read_text())
    except (OSError, ValueError):
        return []


for _c in _load():  # the curves added before
    try:
        add_curve(_c["name"], _c["expr"], _c["a"], _c["b"], _c.get("void"), save=False)
    except (KeyError, ValueError, SyntaxError):
        pass
