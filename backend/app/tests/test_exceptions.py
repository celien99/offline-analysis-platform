from __future__ import annotations

from app.core.exceptions import (
    AppError,
    ClusteringError,
    EmbeddingGenerationError,
    NotFoundError,
    TrainingError,
    VLMAnalysisError,
)


def test_base_app_error() -> None:
    err = AppError("test error", code="TEST_ERROR")
    assert err.message == "test error"
    assert err.code == "TEST_ERROR"


def test_not_found_error() -> None:
    err = NotFoundError("Anomaly", "abc123")
    assert "Anomaly" in err.message
    assert "abc123" in err.message
    assert err.code == "NOT_FOUND"


def test_embedding_error() -> None:
    err = EmbeddingGenerationError("GPU OOM")
    assert err.code == "EMBEDDING_ERROR"


def test_clustering_error() -> None:
    err = ClusteringError("Not enough samples")
    assert err.code == "CLUSTERING_ERROR"


def test_vlm_error() -> None:
    err = VLMAnalysisError("API timeout")
    assert err.code == "VLM_ERROR"


def test_training_error() -> None:
    err = TrainingError("Dataset too small")
    assert err.code == "TRAINING_ERROR"
