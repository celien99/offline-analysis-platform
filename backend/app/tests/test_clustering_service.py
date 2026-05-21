from __future__ import annotations

import numpy as np
import pytest

from app.domain.clustering import ClusterConfig


def test_cluster_config_defaults() -> None:
    cfg = ClusterConfig()
    assert cfg.umap_n_components == 2
    assert cfg.hdbscan_min_cluster_size == 10
    assert cfg.hdbscan_min_samples == 5


def test_cluster_config_custom() -> None:
    cfg = ClusterConfig(
        hdbscan_min_cluster_size=20,
        hdbscan_min_samples=10,
        umap_n_neighbors=30,
    )
    assert cfg.hdbscan_min_cluster_size == 20
    assert cfg.hdbscan_min_samples == 10
    assert cfg.umap_n_neighbors == 30
