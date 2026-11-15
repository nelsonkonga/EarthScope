"""Statistics computed from raw observations. Nothing here is stored ahead of a request."""

from __future__ import annotations

import math
from statistics import median
from typing import Iterable

import numpy as np
import pymannkendall as mk
from scipy.stats import norm, pearsonr

from app.config import MANN_KENDALL_ALPHA, MIN_SAMPLES

SENTINEL = -9999.0


def is_missing(value: float | None) -> bool:
    if value is None or isinstance(value, bool):
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return value <= SENTINEL + 1


def decimal_year(date: str) -> float:
    year = int(date[0:4])
    month = int(date[5:7])
    return year + (month - 1) / 12


def add_months(date: str, count: int) -> str:
    year = int(date[0:4])
    month = int(date[5:7]) - 1 + count
    year += month // 12
    month = month % 12
    return f"{year:04d}-{month + 1:02d}-01"


def finite_pairs(dates: Iterable[str], values: Iterable[float | None]) -> list[tuple[str, float]]:
    return [(date, float(value)) for date, value in zip(dates, values) if not is_missing(value)]


def compute_theil_sen(dates: list[str], values: list[float | None]) -> dict:
    points = [(decimal_year(date), value) for date, value in finite_pairs(dates, values)]
    if len(points) < 2:
        return {"method": "Theil-Sen", "slopePerYear": None, "intercept": None, "sampleCount": len(points)}
    slopes: list[float] = []
    for i, (x0, y0) in enumerate(points):
        for x1, y1 in points[i + 1 :]:
            if x1 != x0:
                slopes.append((y1 - y0) / (x1 - x0))
    if not slopes:
        return {"method": "Theil-Sen", "slopePerYear": None, "intercept": None, "sampleCount": len(points)}
    slope = float(median(slopes))
    intercept = float(median(y - slope * x for x, y in points))
    return {
        "method": "Theil-Sen",
        "slopePerYear": slope,
        "intercept": intercept,
        "sampleCount": len(points),
    }


def seasonal_theil_sen(dates: list[str], values: list[float | None]) -> dict:
    by_month: dict[int, list[tuple[str, float]]] = {month: [] for month in range(1, 13)}
    for date, value in finite_pairs(dates, values):
        by_month[int(date[5:7])].append((date, value))
    slopes: list[float] = []
    for samples in by_month.values():
        if len(samples) < 3:
            continue
        result = compute_theil_sen([date for date, _ in samples], [value for _, value in samples])
        if result["slopePerYear"] is not None:
            slopes.append(result["slopePerYear"])
    if len(slopes) < 3:
        overall = compute_theil_sen(dates, values)
        overall["method"] = "Theil-Sen"
        return overall
    slope = float(median(slopes))
    points = [(decimal_year(date), value) for date, value in finite_pairs(dates, values)]
    intercept = float(median(y - slope * x for x, y in points))
    return {
        "method": "Seasonal Theil-Sen (median of monthly slopes)",
        "slopePerYear": slope,
        "intercept": intercept,
        "sampleCount": len(points),
    }


def _from_mk(result, method: str, sample_count: int, alpha: float) -> dict:
    variance = float(result.var_s)
    z_value = float(result.z) if variance > 0 else 0.0
    p_value = float(result.p) if variance > 0 else 1.0
    if sample_count < MIN_SAMPLES or variance <= 0:
        trend = "insufficient"
    elif p_value < alpha and z_value > 0:
        trend = "up"
    elif p_value < alpha and z_value < 0:
        trend = "down"
    else:
        trend = "flat"
    return {
        "method": method,
        "s": float(result.s),
        "variance": variance,
        "z": z_value,
        "pValue": p_value,
        "alpha": alpha,
        "significant": bool(trend in {"up", "down"}),
        "trend": trend,
        "sampleCount": sample_count,
    }


def compute_mann_kendall(values: list[float | None], alpha: float = MANN_KENDALL_ALPHA) -> dict:
    clean = [float(value) for value in values if not is_missing(value)]
    if len(clean) < 3:
        return {
            "method": "Mann-Kendall",
            "s": None,
            "variance": None,
            "z": None,
            "pValue": None,
            "alpha": alpha,
            "significant": False,
            "trend": "insufficient",
            "sampleCount": len(clean),
        }
    try:
        result = mk.original_test(clean, alpha=alpha)
    except (ValueError, ZeroDivisionError):
        return {
            "method": "Mann-Kendall",
            "s": 0.0,
            "variance": 0.0,
            "z": 0.0,
            "pValue": 1.0,
            "alpha": alpha,
            "significant": False,
            "trend": "insufficient",
            "sampleCount": len(clean),
        }
    return _from_mk(result, "Mann-Kendall", len(clean), alpha)


def seasonal_mann_kendall(dates: list[str], values: list[float | None], alpha: float = MANN_KENDALL_ALPHA) -> dict:
    by_month: dict[int, list[float]] = {month: [] for month in range(1, 13)}
    for date, value in zip(dates, values):
        if is_missing(value):
            continue
        by_month[int(date[5:7])].append(float(value))
    s_total = 0.0
    var_total = 0.0
    count = 0
    for samples in by_month.values():
        if len(samples) < 3:
            continue
        try:
            result = mk.original_test(samples, alpha=alpha)
        except (ValueError, ZeroDivisionError):
            continue
        s_total += float(result.s)
        var_total += float(result.var_s)
        count += len(samples)
    if count < MIN_SAMPLES or var_total <= 0:
        return {
            "method": "Seasonal Mann-Kendall",
            "s": s_total,
            "variance": var_total,
            "z": None,
            "pValue": None,
            "alpha": alpha,
            "significant": False,
            "trend": "insufficient",
            "sampleCount": count,
        }
    sign = 1 if s_total > 0 else -1 if s_total < 0 else 0
    z_value = 0.0 if s_total == 0 else (s_total - sign) / math.sqrt(var_total)
    p_value = float(2 * (1 - norm.cdf(abs(z_value))))
    trend = "insufficient"
    if count >= MIN_SAMPLES:
        if p_value < alpha and z_value > 0:
            trend = "up"
        elif p_value < alpha and z_value < 0:
            trend = "down"
        else:
            trend = "flat"
    return {
        "method": "Seasonal Mann-Kendall (sum of monthly S)",
        "s": s_total,
        "variance": var_total,
        "z": z_value,
        "pValue": p_value,
        "alpha": alpha,
        "significant": trend in {"up", "down"},
        "trend": trend,
        "sampleCount": count,
    }


def compute_climatology(dates: list[str], values: list[float | None]) -> list[dict]:
    buckets: dict[int, list[float]] = {month: [] for month in range(1, 13)}
    for date, value in finite_pairs(dates, values):
        buckets[int(date[5:7])].append(value)
    rows = []
    for month in range(1, 13):
        samples = buckets[month]
        if not samples:
            rows.append({"month": month, "count": 0, "mean": None, "std": None, "min": None, "q1": None, "median": None, "q3": None, "max": None})
            continue
        array = np.asarray(samples, dtype=float)
        rows.append(
            {
                "month": month,
                "count": int(array.size),
                "mean": float(array.mean()),
                "std": float(array.std(ddof=1)) if array.size > 1 else 0.0,
                "min": float(array.min()),
                "q1": float(np.percentile(array, 25)),
                "median": float(np.percentile(array, 50)),
                "q3": float(np.percentile(array, 75)),
                "max": float(array.max()),
            }
        )
    return rows


def _pearson(xs: list[float], ys: list[float]) -> tuple[float | None, float | None]:
    if len(xs) < MIN_SAMPLES:
        return None, None
    if len(set(xs)) < 2 or len(set(ys)) < 2:
        return None, None
    coefficient, p_value = pearsonr(xs, ys)
    if math.isnan(coefficient) or math.isnan(p_value):
        return None, None
    return float(coefficient), float(p_value)


def relationship_of(coefficient: float | None, p_value: float | None, alpha: float = MANN_KENDALL_ALPHA) -> str:
    if coefficient is None or p_value is None:
        return "insufficient"
    if p_value >= alpha:
        return "not_significant"
    magnitude = abs(coefficient)
    if magnitude >= 0.7:
        level = "strong"
    elif magnitude >= 0.4:
        level = "moderate"
    elif magnitude >= 0.2:
        level = "weak"
    else:
        level = "negligible"
    sense = "inverse" if coefficient < 0 else "positive"
    return f"{sense}_{level}"


def format_number(value: float, digits: int = 2) -> str:
    """US number format: decimal point, typographic minus."""
    return f"{value:.{digits}f}".replace("-", "−")


def format_p(p_value: float | None) -> str:
    if p_value is None:
        return "p not computed"
    if p_value < 0.001:
        return "p < 0.001"
    return f"p = {format_number(p_value, 3)}"


def describe_correlation(name_a: str, name_b: str, coefficient: float | None, p_value: float | None, relationship: str) -> str:
    if relationship == "insufficient" or coefficient is None:
        return f"Not enough shared dates to estimate the correlation between {name_a} and {name_b}."
    r_text = format_number(coefficient)
    if relationship == "not_significant":
        return f"Correlation r = {r_text} between {name_a} and {name_b}, not significant ({format_p(p_value)})."
    strength = {
        "strong": "Strong",
        "moderate": "Moderate",
        "weak": "Weak",
        "negligible": "Negligible",
    }[relationship.split("_", 1)[1]]
    sense = "negative" if coefficient < 0 else "positive"
    return f"{strength} {sense} correlation: {name_a} and {name_b} (r = {r_text}, {format_p(p_value)})."


def z_scores(values: list[float | None]) -> list[float | None]:
    clean = [float(value) for value in values if not is_missing(value)]
    if len(clean) < 2:
        return [None for _ in values]
    mean = float(np.mean(clean))
    std = float(np.std(clean, ddof=1))
    if std == 0:
        return [None if is_missing(value) else 0.0 for value in values]
    return [None if is_missing(value) else (float(value) - mean) / std for value in values]


def _lagged_pairs(
    left: dict[str, float],
    right: dict[str, float],
    lag: int,
    step: str,
) -> tuple[list[float], list[float]]:
    xs: list[float] = []
    ys: list[float] = []
    for date, value in left.items():
        shifted = add_months(date, lag) if step == "month" else f"{int(date[0:4]) + lag:04d}-01-01"
        other = right.get(shifted)
        if other is None:
            continue
        xs.append(value)
        ys.append(other)
    return xs, ys


def _anomaly_map(pairs: list[tuple[str, float | None]], step: str) -> dict[str, float]:
    clean = [(date, value) for date, value in pairs if not is_missing(value)]
    if step != "month":
        return dict(clean)
    buckets: dict[int, list[float]] = {}
    for date, value in clean:
        buckets.setdefault(int(date[5:7]), []).append(value)
    baseline = {month: sum(samples) / len(samples) for month, samples in buckets.items()}
    return {date: value - baseline[int(date[5:7])] for date, value in clean}


def compute_multivariable_correlation(
    series_a: list[tuple[str, float | None]],
    series_b: list[tuple[str, float | None]],
    step: str,
) -> dict:
    left = {date: value for date, value in series_a if not is_missing(value)}
    right = {date: value for date, value in series_b if not is_missing(value)}
    xs, ys = _lagged_pairs(left, right, 0, step)
    coefficient, p_value = _pearson(xs, ys)
    relationship = relationship_of(coefficient, p_value)
    # Lags use the seasonal anomaly so a monthly cycle is not reported as a delay.
    anomaly_left = _anomaly_map(series_a, step)
    anomaly_right = _anomaly_map(series_b, step)
    base_x, base_y = _lagged_pairs(anomaly_left, anomaly_right, 0, step)
    base_r, _base_p = _pearson(base_x, base_y)
    span = 12 if step == "month" else 5
    best: dict | None = None
    for lag in range(-span, span + 1):
        if lag == 0:
            continue
        lag_x, lag_y = _lagged_pairs(anomaly_left, anomaly_right, lag, step)
        if base_x and len(lag_x) < 0.75 * len(base_x):
            continue
        lag_r, lag_p = _pearson(lag_x, lag_y)
        if lag_r is None or relationship_of(lag_r, lag_p) in {"insufficient", "not_significant"}:
            continue
        if best is None or abs(lag_r) > abs(best["pearsonR"]):
            best = {"steps": lag, "unit": step, "pearsonR": lag_r, "pValue": lag_p, "sampleCount": len(lag_x)}
    reference = 0.0 if base_r is None else abs(base_r)
    if best is not None and abs(best["pearsonR"]) < reference + 0.1:
        best = None
    return {
        "pearsonR": coefficient,
        "pValue": p_value,
        "sampleCount": len(xs),
        "relationship": relationship,
        "bestLag": best,
    }
