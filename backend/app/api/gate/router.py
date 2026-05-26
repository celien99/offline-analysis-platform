"""模型上线门禁 API。"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.common.logging import get_logger
from app.schemas.common import ErrorResponse, StatusResponse
from app.schemas.gate import GateEvaluationResponse, GateStatusResponse, GateTriggerRequest
from app.repositories.gate.repository import GateEvaluationRepository
from app.workers.gate_worker.tasks import evaluate_model_gate

router = APIRouter(prefix="/api/gates", tags=["gates"])
logger = get_logger(__name__)


@router.get(
    "/status/{model_version_id}",
    response_model=GateStatusResponse,
)
async def get_gate_status(
    model_version_id: str,
    session: AsyncSession = Depends(get_session),
) -> GateStatusResponse:
    """查询模型版本的门禁状态。"""
    from app.models.registry import ModelVersion

    model = await session.get(ModelVersion, model_version_id)
    if model is None:
        raise HTTPException(status_code=404, detail=f"Model version {model_version_id} not found")

    gate_repo = GateEvaluationRepository(session)
    gate_eval = await gate_repo.get_latest_by_model_version(model_version_id)

    if gate_eval is None:
        return GateStatusResponse(
            model_version_id=model_version_id,
            model_status=model.status,
            gate_status="pending",
            gate_passed=False,
            message="门禁评估尚未执行",
        )

    return GateStatusResponse(
        model_version_id=model_version_id,
        model_status=model.status,
        gate_status=gate_eval.status,
        gate_passed=gate_eval.status == "passed",
        message="门禁通过" if gate_eval.status == "passed" else "门禁未通过",
    )


@router.get(
    "/report/{model_version_id}",
    response_model=GateEvaluationResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_gate_report(
    model_version_id: str,
    session: AsyncSession = Depends(get_session),
) -> GateEvaluationResponse:
    """获取模型版本的详细门禁评估报告。"""
    gate_repo = GateEvaluationRepository(session)
    gate_eval = await gate_repo.get_latest_by_model_version(model_version_id)

    if gate_eval is None:
        raise HTTPException(status_code=404, detail="未找到门禁评估记录")

    return GateEvaluationResponse(
        gate_id=gate_eval.id,
        model_version_id=gate_eval.model_version_id,
        status=gate_eval.status,
        real_defect_recall=gate_eval.real_defect_recall,
        baseline_real_defect_recall=gate_eval.baseline_real_defect_recall,
        false_alarm_suppression_rate=gate_eval.false_alarm_suppression_rate,
        baseline_false_alarm_suppression_rate=gate_eval.baseline_false_alarm_suppression_rate,
        suppressed_real_defect_count=gate_eval.suppressed_real_defect_count,
        total_samples=gate_eval.total_samples,
        real_defect_samples=gate_eval.real_defect_samples,
        false_alarm_samples=gate_eval.false_alarm_samples,
        criteria=json.loads(gate_eval.criteria_json) if gate_eval.criteria_json else None,
        metrics=json.loads(gate_eval.metrics_json) if gate_eval.metrics_json else None,
        baseline_metrics=json.loads(gate_eval.baseline_metrics_json) if gate_eval.baseline_metrics_json else None,
        stratified_metrics=json.loads(gate_eval.stratified_metrics_json) if gate_eval.stratified_metrics_json else None,
        failure_reasons=json.loads(gate_eval.failure_reasons_json) if gate_eval.failure_reasons_json else None,
        evaluated_at=gate_eval.evaluated_at,
        evaluated_by=gate_eval.evaluated_by,
    )


@router.post("/evaluate", response_model=StatusResponse)
async def trigger_gate_evaluation(
    request: GateTriggerRequest,
) -> StatusResponse:
    """手动触发门禁评估。"""
    task = evaluate_model_gate.delay(
        model_version_id=request.model_version_id,
        triggered_by="manual",
    )
    logger.info("gate_evaluation_triggered_manual", task_id=task.id, model_version_id=request.model_version_id)
    return StatusResponse(
        status="queued",
        message=f"Gate evaluation task {task.id} dispatched",
    )
