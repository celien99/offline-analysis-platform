from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.graph import GraphBuildRecord, SimilarityEdge
from app.repositories.base import BaseRepository


class GraphRepository(BaseRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, SimilarityEdge)

    async def get_neighbors(
        self, anomaly_id: str, *, k: int = 10
    ) -> Sequence[SimilarityEdge]:
        stmt = (
            select(SimilarityEdge)
            .where(
                SimilarityEdge.deleted_at.is_(None),
                SimilarityEdge.source_anomaly_id == anomaly_id,
            )
            .order_by(SimilarityEdge.rank)
            .limit(k)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_bidirectional_neighbors(
        self, anomaly_id: str, *, k: int = 10
    ) -> Sequence[SimilarityEdge]:
        """获取双向邻居（A→B 和 B→A 的边）"""
        stmt = (
            select(SimilarityEdge)
            .where(
                SimilarityEdge.deleted_at.is_(None),
                (
                    (SimilarityEdge.source_anomaly_id == anomaly_id)
                    | (SimilarityEdge.target_anomaly_id == anomaly_id)
                ),
            )
            .order_by(SimilarityEdge.similarity_score.desc())
            .limit(k * 2)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def clear_all_edges(self) -> None:
        """清空所有边（重建图谱时使用）"""
        stmt = delete(SimilarityEdge)
        await self._session.execute(stmt)
        await self._session.flush()

    async def bulk_create_edges(self, edges: list[SimilarityEdge]) -> int:
        await self._session.add_all(edges)
        await self._session.flush()
        return len(edges)

    async def get_edge_count(self) -> int:
        stmt = select(SimilarityEdge).where(SimilarityEdge.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        return len(result.scalars().all())


class GraphBuildRecordRepository(BaseRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, GraphBuildRecord)

    async def get_latest_build(self) -> GraphBuildRecord | None:
        stmt = (
            select(GraphBuildRecord)
            .where(GraphBuildRecord.deleted_at.is_(None))
            .order_by(GraphBuildRecord.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
