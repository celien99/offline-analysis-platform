from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.logging import get_logger
from app.core.exceptions import NotFoundError
from app.core.security import generate_uuid
from app.models.registry import ModelVersion
from app.repositories.anomaly.repository import AnomalyRepository
from app.repositories.cluster.repository import ClusterMembershipRepository, ClusterRepository
from app.repositories.registry.model_version import ModelVersionRepository

logger = get_logger(__name__)


class TrainingService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._anomaly_repo = AnomalyRepository(session)
        self._cluster_repo = ClusterRepository(session)
        self._model_version_repo = ModelVersionRepository(session)

    async def prepare_training_data(
        self,
        *,
        anomaly_ids: list[str] | None = None,
    ) -> dict[str, list[str]]:
        training_data: dict[str, list[str]] = {
            "real_defect": [],
            "false_alarm": [],
        }

        reviewed_clusters = await self._cluster_repo.get_by_status(
            "reviewed", offset=0, limit=10000
        )

        membership_repo = ClusterMembershipRepository(self._session)

        for cluster in reviewed_clusters:
            if cluster.review_status in ("real_defect", "false_alarm"):
                label = cluster.review_status
                anomaly_ids_in_cluster = (
                    await membership_repo.get_anomaly_ids_by_cluster(cluster.id)
                )
                training_data[label].extend(anomaly_ids_in_cluster)

        if anomaly_ids:
            training_data["real_defect"] = [
                aid for aid in training_data["real_defect"] if aid in anomaly_ids
            ]
            training_data["false_alarm"] = [
                aid for aid in training_data["false_alarm"] if aid in anomaly_ids
            ]

        logger.info(
            "training_data_prepared",
            real_defect_count=len(training_data["real_defect"]),
            false_alarm_count=len(training_data["false_alarm"]),
        )
        return training_data

    async def create_model_version(
        self,
        model_name: str,
        version: str,
        model_type: str,
        artifact_path: str,
        metrics: dict[str, float] | None = None,
        mlflow_run_id: str | None = None,
    ) -> ModelVersion:
        model = ModelVersion(
            id=generate_uuid(),
            model_name=model_name,
            version=version,
            model_type=model_type,
            framework="pytorch",
            artifact_path=artifact_path,
            metrics_json=json.dumps(metrics) if metrics else None,
            mlflow_run_id=mlflow_run_id,
            trained_at=datetime.now(tz=timezone.utc),
            status="registered",
        )
        return await self._model_version_repo.create(model)

    async def get_model(self, model_name: str, version: str) -> ModelVersion:
        model = await self._model_version_repo.get_by_name_and_version(
            model_name, version
        )
        if model is None:
            raise NotFoundError("ModelVersion", f"{model_name}:{version}")
        return model

    async def list_models(
        self,
        *,
        model_type: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[ModelVersion], int]:
        return await self._model_version_repo.list_by_type(
            model_type=model_type, offset=offset, limit=limit
        )
