from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GraphNode:
    """图谱节点"""
    anomaly_id: str
    camera_id: str
    cluster_id: str | None
    cluster_name: str | None
    defect_type: str | None
    umap_x: float | None = None
    umap_y: float | None = None
    crop_url: str | None = None


@dataclass
class GraphEdge:
    """图谱边"""
    source_anomaly_id: str
    target_anomaly_id: str
    similarity_score: float
    rank: int


@dataclass
class GraphQueryResult:
    """图谱查询结果"""
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)


@dataclass
class Subgraph:
    """子图 — 包含中心节点和其邻居"""
    center_node: GraphNode
    neighbors: list[tuple[GraphNode, float]]  # (节点, 相似度)
    edges: list[GraphEdge]
