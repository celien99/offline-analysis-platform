from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.taxonomy import DefectTreeNode
from app.repositories.base import BaseRepository


class TaxonomyRepository(BaseRepository[DefectTreeNode]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, DefectTreeNode)

    async def get_roots(self) -> Sequence[DefectTreeNode]:
        stmt = (
            select(DefectTreeNode)
            .where(
                DefectTreeNode.deleted_at.is_(None),
                DefectTreeNode.parent_id.is_(None),
            )
            .order_by(DefectTreeNode.name)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_children(self, parent_id: str) -> Sequence[DefectTreeNode]:
        stmt = (
            select(DefectTreeNode)
            .where(
                DefectTreeNode.deleted_at.is_(None),
                DefectTreeNode.parent_id == parent_id,
            )
            .order_by(DefectTreeNode.level, DefectTreeNode.name)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_all_nodes(self) -> Sequence[DefectTreeNode]:
        stmt = (
            select(DefectTreeNode)
            .where(DefectTreeNode.deleted_at.is_(None))
            .order_by(DefectTreeNode.level, DefectTreeNode.name)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_by_name(self, name: str) -> DefectTreeNode | None:
        stmt = select(DefectTreeNode).where(
            DefectTreeNode.deleted_at.is_(None),
            DefectTreeNode.name == name,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_defect_type(self, defect_type: str) -> DefectTreeNode | None:
        stmt = select(DefectTreeNode).where(
            DefectTreeNode.deleted_at.is_(None),
            DefectTreeNode.defect_type == defect_type,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_leaves(self) -> Sequence[DefectTreeNode]:
        """获取所有叶子节点（没有子节点的节点）"""
        all_nodes = await self.get_all_nodes()
        parent_ids = {
            n.parent_id for n in all_nodes if n.parent_id is not None
        }
        return [n for n in all_nodes if n.id not in parent_ids]

    async def get_ancestors(self, node_id: str) -> list[DefectTreeNode]:
        """获取从根到该节点的路径"""
        ancestors: list[DefectTreeNode] = []
        current = await self.get_by_id(node_id)
        visited: set[str] = set()
        while current is not None and current.parent_id is not None:
            if current.parent_id in visited:
                break
            visited.add(current.parent_id)
            parent = await self.get_by_id(current.parent_id)
            if parent is not None:
                ancestors.insert(0, parent)
                current = parent
            else:
                break
        return ancestors
