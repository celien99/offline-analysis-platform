from __future__ import annotations

from pydantic import BaseModel, Field


class TaxonomyNodeCreateRequest(BaseModel):
    name: str = Field(..., max_length=128)
    parent_id: str | None = None
    level: int = Field(default=0, ge=0, le=10)
    description: str | None = None
    defect_type: str | None = None
    icon: str | None = None


class TaxonomyNodeUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    description: str | None = None
    defect_type: str | None = None
    icon: str | None = None


class TaxonomyNodeResponse(BaseModel):
    node_id: str
    name: str
    parent_id: str | None
    level: int
    description: str | None
    defect_type: str | None
    icon: str | None
    anomaly_count: int = 0
    children: list[TaxonomyNodeResponse] = []

    model_config = {"from_attributes": True}


class TaxonomyStatsResponse(BaseModel):
    node_id: str
    node_name: str
    anomaly_count: int
    cluster_count: int
    children_stats: list[TaxonomyStatsResponse] = []

    model_config = {"from_attributes": True}


class TaxonomyTreeResponse(BaseModel):
    roots: list[TaxonomyNodeResponse] = []
    total_nodes: int = 0


class AutoClassifyRequest(BaseModel):
    defect_type: str = Field(..., max_length=64)


class AutoClassifyResponse(BaseModel):
    defect_type: str
    matched_node_id: str | None
    matched_node_name: str | None


class LinkKnowledgeRequest(BaseModel):
    knowledge_id: str = Field(...)
    taxonomy_node_id: str = Field(...)
