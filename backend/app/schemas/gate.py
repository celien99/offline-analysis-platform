from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class GateEvaluationResponse(BaseModel):
    gate_id: str
    model_version_id: str
    status: str
    real_defect_recall: float | None = None
    baseline_real_defect_recall: float | None = None
    false_alarm_suppression_rate: float | None = None
    baseline_false_alarm_suppression_rate: float | None = None
    suppressed_real_defect_count: int | None = None
    total_samples: int | None = None
    real_defect_samples: int | None = None
    false_alarm_samples: int | None = None
    criteria: dict[str, object] | None = None
    metrics: dict[str, object] | None = None
    baseline_metrics: dict[str, object] | None = None
    stratified_metrics: list[dict[str, object]] | None = None
    failure_reasons: list[str] | None = None
    evaluated_at: datetime
    evaluated_by: str

    model_config = {"from_attributes": True}


class GateTriggerRequest(BaseModel):
    model_version_id: str


class GateStatusResponse(BaseModel):
    model_version_id: str
    model_status: str
    gate_status: str | None = None
    gate_passed: bool = False
    message: str
