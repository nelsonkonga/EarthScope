from app.services.statistics import (
    compute_mann_kendall,
    compute_multivariable_correlation,
    compute_theil_sen,
    describe_correlation,
    is_missing,
    relationship_of,
)


def yearly(start: int, count: int, slope: float, origin: float = 0):
    dates = [f"{start + index:04d}-01-01" for index in range(count)]
    values = [origin + slope * index for index in range(count)]
    return dates, values


def test_sentinel_is_a_gap():
    assert is_missing(-9999)
    assert not is_missing(0)
    assert not is_missing(-1.5)


def test_theil_sen_recovers_a_straight_line():
    dates, values = yearly(2000, 12, 0.4, 10)
    result = compute_theil_sen(dates, values)
    assert result["slopePerYear"] == 0.4
    assert result["sampleCount"] == 12


def test_theil_sen_ignores_gaps():
    dates, values = yearly(2000, 10, 1, 0)
    values[3] = None
    values[4] = -9999
    result = compute_theil_sen(dates, values)
    assert abs(result["slopePerYear"] - 1) < 1e-9


def test_mann_kendall_on_a_rise():
    _dates, values = yearly(1981, 20, 0.2, -2)
    result = compute_mann_kendall(values)
    assert result["trend"] == "up"
    assert result["pValue"] < 0.05
    assert result["s"] > 0
    assert result["z"] > 0


def test_correlation_of_a_series_and_its_opposite():
    dates, values = yearly(2000, 24, 0.3, 5)
    opposite = [(date, None if value is None else -value) for date, value in zip(dates, values)]
    stats = compute_multivariable_correlation(list(zip(dates, values)), opposite, "year")
    assert abs(stats["pearsonR"] + 1) < 1e-9
    assert stats["relationship"] == "inverse_strong"
    assert relationship_of(0.1, 0.4) == "not_significant"
    text = describe_correlation("Température du sol (0–10 cm)", "Humidité du sol (0–10 cm)", stats["pearsonR"], stats["pValue"], stats["relationship"])
    assert "−1,00" in text
    assert "sens inverse" in text


def test_seasonal_opposition_is_not_reported_as_an_eighteen_month_lag():
    dates = []
    warm = []
    dry = []
    for year in range(2002, 2014):
        for month in range(1, 13):
            dates.append(f"{year:04d}-{month:02d}-01")
            cycle = 1 if month in {12, 1, 2} else -1 if month in {6, 7, 8} else 0
            warm.append(25 + cycle)
            dry.append(30 - cycle)
    stats = compute_multivariable_correlation(list(zip(dates, warm)), list(zip(dates, dry)), "month")
    assert stats["pearsonR"] is not None and stats["pearsonR"] < -0.5
    assert stats["bestLag"] is None


def test_correlation_needs_shared_dates():
    left = [(f"{2000 + index:04d}-01-01", float(index)) for index in range(4)]
    right = [(f"{2010 + index:04d}-01-01", float(index)) for index in range(4)]
    stats = compute_multivariable_correlation(left, right, "year")
    assert stats["relationship"] == "insufficient"
