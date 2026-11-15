"""Observation catalog. Display ranges are the min and max of the raw values, not a fitted model."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.config import DATASET_VERSION
from app.services.ingestion import Series, read_giovanni
from app.services.statistics import (
    compute_climatology,
    compute_mann_kendall,
    compute_multivariable_correlation,
    compute_theil_sen,
    describe_correlation,
    is_missing,
    seasonal_mann_kendall,
    seasonal_theil_sen,
    z_scores,
)

YAOUNDE = {
    "id": "zone_yaounde",
    "name": "Yaoundé",
    "country": "Cameroun",
    "countryCode": "CM",
    "latitude": 3.865,
    "longitude": 11.525,
    "aliases": ["yaounde", "yaoundé"],
    "description": "Moyennes mensuelles GLDAS/MODIS sur l'emprise Giovanni 11,4–11,65 °E, 3,75–3,98 °N. Les coordonnées servent à la navigation.",
    "footprint": [11.4, 3.75, 11.65, 3.98],
}

REGIONS = {
    "zone_barents": ("Mer de Barents et Svalbard", "Arctique", None, 76.5, 30.0, ["barents", "svalbard"]),
    "zone_france": ("Europe de l'Ouest", "France", "FR", 46.5, 2.5, ["france", "europe de l'ouest"]),
    "zone_warm_pool": ("Pacifique ouest équatorial", "Pacifique", None, 0.0, 155.0, ["warm pool", "pacifique ouest"]),
    "zone_sahel": ("Sahel central", "Sahel", None, 15.0, 0.0, ["sahel"]),
    "zone_ross": ("Mer de Ross", "Antarctique", None, -75.0, 180.0, ["ross", "mer de ross"]),
    "zone_amazon": ("Amazonie centrale", "Brésil", "BR", -3.5, -62.0, ["amazonie", "amazon"]),
    "zone_bellingshausen": ("Mer de Bellingshausen", "Antarctique", None, -70.0, -85.0, ["bellingshausen"]),
    "zone_cameroon": ("Cameroun central", "Cameroun", "CM", 5.5, 12.5, ["cameroun central"]),
    "zone_delhi": ("Plaine indo-gangétique", "Inde", "IN", 28.6, 77.2, ["delhi", "indo-gangétique", "indo gangetique"]),
}

VARIABLES = {
    "var_soil_temp": ("Température du sol (0–10 cm)", "GLDAS NOAH SoilTMP0_10cm, kelvin converti en °C.", "cat_soil", "°C", "#E23B2F", "soil-temperature", "month"),
    "var_soil_moisture": ("Humidité du sol (0–10 cm)", "GLDAS NOAH SoilMoi0_10cm, kg/m².", "cat_soil", "kg/m²", "#1F6F9A", "soil-moisture", "month"),
    "var_soil_temp_deep": ("Température du sol (10–40 cm)", "GLDAS NOAH SoilTMP10_40cm, kelvin converti en °C.", "cat_soil", "°C", "#8C2F1B", "soil-temperature-deep", "month"),
    "var_soil_moisture_deep": ("Humidité du sol (10–40 cm)", "GLDAS NOAH SoilMoi10_40cm, kg/m².", "cat_soil", "kg/m²", "#0E3A5C", "soil-moisture-deep", "month"),
    "var_evaporation": ("Évaporation", "GLDAS NOAH Evap_tavg 2.1, kg m⁻² s⁻¹ converti en mm/j.", "cat_soil", "mm/j", "#1F6B62", "evaporation", "month"),
    "var_runoff": ("Ruissellement de surface", "GLDAS NOAH Qs_acc, moyenne mensuelle dans l'unité du fichier (kg/m²).", "cat_soil", "kg/m²", "#1D6E93", "runoff", "month"),
    "var_aod": ("Épaisseur optique des aérosols", "MODIS Deep Blue AOD à 550 nm. La sentinelle −9999 reste un trou.", "cat_atmosphere", "", "#C48A3A", "aerosol-optical-depth", "month"),
    "var_t2m": ("Température de l'air", "Moyenne annuelle régionale T2M, °C.", "cat_climate", "°C", "#D4764E", "air-temperature", "year"),
    "var_ts": ("Température de surface", "Moyenne annuelle régionale TS, °C.", "cat_climate", "°C", "#E09F6D", "surface-temperature", "year"),
    "var_precip": ("Précipitations", "Moyenne annuelle régionale PRECTOTCORR, mm/j.", "cat_climate", "mm/j", "#3E7CB1", "precipitation", "year"),
    "var_root_wetness": ("Humidité racinaire", "Moyenne annuelle régionale GWETROOT, %.", "cat_climate", "%", "#2E8B6A", "root-wetness", "year"),
    "var_evland": ("Évaporation des terres", "Moyenne annuelle régionale EVLAND, mm/j.", "cat_climate", "mm/j", "#5E9BB3", "land-evaporation", "year"),
    "var_rh": ("Humidité relative", "Moyenne annuelle régionale RH2M, %.", "cat_climate", "%", "#7DCEA0", "relative-humidity", "year"),
    "var_tqv": ("Vapeur d'eau", "Moyenne annuelle régionale TQV, kg/m².", "cat_climate", "kg/m²", "#6EA8FE", "water-vapor", "year"),
    "var_slp": ("Pression au niveau de la mer", "Moyenne annuelle régionale SLP, hPa.", "cat_climate", "hPa", "#B8A1E3", "sea-level-pressure", "year"),
    "var_sea_ice": ("Glace de mer", "Moyenne annuelle régionale FRSEAICE, %.", "cat_climate", "%", "#D4E4F2", "sea-ice", "year"),
    "var_snow": ("Épaisseur de neige", "Moyenne annuelle régionale SNODP, cm.", "cat_climate", "cm", "#E5F0F4", "snow-depth", "year"),
    "var_sunlight": ("Rayonnement solaire", "Moyenne annuelle régionale ALLSKY_SFC_SW_DWN, MJ/m²/j.", "cat_atmosphere", "MJ/m²/j", "#E0B15A", "sunlight", "year"),
    "var_cloud": ("Couverture nuageuse", "Moyenne annuelle régionale CLOUD_AMT, %.", "cat_atmosphere", "%", "#A7B0B8", "cloud-cover", "year"),
    "var_tropt": ("Température de la tropopause", "Moyenne annuelle régionale TROPT, °C.", "cat_atmosphere", "°C", "#D98CB3", "tropopause-temperature", "year"),
    "var_wind": ("Vent à 10 m", "Moyenne annuelle régionale WS10M, m/s.", "cat_atmosphere", "m/s", "#8EABC4", "wind", "year"),
}

# Positions 0–1. The measured cell uses one color from the ramp; the ramp is not a spatial map.
COLOR_SCALES = {
    "var_soil_temp": ["#1B2A6B", "#2255C9", "#2EC4E6", "#7DDE6A", "#F4E04D", "#F4A261", "#E23B2F", "#FFF1D6"],
    "var_soil_temp_deep": ["#140E2E", "#1B3A7A", "#2A6F8F", "#3E8C6A", "#C9A227", "#C46B2C", "#8C2F1B"],
    "var_soil_moisture": ["#E6D3A1", "#C4B48A", "#7FA07A", "#2F8F8A", "#1F6F9A", "#0E3A5C", "#071422"],
    "var_soil_moisture_deep": ["#8AA07A", "#2F6B62", "#163E55", "#071820"],
    "var_evaporation": ["#E7F6F2", "#9FD9CF", "#3D9B8F", "#1F6B62", "#0E3D38"],
    "var_runoff": ["#E4E8D4", "#8FB573", "#2F8F7A", "#1D6E93", "#0C3A5C"],
    "var_aod": ["#F4F7F8", "#E4D2A8", "#D09A45", "#A85A28", "#5C2E16", "#24160F"],
}


@dataclass
class Catalog:
    series: dict[tuple[str, str], Series] = field(default_factory=dict)

    def zones(self) -> list[dict]:
        grouped: dict[str, list[str]] = {}
        for zone_id, variable_id in self.series:
            grouped.setdefault(zone_id, []).append(variable_id)
        rows = []
        for zone_id, variable_ids in grouped.items():
            rows.append({**self.zone_record(zone_id), "availableVariableIds": sorted(variable_ids)})
        rows.sort(key=lambda zone: zone["name"])
        return rows

    def zone_record(self, zone_id: str) -> dict:
        if zone_id == YAOUNDE["id"]:
            return {key: value for key, value in YAOUNDE.items() if key != "aliases"} | {"aliases": YAOUNDE["aliases"]}
        name, country, code, latitude, longitude, aliases = REGIONS[zone_id]
        record = {
            "id": zone_id,
            "name": name,
            "country": country,
            "latitude": latitude,
            "longitude": longitude,
            "aliases": aliases,
            "description": "Moyennes annuelles régionales. Les coordonnées sont un point de navigation, pas une station.",
        }
        if code:
            record["countryCode"] = code
        return record

    def variables(self) -> tuple[list[dict], list[dict]]:
        present = {variable_id for _, variable_id in self.series}
        categories = [
            {"id": "cat_soil", "name": "Sol", "order": 1},
            {"id": "cat_atmosphere", "name": "Atmosphère", "order": 2},
            {"id": "cat_climate", "name": "Climat régional", "order": 3},
        ]
        rows = []
        for variable_id in present:
            name, description, category, unit, color, role, resolution = VARIABLES[variable_id]
            values = [value for (_zone, vid), series in self.series.items() if vid == variable_id for value in series.values if not is_missing(value)]
            start, end = self._range(variable_id)
            rows.append(
                {
                    "id": variable_id,
                    "name": name,
                    "description": description,
                    "categoryId": category,
                    "unit": unit,
                    "color": color,
                    "scaleMode": "relative",
                    "displayScale": {"min": min(values), "max": max(values)} if values else None,
                    "visualizationType": "zone-symbols",
                    "supportedTemporalResolutions": [resolution],
                    "defaultResolution": resolution,
                    "availableDateRange": {"start": start, "end": end},
                    "aggregationMethod": "moyenne mensuelle" if resolution == "month" else "moyenne annuelle régionale",
                    "role": role,
                    "datasetVersion": DATASET_VERSION,
                }
            )
            colors = COLOR_SCALES.get(variable_id)
            if colors:
                step = 1 / (len(colors) - 1)
                rows[-1]["colorScale"] = {"stops": [{"at": index * step, "color": color} for index, color in enumerate(colors)]}
        rows.sort(key=lambda variable: variable["name"])
        used = {row["categoryId"] for row in rows}
        return [category for category in categories if category["id"] in used], rows

    def _range(self, variable_id: str) -> tuple[str, str]:
        dates = [date for (_zone, vid), series in self.series.items() if vid == variable_id for date in series.dates]
        return min(dates), max(dates)

    def get(self, zone_id: str, variable_id: str) -> Series | None:
        return self.series.get((zone_id, variable_id))

    def variable(self, variable_id: str) -> dict | None:
        return next((variable for variable in self.variables()[1] if variable["id"] == variable_id), None)

    def known_zone(self, zone_id: str) -> bool:
        return any(zone == zone_id for zone, _variable in self.series)


def load_catalog() -> Catalog:
    catalog = Catalog()
    for series in read_giovanni().values():
        catalog.series[(series.zone_id, series.variable_id)] = series
    return catalog


_CATALOG: Catalog | None = None


def get_catalog() -> Catalog:
    global _CATALOG
    if _CATALOG is None:
        _CATALOG = load_catalog()
    return _CATALOG


def window(series: Series, start: str | None, end: str | None) -> tuple[list[str], list[float | None]]:
    dates: list[str] = []
    values: list[float | None] = []
    for date, value in zip(series.dates, series.values):
        if start and date < start:
            continue
        if end and date > end:
            continue
        dates.append(date)
        values.append(value)
    return dates, values


def trend_block(dates: list[str], values: list[float | None], resolution: str, unit: str) -> dict:
    sen = seasonal_theil_sen(dates, values) if resolution == "month" else compute_theil_sen(dates, values)
    kendall = seasonal_mann_kendall(dates, values) if resolution == "month" else compute_mann_kendall(values)
    direction = kendall["trend"] if kendall["trend"] in {"up", "down", "flat", "insufficient"} else "insufficient"
    finite = [(date, value) for date, value in zip(dates, values) if not is_missing(value)]
    block = {
        "method": f"{sen['method']} ; {kendall['method']}",
        "periodStart": finite[0][0] if finite else (dates[0] if dates else ""),
        "periodEnd": finite[-1][0] if finite else (dates[-1] if dates else ""),
        "sampleCount": sen["sampleCount"],
        "direction": direction,
        "unit": unit,
    }
    if sen["slopePerYear"] is not None and direction != "insufficient" and finite:
        first = decimal_year_of(finite[0][0])
        last = decimal_year_of(finite[-1][0])
        slope = sen["slopePerYear"]
        intercept = sen["intercept"]
        block["changePerDecade"] = slope * 10
        block["changeOverPeriod"] = slope * (last - first)
        block["startValue"] = intercept + slope * first
        block["endValue"] = intercept + slope * last
    return block


def decimal_year_of(date: str) -> float:
    return int(date[0:4]) + (int(date[5:7]) - 1) / 12


def univariate(series: Series, unit: str, start: str | None, end: str | None) -> dict:
    dates, values = window(series, start, end)
    sen = seasonal_theil_sen(dates, values) if series.resolution == "month" else compute_theil_sen(dates, values)
    kendall = seasonal_mann_kendall(dates, values) if series.resolution == "month" else compute_mann_kendall(values)
    finite = [(date, value) for date, value in zip(dates, values) if not is_missing(value)]
    theil = {
        "method": sen["method"],
        "slopePerYear": sen["slopePerYear"],
        "changePerDecade": None if sen["slopePerYear"] is None else sen["slopePerYear"] * 10,
        "intercept": sen["intercept"],
        "sampleCount": sen["sampleCount"],
        "periodStart": finite[0][0] if finite else None,
        "periodEnd": finite[-1][0] if finite else None,
        "startValue": None,
        "endValue": None,
    }
    if sen["slopePerYear"] is not None and finite and sen["intercept"] is not None:
        theil["startValue"] = sen["intercept"] + sen["slopePerYear"] * decimal_year_of(finite[0][0])
        theil["endValue"] = sen["intercept"] + sen["slopePerYear"] * decimal_year_of(finite[-1][0])
    return {
        "zoneId": series.zone_id,
        "variableId": series.variable_id,
        "resolution": series.resolution,
        "unit": unit,
        "period": {"start": dates[0] if dates else start, "end": dates[-1] if dates else end},
        "sampleCount": sum(1 for value in values if not is_missing(value)),
        "missingCount": sum(1 for value in values if is_missing(value)),
        "theilSen": theil,
        "mannKendall": kendall,
        "climatology": compute_climatology(dates, values) if series.resolution == "month" else [],
    }


def multivariable(catalog: Catalog, zone_id: str, variable_ids: list[str], start: str | None, end: str | None) -> dict:
    chosen = []
    for variable_id in variable_ids:
        series = catalog.get(zone_id, variable_id)
        if series is None:
            continue
        chosen.append(series)
    dates: set[str] = set()
    cached = {}
    for series in chosen:
        sliced_dates, sliced_values = window(series, start, end)
        cached[series.variable_id] = dict(zip(sliced_dates, sliced_values))
        dates.update(sliced_dates)
    ordered = sorted(dates)
    normalized = {variable_id: dict(zip(ordered, z_scores([cached[variable_id].get(date) for date in ordered]))) for variable_id in cached}
    climatology = {}
    for series in chosen:
        if series.resolution != "month":
            continue
        sliced_dates, sliced_values = window(series, start, end)
        climatology[series.variable_id] = {row["month"]: row["mean"] for row in compute_climatology(sliced_dates, sliced_values)}
    aligned = []
    for date in ordered:
        values = {variable_id: cached[variable_id].get(date) for variable_id in cached}
        anomalies = {}
        for variable_id, value in values.items():
            mean = climatology.get(variable_id, {}).get(int(date[5:7]))
            anomalies[variable_id] = None if value is None or mean is None else value - mean
        aligned.append(
            {
                "date": date,
                "values": values,
                "normalized": {variable_id: normalized[variable_id][date] for variable_id in cached},
                "anomalies": anomalies,
            }
        )
    names = {variable_id: VARIABLES[variable_id][0] for variable_id in cached}
    pairs = []
    ids = list(cached)
    for index, left_id in enumerate(ids):
        for right_id in ids[index + 1 :]:
            left_series = next(series for series in chosen if series.variable_id == left_id)
            step = "month" if left_series.resolution == "month" else "year"
            stats = compute_multivariable_correlation(
                list(cached[left_id].items()),
                list(cached[right_id].items()),
                step,
            )
            stats["variableIds"] = [left_id, right_id]
            stats["interpretation"] = describe_correlation(
                names[left_id], names[right_id], stats["pearsonR"], stats["pValue"], stats["relationship"]
            )
            pairs.append(stats)
    correlation = None
    if pairs:
        correlation = max(pairs, key=lambda pair: abs(pair["pearsonR"]) if pair["pearsonR"] is not None else -1)
    return {
        "zoneId": zone_id,
        "period": {"start": ordered[0] if ordered else start, "end": ordered[-1] if ordered else end},
        "variables": ids,
        "correlation": correlation,
        "pairs": pairs,
        "alignedObservations": aligned,
    }
