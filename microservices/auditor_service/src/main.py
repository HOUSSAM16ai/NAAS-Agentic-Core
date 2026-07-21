import logging

from fastapi import FastAPI, HTTPException, Response

from microservices.auditor_service.src import prom_metrics
from microservices.auditor_service.src.core import AuditorService
from microservices.auditor_service.src.schemas import (
    ConsultRequest,
    ConsultResponse,
    ReviewRequest,
    ReviewResponse,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AuditorService")

app = FastAPI(title="Auditor Microservice", version="1.0.0")

# Singleton Service
auditor_service = AuditorService()
prom_metrics.set_startup_info()


@app.get("/metrics", include_in_schema=False)
def prometheus_metrics() -> Response:
    """Prometheus scrape endpoint (cogniforge_auditor_*). Hidden from OpenAPI."""
    content, content_type = prom_metrics.export_prometheus_text()
    return Response(content=content, media_type=content_type)


@app.post("/review", response_model=ReviewResponse)
async def review_work(request: ReviewRequest):
    """
    Review the work result or plan.
    """
    try:
        return await auditor_service.review_work(request)
    except Exception as e:
        logger.error(f"Error in review_work: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/consult", response_model=ConsultResponse)
async def consult(request: ConsultRequest):
    """
    Provide consultation.
    """
    try:
        return await auditor_service.consult(request)
    except Exception as e:
        logger.error(f"Error in consult: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "auditor"}
