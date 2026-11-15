from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import CORS_ORIGINS
from app.routers import analytics, assistant, layers, timeseries, variables, zones

app = FastAPI(title="EarthScope", version="1")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (zones.router, variables.router, timeseries.router, layers.router, analytics.router, assistant.router):
    app.include_router(router, prefix="/api/v1")


@app.exception_handler(HTTPException)
async def http_error(_request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, dict) else {}
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": detail.get("code", "INTERNAL"),
                "message": detail.get("message", "Le service est indisponible."),
                "details": detail.get("details", {}),
            }
        },
    )
