"""Read raw observation files. No trend, correlation, or climatology is stored."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field

from app.config import GIOVANNI_CSV, REGIONAL_JSON
from app.services.statistics import is_missing

KELVIN = 273.15
SECONDS_PER_DAY = 86400.0


@dataclass
class Series:
    zone_id: str
    variable_id: str
    resolution: str
    dates: list[str] = field(default_factory=list)
    values: list[float | None] = field(default_factory=list)

    def as_map(self) -> dict[str, float | None]:
        return dict(zip(self.dates, self.values))


def _date_only(raw: str) -> str | None:
    text = raw.strip().split(" ")[0]
    if len(text) < 10 or text[4] != "-" or text[7] != "-":
        return None
    return text[0:10]


def _float_or_gap(raw: str) -> float | None:
    try:
        value = float(raw)
    except ValueError:
        return None
    if is_missing(value):
        return None
    return value


def read_giovanni(path=GIOVANNI_CSV) -> dict[str, Series]:
    """Yaoundé monthly means. Temperatures leave kelvin. Evaporation leaves kg m-2 s-1."""
    columns = {
        2: ("var_soil_moisture", lambda value: value),
        3: ("var_soil_moisture_deep", lambda value: value),
        4: ("var_soil_temp", lambda value: value - KELVIN),
        5: ("var_evaporation", lambda value: value * SECONDS_PER_DAY),
        6: ("var_runoff", lambda value: value),
        7: ("var_soil_temp_deep", lambda value: value - KELVIN),
        8: ("var_aod", lambda value: value),
    }
    series = {
        variable_id: Series("zone_yaounde", variable_id, "month")
        for variable_id, _convert in columns.values()
    }
    with path.open(newline="") as handle:
        for row in csv.reader(handle):
            if not row:
                continue
            date = _date_only(row[0])
            if date is None or len(row) < 9:
                continue
            for index, (variable_id, convert) in columns.items():
                parsed = _float_or_gap(row[index])
                series[variable_id].dates.append(date)
                series[variable_id].values.append(None if parsed is None else convert(parsed))
    return series


def read_regional(path=REGIONAL_JSON) -> list[Series]:
    payload = json.loads(path.read_text())
    found: list[Series] = []
    for entry in payload["series"]:
        variable_id = REGIONAL_VARIABLE_IDS[entry["var"]]
        zone_id = REGIONAL_ZONE_IDS[entry["region"]]
        series = Series(zone_id, variable_id, "year")
        for year, value in zip(entry["years"], entry["values"]):
            series.dates.append(f"{int(year):04d}-01-01")
            series.values.append(None if is_missing(value) else float(value))
        found.append(series)
    return found


REGIONAL_ZONE_IDS = {
    "Barents Sea & Svalbard": "zone_barents",
    "Western Europe (France)": "zone_france",
    "Western Pacific warm pool": "zone_warm_pool",
    "Central Sahel": "zone_sahel",
    "Ross Sea (Antarctica)": "zone_ross",
    "Central Amazon": "zone_amazon",
    "Bellingshausen Sea (Antarctica)": "zone_bellingshausen",
    "Central Cameroon": "zone_cameroon",
    "Indo-Gangetic Plain (Delhi)": "zone_delhi",
}

REGIONAL_VARIABLE_IDS = {
    "T2M": "var_t2m",
    "TS": "var_ts",
    "FRSEAICE": "var_sea_ice",
    "SNODP": "var_snow",
    "PRECTOTCORR": "var_precip",
    "SLP": "var_slp",
    "GWETROOT": "var_root_wetness",
    "EVLAND": "var_evland",
    "ALLSKY_SFC_SW_DWN": "var_sunlight",
    "CLOUD_AMT": "var_cloud",
    "TROPT": "var_tropt",
    "TQV": "var_tqv",
    "RH2M": "var_rh",
    "WS10M": "var_wind",
}
