from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.embedding import EmbeddingVector
from app.repositories.base import BaseRepository


class EmbeddingRepository(BaseRepository[EmbeddingVector]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, EmbeddingVector)

    async def get_by_anomaly_id(
        self, anomaly_id: str
    ) -> EmbeddingVector | None:
        stmt = select(EmbeddingVector).where(
            EmbeddingVector.deleted_at.is_(None),
            EmbeddingVector.anomaly_id == anomaly_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_similar(
        self,
        query_vector: list[float],
        *,
        top_k: int = 20,
        threshold: float = 0.7,
    ) -> list[dict[str, object]]:
        stmt = text("""
            SELECT ev.id AS embedding_id,
                   ev.anomaly_id,
                   ev.model_name,
                   ev.model_version,
                   ev.dimension,
                   1 - (ev.embedding <=> :query_vec) AS similarity
            FROM embedding_vectors ev
            WHERE ev.deleted_at IS NULL
              AND 1 - (ev.embedding <=> :query_vec) >= :threshold
            ORDER BY ev.embedding <=> :query_vec
            LIMIT :top_k
        """)
        result = await self._session.execute(
            stmt,
            {
                "query_vec": query_vector,
                "threshold": threshold,
                "top_k": top_k,
            },
        )
        return [dict(row._mapping) for row in result]

    async def find_similar_by_anomaly(
        self,
        anomaly_id: str,
        *,
        top_k: int = 20,
        threshold: float = 0.7,
    ) -> list[dict[str, object]]:
        source = await self.get_by_anomaly_id(anomaly_id)
        if source is None:
            return []
        return await self.find_similar(
            query_vector=source.embedding,
            top_k=top_k,
            threshold=threshold,
        )

    async def get_batch(
        self, anomaly_ids: list[str]
    ) -> Sequence[EmbeddingVector]:
        stmt = select(EmbeddingVector).where(
            EmbeddingVector.deleted_at.is_(None),
            EmbeddingVector.anomaly_id.in_(anomaly_ids),
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_all_embeddings_with_ids(
        self,
    ) -> list[tuple[str, list[float]]]:
        stmt = select(EmbeddingVector).where(
            EmbeddingVector.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        return [(row.anomaly_id, row.embedding) for row in result.scalars().all()]

    async def get_embeddings_excluding_reviewed(
        self,
    ) -> list[tuple[str, list[float]]]:
        """获取所有非 reviewed 状态的 anomaly 的 embedding，用于图谱构建等全量场景。"""
        from app.models.anomaly import AnomalyRecord

        stmt = (
            select(EmbeddingVector)
            .join(AnomalyRecord, EmbeddingVector.anomaly_id == AnomalyRecord.id)
            .where(
                EmbeddingVector.deleted_at.is_(None),
                AnomalyRecord.deleted_at.is_(None),
                AnomalyRecord.status != "reviewed",
            )
        )
        result = await self._session.execute(stmt)
        return [(row.anomaly_id, row.embedding) for row in result.scalars().all()]

    async def get_embeddings_for_clustering(
        self,
    ) -> list[tuple[str, list[float]]]:
        """获取待聚类的 anomaly embedding：仅包含 embedded（新嵌入）和 noise（未成簇）状态。

        已聚类的 anomaly（status='clustered'）不应被重新打散，因此排除在外。
        """
        from app.models.anomaly import AnomalyRecord

        stmt = (
            select(EmbeddingVector)
            .join(AnomalyRecord, EmbeddingVector.anomaly_id == AnomalyRecord.id)
            .where(
                EmbeddingVector.deleted_at.is_(None),
                AnomalyRecord.deleted_at.is_(None),
                AnomalyRecord.status.in_(["embedded", "noise"]),
            )
        )
        result = await self._session.execute(stmt)
        return [(row.anomaly_id, row.embedding) for row in result.scalars().all()]
