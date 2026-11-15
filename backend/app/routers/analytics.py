from fastapi import APIRouter, HTTPException

from app.models.schemas import MultivariableReport, UnivariateReport
from app.services.catalog import get_catalog, multivariable, univariate

router = APIRouter()


def _check_window(start: str | None, end: str | None) -> None:
    if start and end and start > end:
        raise HTTPException(status_code=400, detail={"code": "VALIDATION_ERROR", "message": "The start date is after the end date."})


@router.get("/analytics", response_model=UnivariateReport)
def analytics(zoneId: str, variableId: str, startDate: str | None = None, endDate: str | None = None):
    _check_window(startDate, endDate)
    catalog = get_catalog()
    variable = catalog.variable(variableId)
    series = catalog.get(zoneId, variableId)
    if not catalog.known_zone(zoneId):
        raise HTTPException(status_code=404, detail={"code": "ZONE_NOT_FOUND", "message": "No zone matches this identifier."})
    if variable is None or series is None:
        raise HTTPException(status_code=404, detail={"code": "VARIABLE_NOT_FOUND", "message": "No variable matches this identifier."})
    return univariate(series, variable["unit"], startDate, endDate)


@router.get("/analytics/multivariable", response_model=MultivariableReport)
def analytics_multi(zoneId: str, variableIds: str, startDate: str | None = None, endDate: str | None = None):
    _check_window(startDate, endDate)
    catalog = get_catalog()
    if not catalog.known_zone(zoneId):
        raise HTTPException(status_code=404, detail={"code": "ZONE_NOT_FOUND", "message": "No zone matches this identifier."})
    identifiers = [item for item in variableIds.split(",") if item]
    if len(identifiers) < 2 or len(identifiers) > 6:
        raise HTTPException(status_code=400, detail={"code": "VALIDATION_ERROR", "message": "Provide between 2 and 6 variables."})
    missing = [item for item in identifiers if catalog.get(zoneId, item) is None]
    if missing:
        raise HTTPException(
            status_code=404,
            detail={"code": "VARIABLE_NOT_FOUND", "message": "A variable is not available for this zone.", "details": {"variableIds": missing}},
        )
    return multivariable(catalog, zoneId, identifiers, startDate, endDate)
