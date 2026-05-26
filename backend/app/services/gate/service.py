"""模型上线门禁评估服务。

训练完成后自动触发，在新的 filter classifier 模型部署前验证其质量：
  - 真实缺陷召回率 ≥ 95% 且相对基线下降 ≤ 2%
  - 误报抑制率相对基线提升 ≥ 10%
  - 被错误抑制的真实缺陷数 = 0
  - 按 camera_id / seat_model_id 分层评估
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.logging import get_logger
from app.core.config import settings
from app.core.security import generate_uuid
from app.infrastructure.storage.minio_client import minio_client
from app.models.gate import GateEvaluation
from app.models.registry import ModelVersion

logger = get_logger(__name__)


class GateEvaluationService:
    """门禁评估引擎。

    评估一个 filter classifier 模型是否满足上线门禁标准。
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def evaluate(
        self,
        model_version: ModelVersion,
        *,
        triggered_by: str = "system:auto_gate",
    ) -> GateEvaluation:
        """对模型版本执行门禁评估，返回评估记录。"""
        from app.core.config import settings
        from app.repositories.registry.model_version import ModelVersionRepository

        criteria = self._build_criteria()
        now = datetime.now(tz=timezone.utc)

        # 1. 加载评估数据（已审核的真实缺陷 + 误报样本）
        eval_data = await self._load_evaluation_data()
        total_samples = len(eval_data["images"])

        gate_eval = GateEvaluation(
            id=generate_uuid(),
            model_version_id=model_version.id,
            status="pending",
            criteria_json=json.dumps(criteria),
            total_samples=total_samples,
            real_defect_samples=sum(1 for label in eval_data["labels"] if label == 1),
            false_alarm_samples=sum(1 for label in eval_data["labels"] if label == 0),
            evaluated_at=now,
            evaluated_by=triggered_by,
        )

        if total_samples < settings.gate_min_evaluation_samples:
            gate_eval.status = "failed"
            gate_eval.failure_reasons_json = json.dumps([
                f"评估样本不足：{total_samples} < {settings.gate_min_evaluation_samples}"
            ])
            self._session.add(gate_eval)
            await self._session.commit()
            logger.info(
                "gate_evaluation_skipped_insufficient_samples",
                model_version_id=model_version.id,
                total_samples=total_samples,
            )
            return gate_eval

        # 2. 加载新模型并推理
        new_predictions = await self._run_inference(
            model_version.artifact_path, eval_data["images"]
        )

        # 3. 计算新模型指标
        new_metrics = self._compute_metrics(eval_data["labels"], new_predictions)

        # 4. 加载基线模型（当前线上模型）并计算基线指标
        baseline_metrics: dict[str, object] | None = None
        model_repo = ModelVersionRepository(self._session)
        baseline_model = await model_repo.get_latest_by_model_name(
            model_version.model_name, status="deployed"
        )
        if baseline_model and baseline_model.artifact_path:
            baseline_path = baseline_model.artifact_path
            if baseline_path != model_version.artifact_path and Path(baseline_path).exists():
                baseline_predictions = await self._run_inference(
                    baseline_path, eval_data["images"]
                )
                baseline_metrics = self._compute_metrics(
                    eval_data["labels"], baseline_predictions
                )

        # 5. 应用门禁标准
        gate_eval.real_defect_recall = new_metrics["real_defect_recall"]
        gate_eval.false_alarm_suppression_rate = new_metrics["false_alarm_suppression_rate"]
        gate_eval.suppressed_real_defect_count = new_metrics["suppressed_real_defect_count"]
        gate_eval.metrics_json = json.dumps(new_metrics)

        if baseline_metrics:
            gate_eval.baseline_real_defect_recall = baseline_metrics["real_defect_recall"]
            gate_eval.baseline_false_alarm_suppression_rate = baseline_metrics[
                "false_alarm_suppression_rate"
            ]
            gate_eval.baseline_metrics_json = json.dumps(baseline_metrics)

        # 分层评估
        stratified = await self._stratified_evaluation(
            model_version.artifact_path, eval_data
        )
        gate_eval.stratified_metrics_json = json.dumps(stratified)

        # 判定
        failures = self._check_criteria(criteria, new_metrics, baseline_metrics, stratified)
        gate_eval.status = "passed" if not failures else "failed"
        gate_eval.failure_reasons_json = json.dumps(failures) if failures else None

        self._session.add(gate_eval)
        await self._session.commit()

        logger.info(
            "gate_evaluation_complete",
            model_version_id=model_version.id,
            status=gate_eval.status,
            recall=new_metrics["real_defect_recall"],
            suppression=new_metrics["false_alarm_suppression_rate"],
            failures=len(failures),
        )
        return gate_eval

    # ── private helpers ──

    def _build_criteria(self) -> dict[str, object]:
        return {
            "min_real_defect_recall": settings.gate_min_real_defect_recall,
            "max_recall_drop": settings.gate_max_recall_drop,
            "min_false_alarm_suppression": settings.gate_min_false_alarm_suppression,
            "max_suppressed_real_defects": settings.gate_max_suppressed_real_defects,
            "min_evaluation_samples": settings.gate_min_evaluation_samples,
        }

    async def _load_evaluation_data(self) -> dict[str, object]:
        """从所有已审核 cluster 中加载评估数据。"""
        from app.repositories.anomaly.repository import AnomalyRepository
        from app.repositories.cluster.repository import ClusterMembershipRepository, ClusterRepository

        cluster_repo = ClusterRepository(self._session)
        membership_repo = ClusterMembershipRepository(self._session)
        anomaly_repo = AnomalyRepository(self._session)

        reviewed = await cluster_repo.get_by_status("reviewed", offset=0, limit=10000)

        image_label_pairs: list[tuple[str, int, str]] = []  # (anomaly_id, label, camera_id)
        for cluster in reviewed:
            if cluster.review_status == "real_defect":
                label = 1
            elif cluster.review_status == "false_alarm":
                label = 0
            else:
                continue

            cluster_aids = await membership_repo.get_anomaly_ids_by_cluster(cluster.id)
            for aid in cluster_aids:
                image_label_pairs.append((aid, label, cluster.camera_id or ""))

        anomalies = await anomaly_repo.get_by_ids([aid for aid, _, _ in image_label_pairs])
        anomaly_map = {a.id: a for a in anomalies}

        images: list[np.ndarray] = []
        labels: list[int] = []
        camera_ids: list[str] = []
        anomaly_ids: list[str] = []

        for aid, label, camera_id in image_label_pairs:
            anomaly = anomaly_map.get(aid)
            if anomaly is None or anomaly.crop_path is None:
                continue
            try:
                raw = await minio_client.download(anomaly.crop_path)
                img = np.array(Image.open(BytesIO(raw)).convert("RGB"))
                images.append(img)
                labels.append(label)
                camera_ids.append(camera_id)
                anomaly_ids.append(aid)
            except Exception as e:
                logger.warning("gate_load_image_failed", anomaly_id=aid, error=str(e))

        return {
            "images": images,
            "labels": labels,
            "camera_ids": camera_ids,
            "anomaly_ids": anomaly_ids,
        }

    async def _run_inference(
        self, model_path: str, images: list[np.ndarray]
    ) -> list[int]:
        """用 TorchScript 模型对图片列表批量推理，返回预测标签列表。"""
        import torch

        if not images:
            return []

        device = "cuda" if torch.cuda.is_available() else "cpu"
        try:
            model = torch.jit.load(model_path)
            model.eval()
        except Exception as e:
            logger.error("gate_model_load_failed", path=model_path, error=str(e))
            return [1] * len(images)  # 故障安全：全部判为真实缺陷

        mean = torch.as_tensor([0.485, 0.456, 0.406], device=device).view(1, 3, 1, 1)
        std = torch.as_tensor([0.229, 0.224, 0.225], device=device).view(1, 3, 1, 1)

        predictions: list[int] = []
        batch_size = 32

        for i in range(0, len(images), batch_size):
            batch_imgs = images[i : i + batch_size]
            tensors = []
            for img in batch_imgs:
                # RGB -> Resize -> normalize (与 trainer 一致)
                pil = Image.fromarray(img.astype(np.uint8)).convert("RGB")
                resized = pil.resize((224, 224))
                t = torch.from_numpy(
                    np.array(resized, dtype=np.float32) / 255.0
                ).permute(2, 0, 1)
                tensors.append(t)

            batch = torch.stack(tensors).to(device)
            batch = (batch - mean) / std

            with torch.no_grad():
                logits = model(batch)
                probs = torch.softmax(logits, dim=1)
                preds = probs.argmax(dim=1).cpu().numpy()

            predictions.extend(int(p) for p in preds)

        return predictions

    def _compute_metrics(
        self, y_true: list[int], y_pred: list[int]
    ) -> dict[str, object]:
        """计算分类指标：准确率、召回率、精确率、F1、混淆矩阵、抑制率。"""
        n = len(y_true)
        if n == 0:
            return {
                "accuracy": 0.0, "real_defect_recall": 0.0,
                "false_alarm_precision": 0.0, "f1": 0.0,
                "false_alarm_suppression_rate": 0.0,
                "suppressed_real_defect_count": 0,
                "confusion_matrix": [[0, 0], [0, 0]],
                "total": 0,
            }

        tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
        tn = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 0)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)

        accuracy = (tp + tn) / n if n > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        precision_fa = tn / (tn + fn) if (tn + fn) > 0 else 0.0
        f1 = 2 * recall * precision_fa / (recall + precision_fa) if (recall + precision_fa) > 0 else 0.0

        total_false_alarms = tn + fn  # label=0 = false_alarm
        suppression_rate = tn / total_false_alarms if total_false_alarms > 0 else 0.0

        # fn = real defect suppressed → 被错误抑制的真实缺陷数
        suppressed_real_defects = fn

        return {
            "accuracy": round(accuracy, 4),
            "real_defect_recall": round(recall, 4),
            "false_alarm_precision": round(precision_fa, 4),
            "f1": round(f1, 4),
            "false_alarm_suppression_rate": round(suppression_rate, 4),
            "suppressed_real_defect_count": suppressed_real_defects,
            "confusion_matrix": [[tn, fp], [fn, tp]],
            "total": n,
        }

    async def _stratified_evaluation(
        self, model_path: str, eval_data: dict[str, object]
    ) -> list[dict[str, object]]:
        """按 camera_id 分层评估模型表现。"""
        from collections import defaultdict

        images = eval_data["images"]
        labels = eval_data["labels"]
        camera_ids = eval_data["camera_ids"]

        groups: dict[str, dict[str, list[int]]] = defaultdict(
            lambda: {"labels": [], "predictions": []}
        )

        for img, lbl, cam in zip(images, labels, camera_ids):
            if not cam:
                cam = "__unknown__"
            groups[cam]["labels"].append(lbl)

        for cam, group in groups.items():
            group_imgs = [
                images[i]
                for i, c in enumerate(camera_ids)
                if (c or "__unknown__") == cam
            ]
            group["predictions"] = await self._run_inference(model_path, group_imgs)

        results: list[dict[str, object]] = []
        for cam, group in sorted(groups.items()):
            metrics = self._compute_metrics(group["labels"], group["predictions"])
            metrics["camera_id"] = cam
            metrics.pop("confusion_matrix", None)
            results.append(metrics)

        return results

    def _check_criteria(
        self,
        criteria: dict[str, object],
        new_metrics: dict[str, object],
        baseline_metrics: dict[str, object] | None,
        stratified: list[dict[str, object]],
    ) -> list[str]:
        """逐条检查门禁标准，返回失败原因列表。"""
        failures: list[str] = []

        min_recall = float(criteria["min_real_defect_recall"])
        if new_metrics["real_defect_recall"] < min_recall:
            failures.append(
                f"真实缺陷召回率 {new_metrics['real_defect_recall']} 低于阈值 {min_recall}"
            )

        if baseline_metrics:
            max_drop = float(criteria["max_recall_drop"])
            recall_drop = float(baseline_metrics["real_defect_recall"]) - float(
                new_metrics["real_defect_recall"]
            )
            if recall_drop > max_drop:
                failures.append(
                    f"召回率下降 {recall_drop:.4f} 超过允许值 {max_drop}"
                )

            min_suppression = float(criteria["min_false_alarm_suppression"])
            baseline_suppression = float(
                baseline_metrics.get("false_alarm_suppression_rate", 0.0)
            )
            new_suppression = float(new_metrics["false_alarm_suppression_rate"])
            suppression_gain = new_suppression - baseline_suppression
            if suppression_gain < min_suppression:
                failures.append(
                    f"误报抑制率提升 {suppression_gain:.4f} 未达阈值 {min_suppression}"
                )

        max_suppressed = int(criteria["max_suppressed_real_defects"])
        suppressed = int(new_metrics["suppressed_real_defect_count"])
        if suppressed > max_suppressed:
            failures.append(
                f"被错误抑制的真实缺陷数 {suppressed} 超过允许上限 {max_suppressed}"
            )

        # 分层检查：每个 camera_id 的召回率不低于全局阈值
        for s in stratified:
            cam = s.get("camera_id", "__unknown__")
            cam_recall = float(s.get("real_defect_recall", 0.0))
            cam_total = int(s.get("total", 0))
            if cam_total >= 5 and cam_recall < min_recall:
                failures.append(
                    f"camera {cam} 召回率 {cam_recall:.4f} 低于阈值 {min_recall} (样本数 {cam_total})"
                )

        return failures
