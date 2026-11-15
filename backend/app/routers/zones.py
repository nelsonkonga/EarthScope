from fastapi import APIRouter, HTTPException

from app.config import DATASET_VERSION
from app.services.catalog import get_catalog

router = APIRouter()


def _meta() -> dict:
    return {"crs": "EPSG:4326", "datasetVersion": DATASET_VERSION, "limit": 200, "nextCursor": None, "complete": True}


@router.get("/zones")
def list_zones(q: str | None = None):
    zones = get_catalog().zones()
    if q:
        from app.services.assistant import fold

        folded = fold(q)
        zones = [
            zone
            for zone in zones
            if folded in fold(zone["name"]) or folded in fold(zone["country"]) or any(folded in fold(alias) for alias in zone.get("aliases", []))
        ]
    return {"meta": _meta(), "zones": zones}


@router.get("/zones/{zone_id}")
def get_zone(zone_id: str):
    catalog = get_catalog()
    if not catalog.known_zone(zone_id):
        raise HTTPException(status_code=404, detail={"code": "ZONE_NOT_FOUND", "message": "No zone matches this identifier."})
    zone = next(zone for zone in catalog.zones() if zone["id"] == zone_id)
    return zone
