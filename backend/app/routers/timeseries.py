from fastapi import APIRouter, HTTPException

from app.config import DATASET_VERSION
from app.services.catalog import get_catalog, trend_block, window

router = APIRouter()


def _series_payload(zone_id: str, variable_id: str, start: str | None = None, end: str | None = None) -> dict:
    catalog = get_catalog()
    variable = catalog.variable(variable_id)
    series = catalog.get(zone_id, variable_id)
    if not catalog.known_zone(zone_id):
        raise HTTPException(status_code=404, detail={"code": "ZONE_NOT_FOUND", "message": "Aucune zone pour cet identifiant."})
    if variable is None:
        raise HTTPException(status_code=404, detail={"code": "VARIABLE_NOT_FOUND", "message": "Aucune variable pour cet identifiant."})
    if series is None:
        return {
            "zoneId": zone_id,
            "variableId": variable_id,
            "resolution": variable["defaultResolution"],
            "unit": variable["unit"],
            "datasetVersion": DATASET_VERSION,
            "observations": [],
            "trend": {"method": "aucune observation", "periodStart": "", "periodEnd": "", "sampleCount": 0, "direction": "insufficient", "unit": variable["unit"]},
        }
    dates, values = window(series, start, end)
    observations = [
        {"date": date, "value": value, "status": "missing" if value is None else "observed", "unit": variable["unit"]}
        for date, value in zip(dates, values)
    ]
    return {
        "zoneId": zone_id,
        "variableId": variable_id,
        "resolution": series.resolution,
        "unit": variable["unit"],
        "datasetVersion": DATASET_VERSION,
        "observations": observations,
        "trend": trend_block(dates, values, series.resolution, variable["unit"]),
    }


@router.get("/timeseries")
def get_timeseries(zoneId: str, variableId: str, resolution: str = "month", startDate: str | None = None, endDate: str | None = None):
    catalog = get_catalog()
    variable = catalog.variable(variableId)
    if variable and resolution not in variable["supportedTemporalResolutions"]:
        raise HTTPException(status_code=400, detail={"code": "VALIDATION_ERROR", "message": "Résolution non prise en charge pour cette variable."})
    return {"series": _series_payload(zoneId, variableId, startDate, endDate)}


@router.get("/rankings")
def rankings(variableId: str, metric: str = "changePerDecade"):
    catalog = get_catalog()
    variable = catalog.variable(variableId)
    if variable is None:
        raise HTTPException(status_code=404, detail={"code": "VARIABLE_NOT_FOUND", "message": "Aucune variable pour cet identifiant."})
    if metric not in {"changePerDecade", "changeOverPeriod"}:
        raise HTTPException(status_code=400, detail={"code": "VALIDATION_ERROR", "message": "Métrique inconnue."})
    rows = []
    for zone in catalog.zones():
        if variableId not in zone["availableVariableIds"]:
            continue
        series = _series_payload(zone["id"], variableId)["trend"]
        if series["direction"] == "insufficient":
            continue
        rows.append(
            {
                "zoneId": zone["id"],
                "direction": series["direction"],
                "changePerDecade": series.get("changePerDecade"),
                "changeOverPeriod": series.get("changeOverPeriod"),
            }
        )
    rows.sort(key=lambda row: row[metric] if row[metric] is not None else float("-inf"), reverse=True)
    entries = [{"rank": index + 1, **row} for index, row in enumerate(rows)]
    return {"ranking": {"unit": variable["unit"], "entries": entries}}


@router.get("/comparisons")
def comparisons(variableId: str, zoneId: list[str]):
    catalog = get_catalog()
    if catalog.variable(variableId) is None:
        raise HTTPException(status_code=404, detail={"code": "VARIABLE_NOT_FOUND", "message": "Aucune variable pour cet identifiant."})
    unique = list(dict.fromkeys(zoneId))
    if len(unique) < 2 or len(unique) > 6:
        raise HTTPException(status_code=400, detail={"code": "VALIDATION_ERROR", "message": "La comparaison demande de 2 à 6 zones."})
    return {"comparison": {"series": [_series_payload(zone_id, variableId) for zone_id in unique]}}
