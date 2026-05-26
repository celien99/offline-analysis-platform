from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class ClusterConfig:
    umap_n_components: int = 2
    umap_n_neighbors: int = 15
    umap_min_dist: float = 0.1
    hdbscan_min_cluster_size: int = 10
    hdbscan_min_samples: int = 5
    hdbscan_metric: str = "euclidean"


@dataclass
class ClusterResult:
    cluster_id: str
    label: int
    sample_count: int
    representative_ids: list[str]
    centroid: list[float] | None = None
    umap_x: float | None = None
    umap_y: float | None = None
    probability: float | None = None
    possible_type: str | None = None
    status: str = "pending_review"
    seat_model_id: str | None = None
    camera_id: str | None = None
    region_id: str | None = None


@dataclass
class ClusteringResult:
    clusters: list[ClusterResult]
    noise_count: int
    total_samples: int
    parameters: ClusterConfig
    run_at: datetime
