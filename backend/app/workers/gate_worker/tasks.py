"""门禁评估 Celery 任务。训练完成后自动触发。"""

from __future__ import annotations

from app.common.logging import get_logger
from app.core.config import settings
from app.infrastructure.database.session import async_session_factory
from app.infrastructure.queue.celery_app import celery_app
from app.workers import run_async

logger = get_logger(__name__)


@celery_app.task(name="gate.evaluate_model")
def evaluate_model_gate(
    model_version_id: str,
    triggered_by: str = "system:auto_gate",
) -> dict[str, object]:
    """对新训练模型执行门禁评估。"""
    logger.info("gate_evaluation_started", model_version_id=model_version_id)

    if not settings.gate_enabled:
        logger.info("gate_evaluation_disabled")
        return {"status": "skipped", "reason": "gate_disabled"}

    async def _run() -> dict[str, object]:
        from app.models.registry import ModelVersion
        from app.services.gate.service import GateEvaluationService

        async with async_session_factory() as session:
            model = await session.get(ModelVersion, model_version_id)
            if model is None:
                logger.error("gate_model_not_found", model_version_id=model_version_id)
                return {"status": "failed", "error": "model not found"}

            service = GateEvaluationService(session)
            gate_eval = await service.evaluate(model, triggered_by=triggered_by)

            # 更新模型状态
            if gate_eval.status == "passed":
                model.status = "validated"
            else:
                model.status = "gate_failed"
            await session.commit()

            return {
                "status": "completed",
                "gate_status": gate_eval.status,
                "gate_id": gate_eval.id,
                "recall": gate_eval.real_defect_recall,
                "suppression_rate": gate_eval.false_alarm_suppression_rate,
            }

    try:
        return run_async(_run())
    except Exception as e:
        logger.error("gate_evaluation_failed", error=str(e))
        return {"status": "failed", "error": str(e)}
