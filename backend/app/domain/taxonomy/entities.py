from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TaxonomyNode:
    """缺陷分类树节点"""
    id: str
    name: str
    parent_id: str | None
    level: int
    description: str | None
    defect_type: str | None
    icon: str | None
    children: list[TaxonomyNode] = field(default_factory=list)
    anomaly_count: int = 0
    cluster_count: int = 0


@dataclass
class TaxonomyTree:
    """完整分类树"""
    roots: list[TaxonomyNode] = field(default_factory=list)
    total_nodes: int = 0


@dataclass
class TaxonomyStats:
    """分类树统计 — 各节点下的异常/聚类计数"""
    node_id: str
    node_name: str
    anomaly_count: int
    cluster_count: int
    children_stats: list[TaxonomyStats] = field(default_factory=list)
