from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cluster import Cluster, ClusterMembership
from app.repositories.base import BaseRepository


class ClusterRepository(BaseRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Cluster)

    async def get_by_label(self, hdbscan_label: int) -> Cluster | None:
        stmt = select(Cluster).where(
            Cluster.deleted_at.is_(None),
            Cluster.hdbscan_label == hdbscan_label,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_status(
        self,
        status: str,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> Sequence[Cluster]:
        return await self.list_all(status=status, offset=offset, limit=limit)

    async def get_pending_review(
        self, *, offset: int = 0, limit: int = 20
    ) -> Sequence[Cluster]:
        return await self.get_by_status("pending_review", offset=offset, limit=limit)

    async def update_review(
        self,
        cluster_id: str,
        *,
        review_status: str,
        defect_type: str | None = None,
        reviewed_by: str,
        name: str | None = None,
    ) -> None:
        values: dict[str, object] = {
            "review_status": review_status,
            "defect_type": defect_type,
            "reviewed_by": reviewed_by,
            "status": "reviewed",
        }
        if name is not None:
            values["name"] = name

        from datetime import datetime, timezone

        stmt = (
            update(Cluster)
            .where(Cluster.id == cluster_id)
            .values(
                reviewed_at=datetime.now(tz=timezone.utc),
                **values,
            )
        )
        await self._session.execute(stmt)

    async def get_clusters_by_run(
        self, clustering_run_at: str, *, offset: int = 0, limit: int = 100
    ) -> Sequence[Cluster]:
        stmt = (
            select(Cluster)
            .where(
                Cluster.deleted_at.is_(None),
                Cluster.clustering_run_at >= clustering_run_at,
            )
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()


    async def update_fields(self, cluster_id: str, **values: object) -> None:
        stmt = update(Cluster).where(Cluster.id == cluster_id).values(**values)
        await self._session.execute(stmt)


class ClusterMembershipRepository(BaseRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, ClusterMembership)

    async def get_by_cluster(
        self, cluster_id: str
    ) -> Sequence[ClusterMembership]:
        stmt = select(ClusterMembership).where(
            ClusterMembership.deleted_at.is_(None),
            ClusterMembership.cluster_id == cluster_id,
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_anomaly_ids_by_cluster(
        self, cluster_id: str
    ) -> list[str]:
        memberships = await self.get_by_cluster(cluster_id)
        return [m.anomaly_id for m in memberships]

    async def bulk_create(
        self, memberships: list[ClusterMembership]
    ) -> list[ClusterMembership]:
        return await self.create_all(memberships)

    async def get_cluster_ids_by_anomaly(
        self, anomaly_id: str
    ) -> list[str]:
        """获取 anomaly 所属的 cluster ID 列表（通常只有 0 或 1 个）。"""
        stmt = select(ClusterMembership.cluster_id).where(
            ClusterMembership.deleted_at.is_(None),
            ClusterMembership.anomaly_id == anomaly_id,
        )
        result = await self._session.execute(stmt)
        return [row[0] for row in result.all()]

    async def move_memberships(
        self,
        *,
        source_cluster_id: str,
        target_cluster_id: str,
        anomaly_ids: list[str],
    ) -> int:
        if not anomaly_ids:
            return 0

        stmt = (
            update(ClusterMembership)
            .where(
                ClusterMembership.deleted_at.is_(None),
                ClusterMembership.cluster_id == source_cluster_id,
                ClusterMembership.anomaly_id.in_(anomaly_ids),
            )
            .values(cluster_id=target_cluster_id)
        )
        result = await self._session.execute(stmt)
        return int(result.rowcount or 0)
