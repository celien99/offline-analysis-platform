from __future__ import annotations

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "industrial_ai_offline",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.infrastructure.queue.worker_init",  # 必须在 worker tasks 之前加载，注册子进程初始化信号
        "app.workers.embedding_worker.tasks",
        "app.workers.clustering_worker.tasks",
        "app.workers.deployment_worker.tasks",
        "app.workers.vlm_worker.tasks",
        "app.workers.training_worker.tasks",
        "app.workers.heatmap_worker.tasks",
        "app.workers.thumbnail_worker.tasks",
        "app.workers.maintenance_worker.tasks",
        "app.workers.pipeline_worker.tasks",
        "app.workers.efficientad_training_worker.tasks",
        "app.workers.inspection_worker.tasks",
        "app.workers.mask_refinement_worker.tasks",
        "app.workers.gate_worker.tasks",
        "app.workers.graph_worker.tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,
    task_soft_time_limit=3300,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
    beat_schedule={
        "regular-pipeline-every-6-hours": {
            "task": "pipeline.full_cycle",
            "schedule": 21600.0,
        },
        "cleanup-expired-data-daily": {
            "task": "maintenance.cleanup_expired",
            "schedule": 86400.0,
        },
        "auto-train-check": {
            "task": "training.check_and_auto_train",
            "schedule": 3600.0,
        },
    },
)
