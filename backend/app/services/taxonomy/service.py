from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from typing import Any

from app.common.logging import get_logger
from app.core.security import generate_uuid
from app.domain.taxonomy.entities import TaxonomyNode, TaxonomyStats, TaxonomyTree
from app.models.knowledge import KnowledgeEntry
from app.models.taxonomy import DefectTreeNode
from app.repositories.taxonomy import TaxonomyRepository

logger = get_logger(__name__)

# 预设缺陷分类树结构
DEFAULT_TAXONOMY = {
    "表面缺陷": {
        "description": "座椅表面可见缺陷",
        "defect_type": None,
        "children": {
            "褶皱": {"description": "皮面/布面褶皱变形", "defect_type": "wrinkle", "children": {}},
            "划痕": {"description": "表面划伤痕迹", "defect_type": "scratch", "children": {}},
            "污渍": {"description": "油污/色斑等污染", "defect_type": "stain", "children": {}},
            "破损": {"description": "破洞/撕裂/磨损", "defect_type": None, "children": {
                "破洞": {"description": "贯穿性破损", "defect_type": "hole", "children": {}},
                "撕裂": {"description": "线性撕裂口", "defect_type": "tear", "children": {}},
                "磨损": {"description": "表面材质磨损", "defect_type": "abrasion", "children": {}},
            }},
        },
    },
    "缝线缺陷": {
        "description": "缝线/接缝相关问题",
        "defect_type": None,
        "children": {
            "缝线偏移": {"description": "缝线偏离标准位置", "defect_type": "seam_shift", "children": {}},
            "跳针": {"description": "缝线缺失/跳针", "defect_type": "skip_stitch", "children": {}},
            "线头": {"description": "多余线头未清理", "defect_type": "loose_thread", "children": {}},
        },
    },
    "结构缺陷": {
        "description": "座椅结构/装配问题",
        "defect_type": None,
        "children": {
            "变形": {"description": "座椅结构变形", "defect_type": "deformation", "children": {}},
            "装配不良": {"description": "部件装配不到位", "defect_type": "assembly_issue", "children": {}},
            "异物": {"description": "非座椅材质的异物混入", "defect_type": "foreign_object", "children": {}},
        },
    },
    "光学异常": {
        "description": "光照/反射造成的检测干扰",
        "defect_type": None,
        "children": {
            "反光": {"description": "表面反光导致的误检", "defect_type": "reflection", "children": {}},
            "阴影": {"description": "光照不均造成的阴影干扰", "defect_type": "shadow", "children": {}},
        },
    },
}


class TaxonomyService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = TaxonomyRepository(session)

    # ── 初始化默认分类树 ──────────────────────────────────

    async def init_default_taxonomy(self) -> int:
        """初始化预设分类树，返回创建的节点数"""
        existing = await self._repo.get_all_nodes()
        if existing:
            logger.info("taxonomy_already_initialized", count=len(existing))
            return 0
        count = await self._create_subtree(None, DEFAULT_TAXONOMY, level=0)
        logger.info("taxonomy_initialized", node_count=count)
        return count

    async def _create_subtree(
        self, parent_id: str | None, tree: dict[str, Any], level: int
    ) -> int:
        count = 0
        for name, config in tree.items():
            node = DefectTreeNode(
                id=generate_uuid(),
                name=name,
                parent_id=parent_id,
                level=level,
                description=config.get("description"),
                defect_type=config.get("defect_type"),
            )
            await self._repo.create(node)
            count += 1
            children = config.get("children", {})
            if children:
                count += await self._create_subtree(node.id, children, level + 1)
        return count

    # ── CRUD ─────────────────────────────────────────────

    async def create_node(
        self,
        *,
        name: str,
        parent_id: str | None = None,
        level: int = 0,
        description: str | None = None,
        defect_type: str | None = None,
        icon: str | None = None,
    ) -> DefectTreeNode:
        existing = await self._repo.get_by_name(name)
        if existing is not None:
            from app.core.exceptions import ConflictError
            raise ConflictError(f"节点 '{name}' 已存在")

        node = DefectTreeNode(
            id=generate_uuid(),
            name=name,
            parent_id=parent_id,
            level=level,
            description=description,
            defect_type=defect_type,
            icon=icon,
        )
        result = await self._repo.create(node)
        logger.info("taxonomy_node_created", node_id=result.id, name=name)
        return result

    async def update_node(
        self,
        node_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        defect_type: str | None = None,
        icon: str | None = None,
    ) -> DefectTreeNode | None:
        node = await self._repo.get_by_id(node_id)
        if node is None:
            return None
        if name is not None:
            node.name = name
        if description is not None:
            node.description = description
        if defect_type is not None:
            node.defect_type = defect_type
        if icon is not None:
            node.icon = icon
        await self._repo.update(node)
        logger.info("taxonomy_node_updated", node_id=node_id)
        return node

    async def delete_node(self, node_id: str) -> None:
        children = await self._repo.get_children(node_id)
        for child in children:
            await self.delete_node(child.id)
        await self._repo.soft_delete(node_id)
        logger.info("taxonomy_node_deleted", node_id=node_id)

    # ── 查询 ─────────────────────────────────────────────

    async def get_tree(self) -> TaxonomyTree:
        nodes = await self._repo.get_all_nodes()
        if not nodes:
            return TaxonomyTree()

        node_map: dict[str, TaxonomyNode] = {}
        roots: list[TaxonomyNode] = []

        for n in nodes:
            tn = TaxonomyNode(
                id=n.id,
                name=n.name,
                parent_id=n.parent_id,
                level=n.level,
                description=n.description,
                defect_type=n.defect_type,
                icon=n.icon,
            )
            node_map[n.id] = tn

        for n in nodes:
            tn = node_map[n.id]
            if n.parent_id and n.parent_id in node_map:
                node_map[n.parent_id].children.append(tn)
            elif n.parent_id is None:
                roots.append(tn)

        return TaxonomyTree(roots=roots, total_nodes=len(nodes))

    async def get_node(self, node_id: str) -> DefectTreeNode | None:
        return await self._repo.get_by_id(node_id)

    async def get_node_with_stats(self, node_id: str) -> TaxonomyStats | None:
        """获取节点及其统计信息"""
        node = await self._repo.get_by_id(node_id)
        if node is None:
            return None
        return await self._build_stats(node)

    async def get_tree_stats(self) -> list[TaxonomyStats]:
        """获取整棵树的统计信息"""
        roots = await self._repo.get_roots()
        stats_list: list[TaxonomyStats] = []
        for root in roots:
            stats = await self._build_stats(root)
            stats_list.append(stats)
        return stats_list

    async def _build_stats(self, node: DefectTreeNode) -> TaxonomyStats:
        defect_type = node.defect_type
        anomaly_count = 0
        cluster_count = 0

        if defect_type:
            stmt = select(func.count()).select_from(KnowledgeEntry).where(
                KnowledgeEntry.deleted_at.is_(None),
                KnowledgeEntry.defect_type == defect_type,
            )
            result = await self._session.execute(stmt)
            anomaly_count = result.scalar_one()

        children = await self._repo.get_children(node.id)
        children_stats = []
        for child in children:
            cs = await self._build_stats(child)
            children_stats.append(cs)
            anomaly_count += cs.anomaly_count
            cluster_count += cs.cluster_count

        return TaxonomyStats(
            node_id=node.id,
            node_name=node.name,
            anomaly_count=anomaly_count,
            cluster_count=cluster_count,
            children_stats=children_stats,
        )

    # ── 自动分类 ─────────────────────────────────────────

    async def auto_classify(
        self, defect_type: str
    ) -> str | None:
        """根据 defect_type 字符串匹配最近的分类树节点，返回 node_id"""
        node = await self._repo.get_by_defect_type(defect_type)
        if node is not None:
            return node.id
        # 模糊匹配：名称包含关系
        all_nodes = await self._repo.get_all_nodes()
        for n in all_nodes:
            if n.defect_type and defect_type.lower() in n.defect_type.lower():
                return n.id
        return None

    async def link_knowledge_to_taxonomy(
        self, knowledge_id: str, taxonomy_node_id: str
    ) -> None:
        """将知识条目关联到分类树节点"""
        from app.repositories.knowledge import KnowledgeRepository
        knowledge_repo = KnowledgeRepository(self._session)
        entry = await knowledge_repo.get_by_id(knowledge_id)
        if entry is not None:
            entry.taxonomy_node_id = taxonomy_node_id
            await knowledge_repo.update(entry)
            logger.info(
                "knowledge_linked_to_taxonomy",
                knowledge_id=knowledge_id,
                taxonomy_node_id=taxonomy_node_id,
            )

    async def get_unclassified_entries(
        self, *, offset: int = 0, limit: int = 20
    ) -> list[KnowledgeEntry]:
        """获取未关联分类树的条目"""
        stmt = (
            select(KnowledgeEntry)
            .where(
                KnowledgeEntry.deleted_at.is_(None),
                KnowledgeEntry.taxonomy_node_id.is_(None),
            )
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
