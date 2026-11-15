from fastapi import APIRouter, HTTPException

from app.services.catalog import get_catalog
from app.services.statistics import is_missing

router = APIRouter()


def _snap(date: str, resolution: str) -> str:
    if resolution == "year":
        return f"{date[0:4]}-01-01"
    return f"{date[0:7]}-01"


@router.get("/layers")
def layer(variableId: str, date: str):
    catalog = get_catalog()
    variable = catalog.variable(variableId)
    if variable is None:
        raise HTTPException(status_code=404, detail={"code": "VARIABLE_NOT_FOUND", "message": "No variable matches this identifier."})
    if len(date) < 10:
        raise HTTPException(status_code=400, detail={"code": "VALIDATION_ERROR", "message": "Expected a date in YYYY-MM-DD format."})
    snapped = _snap(date, variable["defaultResolution"])
    if snapped < variable["availableDateRange"]["start"] or snapped > variable["availableDateRange"]["end"]:
        raise HTTPException(status_code=400, detail={"code": "VALIDATION_ERROR", "message": "Date outside the available coverage."})
    zone_values = []
    for series in catalog.series.values():
        if series.variable_id != variableId:
            continue
        key = f"{date[0:4]}-01-01" if series.resolution == "year" else f"{date[0:7]}-01"
        value = series.as_map().get(key)
        zone_values.append(
            {
                "zoneId": series.zone_id,
                "value": None if is_missing(value) else value,
                "status": "missing" if is_missing(value) else "observed",
            }
        )
    scale = variable.get("displayScale")
    return {
        "layer": {
            "variableId": variableId,
            "date": snapped if variable["defaultResolution"] == "month" else f"{date[0:4]}-01-01",
            "mode": "zone-symbols",
            "unit": variable["unit"],
            "scale": None if not scale else {"min": scale["min"], "max": scale["max"], "source": "data"},
            "zoneValues": zone_values,
        }
    }
