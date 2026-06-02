from __future__ import annotations

import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from app.common.logging import get_logger
from app.core.config import settings
from app.core.security import generate_uuid
from app.infrastructure.database.session import async_session_factory
from app.infrastructure.queue.celery_app import celery_app
from app.models.registry import ModelVersion
from app.repositories.registry.model_version import ModelVersionRepository
from app.workers import run_async

logger = get_logger(__name__)


@celery_app.task(name="patchcore_training.train_patchcore_model")
def train_patchcore_model(
    camera_id: str,
    config_json: str,
    good_image_paths: list[str],
) -> dict[str, object]:
    """Celery task: train a PatchCore model via seat_defect_core."""
    logger.info(
        "patchcore_training_started",
        camera_id=camera_id,
        image_count=len(good_image_paths),
    )

    tmp_config: str | None = None
    tmp_dir: str | None = None

    try:
        # 将配置写入临时文件
        tmp_dir = tempfile.mkdtemp(prefix="patchcore_training_")
        tmp_config = str(Path(tmp_dir) / "config.json")
        with open(tmp_config, "w", encoding="utf-8") as f:
            f.write(config_json)

        output_dir = settings.model_dir / "patchcore"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{camera_id}_patchcore_{datetime.now(tz=timezone.utc).strftime('%Y%m%d%H%M%S')}.npz"

        cmd = [
            settings.seat_defect_core_python,
            "-m", "seat_defect_core",
            "train-patchcore",
            "--config", tmp_config,
            "--camera-id", camera_id,
            "--good-images", good_image_paths[0] if len(good_image_paths) == 1 and Path(good_image_paths[0]).is_dir() else tmp_dir,
            "--output", str(output_path),
        ]

        # 如果传的是文件列表而非目录，需要把图片放到同一目录
        if not (len(good_image_paths) == 1 and Path(good_image_paths[0]).is_dir()):
            img_dir = Path(tmp_dir) / "images"
            img_dir.mkdir(exist_ok=True)
            import shutil
            for i, src in enumerate(good_image_paths):
                ext = Path(src).suffix or ".jpg"
                shutil.copy(src, img_dir / f"good_{i:04d}{ext}")
            cmd[cmd.index("--good-images") + 1] = str(img_dir)

        logger.info("patchcore_subprocess", cmd=" ".join(cmd))

        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)

        if proc.returncode != 0:
            logger.error("patchcore_subprocess_failed", stderr=proc.stderr[-2000:])
            return {"status": "failed", "error": proc.stderr[-1000:]}

        result = json.loads(proc.stdout.strip().split("\n")[-1])

        numeric_metrics = {
            "memory_bank_size": int(result.get("memory_bank_size", 0)),
            "total_embeddings": int(result.get("total_embeddings", 0)),
            "threshold": float(result.get("threshold", 0.0)),
        }

        model_version = run_async(_create_model_version(
            model_name=f"patchcore_{camera_id}",
            model_type="patchcore",
            artifact_path=str(output_path),
            metrics=numeric_metrics,
            mlflow_run_id=None,
        ))

        logger.info(
            "patchcore_training_complete",
            camera_id=camera_id,
            output_path=str(output_path),
            memory_bank_size=result.get("memory_bank_size"),
        )
        return {
            "status": "completed",
            "model_name": f"patchcore_{camera_id}",
            "camera_id": camera_id,
            "artifact_path": str(output_path),
            "metrics": numeric_metrics,
            "model_version_id": model_version.id,
            "model_version": model_version.version,
        }
    except subprocess.TimeoutExpired:
        logger.error("patchcore_training_timeout")
        return {"status": "failed", "error": "训练超时 (1800s)"}
    except Exception as e:
        logger.error("patchcore_training_failed", error=str(e))
        return {"status": "failed", "error": str(e)}
    finally:
        import shutil
        if tmp_dir is not None:
            shutil.rmtree(tmp_dir, ignore_errors=True)


async def _create_model_version(
    model_name: str,
    model_type: str,
    artifact_path: str,
    metrics: dict[str, float],
    mlflow_run_id: str | None = None,
) -> ModelVersion:
    async with async_session_factory() as session:
        model = ModelVersion(
            id=generate_uuid(),
            model_name=model_name,
            version=datetime.now(tz=timezone.utc).strftime("%Y%m%d%H%M%S"),
            model_type=model_type,
            framework="pytorch",
            artifact_path=artifact_path,
            metrics_json=json.dumps(metrics),
            mlflow_run_id=mlflow_run_id,
            trained_at=datetime.now(tz=timezone.utc),
            status="registered",
        )
        repo = ModelVersionRepository(session)
        await repo.create(model)
        await session.commit()
        return model
