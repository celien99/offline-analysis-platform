"""模型上线门禁记录 — 记录新模型通过门禁评估的结果。

门禁评估在每次训练完成后自动执行，检查新模型是否满足：
  - 真实缺陷召回率不下降
  - 误报抑制率提升达到阈值
  - 真实缺陷被抑制数量为 0
  - 按相机/型号分层评估
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class GateEvaluation(BaseModel):
    __tablename__ = "gate_evaluations"

    model_version_id: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True, comment="被评估的模型版本 ID"
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending",
        comment="pending / passed / failed"
    )
    # 门禁标准快照（JSON）
    criteria_json: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="评估时使用的门禁标准快照"
    )
    # 整体指标（JSON）
    metrics_json: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="整体评估指标"
    )
    # 分层指标（JSON），按 camera_id/seat_model_id 分组
    stratified_metrics_json: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="按型号/相机分层的评估指标"
    )
    # 基线模型（当前线上模型）的对比指标
    baseline_metrics_json: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="基线模型指标"
    )
    # 召回率变化
    real_defect_recall: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="真实缺陷召回率"
    )
    baseline_real_defect_recall: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="基线模型真实缺陷召回率"
    )
    # 误报抑制率
    false_alarm_suppression_rate: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="误报抑制率"
    )
    baseline_false_alarm_suppression_rate: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="基线模型误报抑制率"
    )
    # 被抑制的真实缺陷数
    suppressed_real_defect_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="被模型错误抑制的真实缺陷数"
    )
    # 评估样本量
    total_samples: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="评估集样本总数"
    )
    real_defect_samples: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="评估集真实缺陷样本数"
    )
    false_alarm_samples: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="评估集误报样本数"
    )
    # 失败原因
    failure_reasons_json: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="失败的具体原因列表（JSON）"
    )
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    evaluated_by: Mapped[str] = mapped_column(
        String(64), nullable=False, default="system:auto_gate",
        comment="评估触发者"
    )
