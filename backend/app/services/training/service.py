from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.logging import get_logger
from app.core.exceptions import NotFoundError
from app.models.registry import ModelVersion
from app.repositories.anomaly.repository import AnomalyRepository
from app.repositories.cluster.repository import ClusterRepository

logger = get_logger(__name__)


class TrainingService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._anomaly_repo = AnomalyRepository(session)
        self._cluster_repo = ClusterRepository(session)

    async def prepare_training_data(
        self,
        *,
        anomaly_ids: list[str] | None = None,
    ) -> dict[str, list[str]]:
        """Collect labeled anomaly data for classifier training.

        Returns dict mapping label (real_defect / false_alarm) to list of anomaly IDs.
        """
        training_data: dict[str, list[str]] = {
            "real_defect": [],
            "false_alarm": [],
        }

        reviewed_clusters = await self._cluster_repo.get_by_status(
            "reviewed", offset=0, limit=10000
        )

        from app.repositories.cluster.repository import ClusterMembershipRepository
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
        from app.core.security import generate_uuid

        model = ModelVersion(
            id=generate_uuid(),
            model_name=model_name,
            version=version,
            model_type=model_type,
            framework="pytorch",
            artifact_path=artifact_path,
            metrics_json=str(metrics) if metrics else None,
            mlflow_run_id=mlflow_run_id,
            trained_at=datetime.now(tz=timezone.utc),
            status="registered",
        )
        self._session.add(model)
        await self._session.flush()
        return model

    async def get_model(self, model_name: str, version: str) -> ModelVersion:
        from sqlalchemy import select

        stmt = select(ModelVersion).where(
            ModelVersion.model_name == model_name,
            ModelVersion.version == version,
            ModelVersion.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
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
        from sqlalchemy import func, select

        stmt = select(ModelVersion).where(ModelVersion.deleted_at.is_(None))
        if model_type is not None:
            stmt = stmt.where(ModelVersion.model_type == model_type)
        stmt = stmt.offset(offset).limit(limit)

        result = await self._session.execute(stmt)
        models = list(result.scalars().all())

        count_stmt = select(func.count()).select_from(ModelVersion).where(
            ModelVersion.deleted_at.is_(None)
        )
        if model_type is not None:
            count_stmt = count_stmt.where(ModelVersion.model_type == model_type)
        total = await self._session.execute(count_stmt)

        return models, total.scalar_one()
