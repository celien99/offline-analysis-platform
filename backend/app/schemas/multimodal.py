from __future__ import annotations

from pydantic import BaseModel, Field


class VLMAnalyzeRequest(BaseModel):
    cluster_ids: list[str] = Field(..., min_length=1, max_length=50)
    prompt_override: str | None = None


class VLMResultResponse(BaseModel):
    anomaly_type: str
    is_false_alarm: bool
    reason: str
    confidence: float
    suggestion: str
    raw_response: str | None = None


class VLMAnalysisResponse(BaseModel):
    status: str
    cluster_id: str
    result: VLMResultResponse | None = None
    error: str | None = None


class VLMBatchAnalysisResponse(BaseModel):
    status: str
    total: int
    results: list[VLMAnalysisResponse]


class VLMAnomalyAnalysisResponse(BaseModel):
    status: str
    anomaly_id: str
    result: VLMResultResponse | None = None
    error: str | None = None
