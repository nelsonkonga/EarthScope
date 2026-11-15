"""Mann-Kendall test with the Hamed and Rao autocorrelation correction, plus Sen's slope.

The variance of S is corrected for the autocorrelation of the ranks of the detrended
series when ``autocorr`` is true. Dependencies: numpy, scipy.
"""

from __future__ import annotations

import math

import numpy as np
from scipy import stats as st


def _pairs(n: int):
    return np.triu_indices(n, 1)


def _s_var(y) -> tuple[float, float]:
    y = np.asarray(y, float)
    n = len(y)
    i, j = _pairs(n)
    s = float(np.sign(y[j] - y[i]).sum())
    _vals, counts = np.unique(y, return_counts=True)
    ties = float((counts * (counts - 1) * (2 * counts + 5)).sum())
    return s, (n * (n - 1) * (2 * n + 5) - ties) / 18.0


def _z(s: float, var: float) -> float:
    if var <= 0:
        return 0.0
    if s > 0:
        return (s - 1) / math.sqrt(var)
    if s < 0:
        return (s + 1) / math.sqrt(var)
    return 0.0


def _acf(x, nlags: int) -> np.ndarray:
    x = np.asarray(x, float)
    centered = x - x.mean()
    denominator = float(centered @ centered)
    if denominator == 0:
        return np.zeros(nlags + 1)
    full = np.correlate(centered, centered, mode="full")[len(x) - 1 :]
    return full[: nlags + 1] / denominator


def sen_slope(t, y) -> float:
    t, y = np.asarray(t, float), np.asarray(y, float)
    i, j = _pairs(len(y))
    dt = t[j] - t[i]
    ok = dt != 0
    return float(np.median((y[j] - y[i])[ok] / dt[ok]))


def mann_kendall(y, autocorr: bool = True, alpha: float = 0.05) -> dict:
    """Mann-Kendall. With ``autocorr``, the variance of S follows Hamed and Rao (1998)."""
    y = np.asarray(y, float)
    n = len(y)
    if n < 4:
        return {"n": n, "S": 0.0, "z": 0.0, "p": float("nan"), "tau": 0.0, "var": 0.0, "factor": 1.0}
    s, var = _s_var(y)
    factor = 1.0
    if autocorr:
        idx = np.arange(1, n + 1, dtype=float)
        ranks = st.rankdata(y - sen_slope(idx, y) * idx)
        acf = _acf(ranks, n - 1)
        band = st.norm.ppf(1 - alpha / 2) / math.sqrt(n)
        k = np.arange(1, n)
        significant_lags = np.abs(acf[1:]) > band
        accumulated = float(((n - k) * (n - k - 1) * (n - k - 2) * acf[1:])[significant_lags].sum())
        factor = 1 + 2 * accumulated / (n * (n - 1) * (n - 2))
        if factor > 0:
            var *= factor
        else:
            factor = 1.0
    z = _z(s, var)
    return {
        "n": n,
        "S": s,
        "var": var,
        "z": z,
        "p": float(2 * st.norm.sf(abs(z))),
        "tau": s / (n * (n - 1) / 2),
        "factor": factor,
    }
