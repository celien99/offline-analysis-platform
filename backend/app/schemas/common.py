from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class PaginatedResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    items: list[object]


class ErrorResponse(BaseModel):
    code: str
    message: str
    trace_id: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))


class StatusResponse(BaseModel):
    status: str
    message: str | None = None
    task_id: str | None = None
