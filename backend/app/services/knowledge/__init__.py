from __future__ import annotations

import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.logging import get_logger
from app.core.security import generate_uuid
from app.models.knowledge import KnowledgeEntry
from app.repositories.knowledge import KnowledgeRepository

logger = get_logger(__name__)


class KnowledgeService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = KnowledgeRepository(session)

    async def create_entry(
        self,
        *,
        category: str,
        title: str,
        description: str | None = None,
        cluster_id: str | None = None,
        defect_type: str | None = None,
        action: str = "ignore",
        camera_ids: list[str] | None = None,
        vlm_analysis_json: str | None = None,
        example_image_paths: list[str] | None = None,
    ) -> KnowledgeEntry:
        entry = KnowledgeEntry(
            id=generate_uuid(),
            cluster_id=cluster_id,
            category=category,
            defect_type=defect_type,
            title=title,
            description=description,
            vlm_analysis_json=vlm_analysis_json,
            action=action,
            camera_ids=json.dumps(camera_ids) if camera_ids else None,
            example_image_paths=json.dumps(example_image_paths) if example_image_paths else None,
        )
        result = await self._repo.create(entry)
        logger.info(
            "knowledge_entry_created",
            knowledge_id=result.id,
            category=category,
            title=title,
        )
        return result

    async def auto_generate_from_review(
        self,
        *,
        cluster_id: str,
        review_action: str,
        defect_type: str | None,
        camera_ids: list[str] | None = None,
    ) -> KnowledgeEntry | None:
        if review_action == "mark_false_alarm":
            return await self.create_entry(
                category="false_alarm",
                title=f"False alarm pattern from cluster {cluster_id[:8]}",
                description="Automatically generated from engineer review: marked as false alarm",
                cluster_id=cluster_id,
                action="ignore",
                camera_ids=camera_ids,
            )

        if review_action == "confirm_defect" and defect_type:
            return await self.create_entry(
                category="defect",
                defect_type=defect_type,
                title=f"{defect_type} defect from cluster {cluster_id[:8]}",
                description="Automatically generated from engineer review: confirmed defect",
                cluster_id=cluster_id,
                action="NG",
                camera_ids=camera_ids,
            )

        return None

    async def get_entry(self, knowledge_id: str) -> KnowledgeEntry | None:
        return await self._repo.get_by_id(knowledge_id)

    async def list_by_cluster(self, cluster_id: str) -> list[KnowledgeEntry]:
        result = await self._repo.get_by_cluster(cluster_id)
        return list(result)

    async def list_entries(
        self,
        *,
        category: str | None = None,
        defect_type: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[KnowledgeEntry], int]:
        if category:
            entries = await self._repo.get_by_category(category, offset=offset, limit=limit)
            total = await self._repo.count(category=category)
        elif defect_type:
            entries = await self._repo.get_by_defect_type(defect_type, offset=offset, limit=limit)
            total = await self._repo.count(defect_type=defect_type)
        else:
            entries = await self._repo.list_all(offset=offset, limit=limit)
            total = await self._repo.count()
        return list(entries), total

    async def search(self, keyword: str, *, limit: int = 20) -> list[KnowledgeEntry]:
        result = await self._repo.search(keyword, limit=limit)
        return list(result)

    async def update_entry(
        self,
        knowledge_id: str,
        *,
        title: str | None = None,
        description: str | None = None,
        action: str | None = None,
    ) -> KnowledgeEntry | None:
        entry = await self._repo.get_by_id(knowledge_id)
        if entry is None:
            return None
        if title is not None:
            entry.title = title
        if description is not None:
            entry.description = description
        if action is not None:
            entry.action = action
        await self._repo.update(entry)
        return entry

    async def delete_entry(self, knowledge_id: str) -> None:
        await self._repo.soft_delete(knowledge_id)
