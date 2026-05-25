from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_prefix="INDUSTRIAL_",
    )

    # Application
    app_name: str = "industrial-ai-offline"
    app_version: str = "0.1.0"
    debug: bool = False
    environment: str = "development"
    cors_origins: list[str] = ["http://localhost:3000"]

    # PostgreSQL + pgvector
    postgres_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/anomaly_db"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "anomaly-data"
    minio_secure: bool = False

    # Celery
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # Embedding (DINOv2-S: 384-dim)
    embedding_dim: int = 384
    embedding_model: str = "dinov2_vits14"
    embedding_batch_size: int = 32

    # Clustering
    clustering_min_samples: int = 5
    clustering_min_cluster_size: int = 3
    umap_n_components: int = 2
    umap_n_neighbors: int = 15

    # VLM（支持任意 OpenAI 兼容的视觉模型 API）
    vlm_model: str = "qwen2.5-vl"
    vlm_endpoint: str = "http://localhost:8001/v1"
    vlm_api_key: str = ""

    # MLflow
    mlflow_tracking_uri: str = "http://localhost:5001"
    mlflow_artifact_root: str = "./mlruns"

    # File storage paths
    data_dir: Path = Path("./data")
    model_dir: Path = Path("./models")

    # 模型部署目标：目标名 -> 部署目录路径
    deploy_targets: dict[str, str] = {
        "production_line_a": "./deployed_models/line_a",
        "production_line_b": "./deployed_models/line_b",
    }
    deploy_model_subdir: str = "filter_classifier"
    deploy_rules_subdir: str = "rules"
    deploy_on_train_complete: bool = False
    default_deploy_target: str = "production_line_a"
    deploy_default_strategy: str = "immediate"  # immediate / shadow / canary
    deploy_canary_watch_seconds: int = 1800  # 金丝雀观察时长（秒）
    deploy_canary_min_samples: int = 100  # 金丝雀评估最小样本数
    deploy_canary_ng_rate_threshold: float = 0.05  # NG 率超此阈值自动回滚

    # Auto-training
    auto_train_enabled: bool = False
    auto_train_min_total_samples: int = 50  # 首次训练的最低总样本数
    auto_train_min_new_labels: int = 20     # 自上次训练以来的最低新标签数
    auto_train_check_interval_seconds: int = 3600  # 检查间隔（秒）
    auto_train_model_type: str = "mobilenet_v3_small"
    auto_train_batch_size: int = 32
    auto_train_epochs: int = 50

    # PatchCore Training
    patchcore_models_dir: Path = Path("./models/patchcore")

    # Inspection (seat_defect_core 子进程调用，训练与检测共用)
    seat_defect_core_python: str = "../seat_defect_core/.venv/bin/python"
    default_inspection_config: str = "../seat_defect_core/config.example.json"
    backend_base_url: str = "http://localhost:8000"  # 子进程回调上传 NG 异常的 API 地址

    # Pagination
    default_page_size: int = 20
    max_page_size: int = 100


settings = Settings()
