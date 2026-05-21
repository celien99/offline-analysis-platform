from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.anomaly.router import router as anomaly_router
from app.api.cluster.router import router as cluster_router
from app.api.review.router import router as review_router
from app.api.training.router import router as training_router
from app.api.registry.router import router as registry_router
from app.api.embedding.router import router as embedding_router
from app.api.knowledge.router import router as knowledge_router
from app.api.rules.router import router as rules_router
from app.api.multimodal.router import router as multimodal_router
from app.common.logging import get_logger, setup_logging
from app.core.config import settings
from app.core.exceptions import AppError
from app.schemas.common import ErrorResponse

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    setup_logging()
    logger.info(
        "app_starting",
        name=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )
    yield
    logger.info("app_shutting_down")


app = FastAPI(
    title="Industrial AI Offline Analysis Platform",
    version=settings.app_version,
    description="Industrial seat defect detection — offline intelligent analysis platform",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            code=exc.code,
            message=exc.message,
        ).model_dump(),
    )


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "healthy", "version": settings.app_version}


app.include_router(anomaly_router)
app.include_router(cluster_router)
app.include_router(review_router)
app.include_router(training_router)
app.include_router(registry_router)
app.include_router(embedding_router)
app.include_router(knowledge_router)
app.include_router(rules_router)
app.include_router(multimodal_router)
