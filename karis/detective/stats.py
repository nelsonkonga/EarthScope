"""Classical trend statistics — the "basic statistical analysis" the challenge asks for.

- ``anomalies``: each month minus the baseline mean of its calendar month (the seasonal cycle
  removed), ``annual_means``;
- ``ols``: least-squares slope with its t-test and 95 % confidence interval; the residuals of
  monthly climate series are autocorrelated (a warm month is followed by a warm month), so
  the test uses the effective sample size n·(1−r1)/(1+r1) (Santer et al. 2000);
- ``mann_kendall``: non-parametric test of a monotonic trend (Mann 1945, Kendall 1975), with
  ties, and the variance correction of Hamed & Rao (1998) for autocorrelated series;
- ``seasonal_mann_kendall``: each calendar month compared only with itself (Hirsch et al. 1982);
- ``sen``: Sen's (1968) slope — the median of the slopes between every pair of points — and
  its confidence interval (Gilbert 1987);
- ``pettitt``: when the series changed level (Pettitt 1979);
- ``years_to_detect``: how many years of data a trend of this size needs to be detected with
  90 % probability at the 5 % level, given the noise (Weatherhead et al. 1998).
"""

from __future__ import annotations

import math

import numpy as np
from scipy import stats as st


# ------------------------------------------------------------------ series
def decimal_year(key: tuple) -> float:
    y, m = key
    return y + (m - 0.5) / 12.0


def climatology(series: dict, base: tuple) -> dict:
    """Mean of each calendar month over the baseline years."""
    acc: dict = {}
    for (y, m), v in series.items():
        if v is not None and base[0] <= y <= base[1]:
            acc.setdefault(m, []).append(v)
    return {m: float(np.mean(vs)) for m, vs in acc.items()}


def anomalies(series: dict, base: tuple) -> dict:
    clim = climatology(series, base)
    return {k: (v - clim[k[1]] if v is not None and k[1] in clim else None) for k, v in sorted(series.items())}


def annual_means(series: dict, min_months: int = 12) -> dict:
    acc: dict = {}
    for (y, _m), v in series.items():
        if v is not None:
            acc.setdefault(y, []).append(v)
    return {y: float(np.mean(vs)) for y, vs in sorted(acc.items()) if len(vs) >= min_months}


def lag1(x) -> float:
    x = np.asarray(x, float)
    d = x - x.mean()
    den = float(d @ d)
    return float(d[:-1] @ d[1:] / den) if den > 0 and len(x) > 2 else 0.0


def _pairs(n: int):
    i, j = np.triu_indices(n, 1)
    return i, j


# ---------------------------------------------------------- least squares
def ols(t, y, alpha: float = 0.05) -> dict:
    """Slope with a t-test and a confidence interval that account for lag-1 autocorrelation."""
    t, y = np.asarray(t, float), np.asarray(y, float)
    n = len(y)
    if n < 4:
        return {"n": n, "slope": float("nan"), "p": float("nan")}
    tm, ym = t.mean(), y.mean()
    sxx = float(((t - tm) ** 2).sum())
    b = float(((t - tm) * (y - ym)).sum() / sxx)
    a = ym - b * tm
    resid = y - (a + b * t)
    sse = float(resid @ resid)
    r1 = lag1(resid)
    neff = n * (1 - r1) / (1 + r1) if r1 > 0 else float(n)
    neff = min(float(n), neff)
    out = {"n": n, "n_eff": neff, "r1": r1, "slope": b, "intercept": a,
           "r2": 1 - sse / float(((y - ym) ** 2).sum()) if np.any(y != ym) else 0.0}
    if neff <= 3:
        out.update(se=float("nan"), t=float("nan"), df=neff - 2, p=float("nan"), ci=(float("nan"), float("nan")))
        return out
    se = math.sqrt(sse / (neff - 2) / sxx)
    df = neff - 2
    tstat = b / se if se > 0 else float("inf")
    crit = float(st.t.ppf(1 - alpha / 2, df))
    out.update(se=se, t=tstat, df=df, p=float(2 * st.t.sf(abs(tstat), df)), ci=(b - crit * se, b + crit * se))
    return out


# ------------------------------------------------------------ Mann-Kendall
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
    d = x - x.mean()
    den = float(d @ d)
    if den == 0:
        return np.zeros(nlags + 1)
    full = np.correlate(d, d, mode="full")[len(x) - 1:]
    return full[: nlags + 1] / den


def sen_slope(t, y) -> float:
    t, y = np.asarray(t, float), np.asarray(y, float)
    i, j = _pairs(len(y))
    dt = t[j] - t[i]
    ok = dt != 0
    return float(np.median((y[j] - y[i])[ok] / dt[ok]))


def mann_kendall(y, autocorr: bool = True, alpha: float = 0.05) -> dict:
    """Mann-Kendall test; with ``autocorr`` the variance of S is corrected for the
    autocorrelation of the ranks of the detrended series (Hamed & Rao 1998)."""
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
        sig = np.abs(acf[1:]) > band
        acc = float(((n - k) * (n - k - 1) * (n - k - 2) * acf[1:])[sig].sum())
        factor = 1 + 2 * acc / (n * (n - 1) * (n - 2))
        if factor > 0:
            var *= factor
        else:
            factor = 1.0
    z = _z(s, var)
    return {"n": n, "S": s, "var": var, "z": z, "p": float(2 * st.norm.sf(abs(z))),
            "tau": s / (n * (n - 1) / 2), "factor": factor}


def seasonal_mann_kendall(series: dict) -> dict:
    """Each calendar month compared with itself only: no seasonal cycle can fake a trend."""
    s_tot = var_tot = 0.0
    slopes = []
    for m in range(1, 13):
        pts = sorted((y, v) for (y, mm), v in series.items() if mm == m and v is not None)
        if len(pts) < 4:
            continue
        ys = np.array([p[0] for p in pts], float)
        vs = np.array([p[1] for p in pts], float)
        s, var = _s_var(vs)
        s_tot += s
        var_tot += var
        i, j = _pairs(len(vs))
        slopes.append((vs[j] - vs[i]) / (ys[j] - ys[i]))
    z = _z(s_tot, var_tot)
    return {"S": s_tot, "var": var_tot, "z": z, "p": float(2 * st.norm.sf(abs(z))),
            "slope": float(np.median(np.concatenate(slopes))) if slopes else float("nan")}


def sen(t, y, alpha: float = 0.05, var_s: float | None = None) -> dict:
    """Sen's slope, intercept and confidence interval (Gilbert 1987), from the variance of the
    Mann-Kendall S (``var_s``: pass the autocorrelation-corrected one)."""
    t, y = np.asarray(t, float), np.asarray(y, float)
    i, j = _pairs(len(y))
    dt = t[j] - t[i]
    ok = dt != 0
    slopes = np.sort((y[j] - y[i])[ok] / dt[ok])
    b = float(np.median(slopes))
    if var_s is None:
        var_s = _s_var(y)[1]
    c = st.norm.ppf(1 - alpha / 2) * math.sqrt(max(var_s, 0.0))
    N = len(slopes)
    lo = int(round((N - c) / 2)) - 1
    hi = int(round((N + c) / 2))
    return {"slope": b, "intercept": float(np.median(y - b * t)),
            "ci": (float(slopes[min(max(lo, 0), N - 1)]), float(slopes[min(max(hi, 0), N - 1)]))}


# ------------------------------------------------------------ change point
def pettitt(y) -> dict:
    """Pettitt's test: the index where the series most clearly changed level. ``at`` is the
    first index of the new level; p is the usual approximation 2·exp(−6K²/(n³+n²))."""
    y = np.asarray(y, float)
    n = len(y)
    if n < 6:
        return {"at": None, "K": 0.0, "p": float("nan")}
    v = np.sign(y[:, None] - y[None, :]).sum(axis=1)  # v_t = sum_j sign(y_t - y_j)
    u = np.cumsum(v)[:-1]  # U_t, t = 1..n-1
    t = int(np.argmax(np.abs(u)))
    K = float(abs(u[t]))
    p = min(1.0, 2 * math.exp(-6 * K * K / (n ** 3 + n ** 2)))
    return {"at": t + 1, "K": K, "p": p, "before": float(y[: t + 1].mean()), "after": float(y[t + 1:].mean())}


def years_to_detect(trend_per_year: float, sigma: float, phi: float) -> float:
    """Years of monthly data needed to detect a linear trend (90 % probability, 5 % level)."""
    if trend_per_year == 0 or not math.isfinite(trend_per_year):
        return float("inf")
    phi = min(max(phi, -0.95), 0.95)
    return ((3.3 * sigma / abs(trend_per_year)) * math.sqrt((1 + phi) / (1 - phi))) ** (2 / 3)


# ------------------------------------------------------------------ report
def verdict(p_mk: float, p_ols: float, slope: float, alpha: float = 0.05) -> dict:
    """Plain-language verdict: both tests must agree for "significant"."""
    sign = "rising" if slope > 0 else "falling" if slope < 0 else "flat"
    if p_mk < alpha and p_ols < alpha:
        level, text = "significant", f"Significant {sign} trend: both tests agree at the 95 % level."
    elif min(p_mk, p_ols) < alpha or max(p_mk, p_ols) < 2 * alpha:
        level, text = "suggestive", f"A {sign} trend that only one test (or only the 90 % level) supports."
    else:
        level, text = "not significant", f"A {sign} tendency that is not significant (yet): it could be chance."
    return {"level": level, "direction": sign, "text": text}


# ------------------------------------------------------------ season / months
ALL_MONTHS = tuple(range(1, 13))
SEASONS = {"DJF": (12, 1, 2), "MAM": (3, 4, 5), "JJA": (6, 7, 8), "SON": (9, 10, 11)}


def season_plan(months) -> tuple[tuple, frozenset]:
    """The selected calendar months, sorted, and those that belong to the NEXT year's season.

    The selection is read as a circular arc: it starts right after its widest gap. When the arc
    crosses the year end (Dec-Jan-Feb, Nov-Feb...) its months before the year end belong to the
    next year (DJF 1990 = Dec 1989 + Jan-Feb 1990). Ties prefer "no wrap"."""
    ms = tuple(sorted({int(m) for m in months}))
    if not ms or ms[0] < 1 or ms[-1] > 12:
        raise ValueError("months must be calendar months 1..12")
    gaps = [(ms[0] + 12 - ms[-1], 0)] + [(ms[i] - ms[i - 1], i) for i in range(1, len(ms))]
    best_gap, start = gaps[0]
    for g, i in gaps[1:]:
        if g > best_gap:
            best_gap, start = g, i
    return ms, frozenset(ms[start:]) if start > 0 else frozenset()


def seasonal_annual_means(series: dict, months=None) -> dict:
    """Like ``annual_means`` but averaging only the requested calendar months of each year. A year
    counts only if all its selected months are present (``None`` is missing)."""
    ms, nxt = season_plan(ALL_MONTHS if months is None else months)
    acc: dict = {}
    for (y, m), v in sorted(series.items()):
        if v is None or m not in ms:
            continue
        acc.setdefault(y + 1 if m in nxt else y, {})[m] = v
    return {y: float(np.mean([d[m] for m in ms])) for y, d in sorted(acc.items()) if len(d) == len(ms)}


def season_trend(series: dict, base: tuple, months=None, alpha: float = 0.05) -> dict | None:
    """The yearly trend of a subset of calendar months: the same tests as the annual part of
    ``trend_report`` (``ols``, ``mann_kendall``, ``sen``, ``pettitt``, ``verdict``) on the yearly
    means of those months only. None when fewer than four complete seasons or no baseline."""
    ms, _nxt = season_plan(ALL_MONTHS if months is None else months)
    ann = seasonal_annual_means(series, ms)
    clim = climatology(series, base)
    if len(ann) < 4 or any(m not in clim for m in ms):
        return None
    bmean = float(np.mean([clim[m] for m in ms]))
    ay = np.array(list(ann), float)
    av = np.array(list(ann.values()), float)
    y_ols = ols(ay, av, alpha)
    y_mk = mann_kendall(av, True, alpha)
    y_sen = sen(ay, av, alpha, var_s=y_mk["var"])
    change = pettitt(av) if len(av) >= 6 else {"at": None, "K": 0.0, "p": float("nan")}
    rate = y_sen["slope"]
    resid = av - (y_ols["intercept"] + y_ols["slope"] * ay)
    sigma, phi = float(resid.std(ddof=1)), lag1(resid)
    base_years = [v for y, v in ann.items() if base[0] <= y <= base[1]]
    base_sd = float(np.std(base_years, ddof=1)) if len(base_years) > 2 else float("nan")
    total = rate * float(ay[-1] - ay[0])
    return {
        "months": list(ms), "baseline_mean": bmean, "baseline_sd": base_sd,
        "annual": {"years": ay.tolist(), "values": av.tolist(), "ols": y_ols, "mann_kendall": y_mk, "sen": y_sen,
                   "pettitt": {**change, "year": int(ay[change["at"]]) if change.get("at") is not None else None}},
        "per_decade": rate * 10, "per_decade_ci": [c * 10 for c in y_sen["ci"]],
        "ols_per_decade": y_ols["slope"] * 10, "ols_per_decade_ci": [c * 10 for c in y_ols["ci"]],
        "total_change": total, "total_change_sd": total / base_sd if base_sd and base_sd > 0 else float("nan"),
        "total_change_pct": 100 * total / bmean if bmean and bmean > 0 else None,
        "years": float(ay[-1] - ay[0] + 1), "noise_sd": sigma, "noise_r1": phi,
        "years_needed": years_to_detect(rate, sigma, phi),
        "verdict": verdict(y_mk["p"], y_ols["p"], rate, alpha),
        "anomalies": (av - bmean).tolist(),
    }


def trend_report(series: dict, base: tuple, alpha: float = 0.05) -> dict:
    """Everything the challenge asks about one monthly series."""
    keys = [k for k, v in sorted(series.items()) if v is not None]
    if len(keys) < 48:
        raise ValueError("at least four years of monthly data are needed")
    anom = anomalies({k: series[k] for k in keys}, base)
    ak = [k for k in keys if anom.get(k) is not None]
    t = np.array([decimal_year(k) for k in ak])
    a = np.array([anom[k] for k in ak])
    m_ols = ols(t, a, alpha)
    m_mk = mann_kendall(a, True, alpha)
    m_sen = sen(t, a, alpha, var_s=m_mk["var"])
    seas = seasonal_mann_kendall({k: series[k] for k in keys})
    ann = annual_means({k: series[k] for k in keys})
    ay = np.array(list(ann), float)
    av = np.array(list(ann.values()), float)
    y_ols = ols(ay, av, alpha) if len(ay) >= 4 else None
    y_mk = mann_kendall(av, True, alpha) if len(ay) >= 4 else None
    y_sen = sen(ay, av, alpha, var_s=y_mk["var"]) if y_mk else None
    change = pettitt(av) if len(av) >= 6 else {"at": None}
    # The headline: Sen's slope of the annual means, tested by Mann-Kendall and by the t-test on
    # the same yearly values (both corrected for autocorrelation). The slopes of monthly
    # anomalies are kept as a second look: for a variable that is zero half of the year
    # (rain in a dry season) their median is pulled toward 0 by the ties.
    if y_sen is None:
        raise ValueError("at least four complete years are needed")
    rate = y_sen["slope"]
    resid = a - (m_ols["intercept"] + m_ols["slope"] * t)
    sigma, phi = float(resid.std(ddof=1)), lag1(resid)
    need = years_to_detect(rate, sigma, phi)
    span = float(ay[-1] - ay[0] + 1)
    base_vals = [series[k] for k in keys if base[0] <= k[0] <= base[1]]
    base_mean = float(np.mean(base_vals)) if base_vals else float("nan")
    base_years = [v for y, v in ann.items() if base[0] <= y <= base[1]]
    base_sd = float(np.std(base_years, ddof=1)) if len(base_years) > 2 else float("nan")
    total = rate * (span - 1)
    return {
        "first": list(keys[0]), "last": list(keys[-1]), "months": len(keys), "years": span,
        "baseline": list(base), "baseline_mean": base_mean, "baseline_sd": base_sd,
        "monthly": {"ols": m_ols, "mann_kendall": m_mk, "sen": m_sen, "seasonal_mann_kendall": seas},
        "annual": {"years": ay.tolist(), "values": av.tolist(), "ols": y_ols, "mann_kendall": y_mk, "sen": y_sen,
                   "pettitt": {**change, "year": int(ay[change["at"]]) if change.get("at") is not None else None}},
        "per_decade": rate * 10, "per_decade_ci": [c * 10 for c in y_sen["ci"]],
        "ols_per_decade": y_ols["slope"] * 10, "ols_per_decade_ci": [c * 10 for c in y_ols["ci"]],
        "monthly_per_decade": m_ols["slope"] * 10, "monthly_per_decade_ci": [c * 10 for c in m_ols["ci"]],
        "total_change": total, "total_change_sd": total / base_sd if base_sd and base_sd > 0 else float("nan"),
        "total_change_pct": 100 * total / base_mean if base_mean and base_mean > 0 else None,
        "noise_sd": sigma, "noise_r1": phi, "years_needed": need,
        "verdict": verdict(y_mk["p"], y_ols["p"], rate, alpha),
        "anomalies": {"t": t.tolist(), "values": a.tolist()},
    }
