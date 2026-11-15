from fastapi import APIRouter

from app.config import DATASET_VERSION
from app.services.catalog import get_catalog

router = APIRouter()


@router.get("/variables")
def list_variables():
    categories, variables = get_catalog().variables()
    return {"meta": {"datasetVersion": DATASET_VERSION, "complete": True}, "categories": categories, "variables": variables}
