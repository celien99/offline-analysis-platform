from __future__ import annotations

import json
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import KnowledgeEntry, RuleEntry
from app.repositories.base import BaseRepository


class KnowledgeRepository(BaseRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, KnowledgeEntry)

    async def get_by_cluster(self, cluster_id: str) -> Sequence[KnowledgeEntry]:
        stmt = (
            select(KnowledgeEntry)
            .where(
                KnowledgeEntry.deleted_at.is_(None),
                KnowledgeEntry.cluster_id == cluster_id,
            )
            .order_by(KnowledgeEntry.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_by_category(
        self,
        category: str,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> Sequence[KnowledgeEntry]:
        return await self.list_all(category=category, offset=offset, limit=limit)

    async def get_by_defect_type(
        self,
        defect_type: str,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> Sequence[KnowledgeEntry]:
        return await self.list_all(defect_type=defect_type, offset=offset, limit=limit)

    async def search(self, keyword: str, *, limit: int = 20) -> Sequence[KnowledgeEntry]:
        stmt = (
            select(KnowledgeEntry)
            .where(
                KnowledgeEntry.deleted_at.is_(None),
                (KnowledgeEntry.title.ilike(f"%{keyword}%"))
                | (KnowledgeEntry.description.ilike(f"%{keyword}%")),
            )
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()


class RuleRepository(BaseRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, RuleEntry)

    async def get_enabled_rules(self) -> Sequence[RuleEntry]:
        stmt = select(RuleEntry).where(
            RuleEntry.deleted_at.is_(None),
            RuleEntry.enabled.is_(True),
        ).order_by(RuleEntry.priority.desc())
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_disabled_rules(self) -> Sequence[RuleEntry]:
        stmt = select(RuleEntry).where(
            RuleEntry.deleted_at.is_(None),
            RuleEntry.enabled.is_(False),
        ).order_by(RuleEntry.priority.desc())
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_by_type(self, rule_type: str) -> Sequence[RuleEntry]:
        return await self.list_all(rule_type=rule_type, enabled=True)

    async def get_by_camera(self, camera_id: str) -> Sequence[RuleEntry]:
        stmt = select(RuleEntry).where(
            RuleEntry.deleted_at.is_(None),
            RuleEntry.enabled.is_(True),
        )
        result = await self._session.execute(stmt)
        rules = result.scalars().all()
        return [
            r for r in rules
            if r.camera_ids is None
            or camera_id in json.loads(r.camera_ids or "[]")
        ]
