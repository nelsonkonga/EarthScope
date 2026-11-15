from fastapi import APIRouter, HTTPException

from app.services.catalog import get_catalog, multivariable, univariate

router = APIRouter()


def _check_window(start: str | None, end: str | None) -> None:
    if start and end and start > end:
        raise HTTPException(status_code=400, detail={"code": "VALIDATION_ERROR", "message": "La date de début est après la date de fin."})


@router.get("/analytics")
def analytics(zoneId: str, variableId: str, startDate: str | None = None, endDate: str | None = None):
    _check_window(startDate, endDate)
    catalog = get_catalog()
    variable = catalog.variable(variableId)
    series = catalog.get(zoneId, variableId)
    if not catalog.known_zone(zoneId):
        raise HTTPException(status_code=404, detail={"code": "ZONE_NOT_FOUND", "message": "Aucune zone pour cet identifiant."})
    if variable is None or series is None:
        raise HTTPException(status_code=404, detail={"code": "VARIABLE_NOT_FOUND", "message": "Aucune variable pour cet identifiant."})
    return univariate(series, variable["unit"], startDate, endDate)


@router.get("/analytics/multivariable")
def analytics_multi(zoneId: str, variableIds: str, startDate: str | None = None, endDate: str | None = None):
    _check_window(startDate, endDate)
    catalog = get_catalog()
    if not catalog.known_zone(zoneId):
        raise HTTPException(status_code=404, detail={"code": "ZONE_NOT_FOUND", "message": "Aucune zone pour cet identifiant."})
    identifiers = [item for item in variableIds.split(",") if item]
    if len(identifiers) < 2 or len(identifiers) > 6:
        raise HTTPException(status_code=400, detail={"code": "VALIDATION_ERROR", "message": "Indiquez de 2 à 6 variables."})
    missing = [item for item in identifiers if catalog.get(zoneId, item) is None]
    if missing:
        raise HTTPException(
            status_code=404,
            detail={"code": "VARIABLE_NOT_FOUND", "message": "Une variable n'est pas disponible sur cette zone.", "details": {"variableIds": missing}},
        )
    return multivariable(catalog, zoneId, identifiers, startDate, endDate)
