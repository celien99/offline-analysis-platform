from __future__ import annotations

from pydantic import BaseModel, Field


class GraphNodeResponse(BaseModel):
    anomaly_id: str
    camera_id: str
    cluster_id: str | None
    cluster_name: str | None
    defect_type: str | None
    umap_x: float | None
    umap_y: float | None


class GraphEdgeResponse(BaseModel):
    source_anomaly_id: str
    target_anomaly_id: str
    similarity_score: float
    rank: int


class GraphQueryResultResponse(BaseModel):
    nodes: list[GraphNodeResponse] = []
    edges: list[GraphEdgeResponse] = []


class SubgraphResponse(BaseModel):
    center_node: GraphNodeResponse
    neighbors: list[NeighborWithScore] = []
    edges: list[GraphEdgeResponse] = []


class NeighborWithScore(BaseModel):
    node: GraphNodeResponse
    similarity_score: float


class GraphBuildStatusResponse(BaseModel):
    status: str
    total_anomalies: int = 0
    total_edges: int = 0
    current_edge_count: int = 0
    k_neighbors: int = 10
    error_message: str | None = None
    started_at: str | None = None
    completed_at: str | None = None


class BuildGraphRequest(BaseModel):
    k: int = Field(default=10, ge=1, le=50, description="每个节点的 K 近邻数")
    seat_model_id: str | None = Field(default=None, description="限定座椅型号")


class FindPathRequest(BaseModel):
    source_id: str = Field(...)
    target_id: str = Field(...)
    max_hops: int = Field(default=5, ge=1, le=10)
