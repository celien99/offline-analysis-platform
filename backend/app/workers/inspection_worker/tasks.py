from __future__ import annotations

import base64
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from app.common.logging import get_logger
from app.core.config import settings
from app.infrastructure.queue.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(name="inspection.run_inspection")
def run_inspection_task(
    config_path: str,
    camera_image_paths: dict[str, str],
    seat_model_id: str | None = None,
    part_id: str | None = None,
) -> dict[str, object]:
    """Celery 任务：通过子进程调用 seat_defect_core 执行检测。

    Args:
        config_path: 检测配置文件绝对路径（用于子进程 --config，相对路径以此为基准解析）。
        camera_image_paths: {camera_id: image_file_path} 映射。
        seat_model_id: 座椅型号 ID（可选）。
        part_id: 零件 ID（可选）。
    """
    logger.info(
        "inspection_started",
        seat_model_id=seat_model_id,
        camera_count=len(camera_image_paths),
    )

    tmp_dir: str | None = None

    try:
        # result.json 写入临时目录，配置文件直接使用原始路径（保证相对路径解析正确）
        tmp_dir = tempfile.mkdtemp(prefix="inspection_")
        result_path = str(Path(tmp_dir) / "result.json")

        # 仓库根目录：从当前文件位置推算（避免 venv symlink 干扰）
        # tasks.py -> inspection_worker -> workers -> app -> backend -> repo_root
        repo_root = Path(__file__).resolve().parent.parent.parent.parent.parent
        python_bin = str(repo_root / "seat_defect_core" / ".venv" / "bin" / "python")

        cmd = [
            python_bin, "-m", "seat_defect_core", "inspect",
            "--config", config_path,
            "--output", result_path,
            "--warmup",
            # 同步上传 NG 异常到离线平台，填充数据闭环
            "--upload", settings.backend_base_url,
        ]

        for camera_id, img_path in camera_image_paths.items():
            if Path(img_path).exists():
                cmd.extend(["--images", f"{camera_id}={img_path}"])

        if seat_model_id:
            cmd.extend(["--seat-model-id", seat_model_id])
        if part_id:
            cmd.extend(["--part-id", part_id])

        logger.info("inspection_subprocess", cmd=" ".join(cmd))

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
            cwd=str(repo_root),
        )

        if proc.returncode != 0:
            logger.error(
                "inspection_subprocess_failed",
                returncode=proc.returncode,
                stderr=proc.stderr[-2000:],
            )
            return {
                "status": "FAILURE",
                "error_message": proc.stderr[-1000:],
                "camera_results": [],
            }

        with open(result_path, "r", encoding="utf-8") as f:
            inspection_result = json.load(f)

        # 读取各机位叠加图像并 Base64 编码
        overlay_images: dict[str, str] = {}
        result_dir = Path(result_path).parent
        for camera_id in camera_image_paths:
            overlay_path = result_dir / f"{camera_id}_overlay.jpg"
            if overlay_path.exists():
                overlay_images[camera_id] = base64.b64encode(
                    overlay_path.read_bytes()
                ).decode("utf-8")

        camera_results = _extract_camera_results(inspection_result, overlay_images)
        overall_status = _extract_overall_status(inspection_result)

        logger.info("inspection_complete", overall_status=overall_status)

        # NG 结果上传成功后，触发离线分析 pipeline（embedding → clustering → VLM）
        if overall_status == "NG":
            from app.workers.pipeline_worker.tasks import process_new_anomalies
            pipeline_result = process_new_anomalies.delay(limit=500)
            logger.info(
                "pipeline_triggered_after_inspection",
                pipeline_task_id=pipeline_result.id,
            )

        return {
            "status": "SUCCESS",
            "overall_status": overall_status,
            "decision_reason": _extract_decision_reason(inspection_result),
            "camera_results": camera_results,
        }

    except subprocess.TimeoutExpired:
        logger.error("inspection_timeout")
        return {"status": "FAILURE", "error_message": "检测超时 (600s)", "camera_results": []}
    except Exception as e:
        logger.error("inspection_failed", error=str(e))
        return {"status": "FAILURE", "error_message": str(e), "camera_results": []}
    finally:
        # 清理临时文件（结果目录 + 图像目录）
        if tmp_dir is not None:
            try:
                shutil.rmtree(tmp_dir, ignore_errors=True)
            except Exception:
                pass
        # 清理 API 端保存的图像临时目录
        for img_path in camera_image_paths.values():
            img_dir = Path(img_path).parent
            if img_dir.exists():
                try:
                    shutil.rmtree(str(img_dir), ignore_errors=True)
                except Exception:
                    pass
                break  # 所有图像在同一目录，清理一次即可


def _extract_overall_status(result: dict) -> str | None:
    """从 seat_defect_core 返回结果中提取整体状态。"""
    resp = result.get("result", result)
    if isinstance(resp, dict):
        return resp.get("status") or resp.get("overall_status")
    return None


def _extract_decision_reason(result: dict) -> str | None:
    """从 seat_defect_core 返回结果中提取判定原因。"""
    resp = result.get("result", result)
    if isinstance(resp, dict):
        return resp.get("reason") or resp.get("decision_reason")
    return None


def _extract_camera_results(
    result: dict,
    overlay_images: dict[str, str] | None = None,
) -> list[dict[str, object]]:
    """从 seat_defect_core 返回结果中提取各相机检测结果。"""
    resp = result.get("result", result)
    if not isinstance(resp, dict):
        return []

    camera_results = resp.get("camera_results", [])
    if not camera_results:
        return []

    overlays = overlay_images or {}

    parsed: list[dict[str, object]] = []
    for cr in camera_results:
        cam_id = str(cr.get("camera_id", "unknown"))
        texture = cr.get("texture_result") or {}
        parsed.append({
            "camera_id": cam_id,
            "status": str(cr.get("status", "unknown")),
            "anomaly_score": float(texture.get("score", 0)) if texture else None,
            "threshold": float(texture.get("threshold", 0)) if texture else None,
            "is_anomaly": bool(texture.get("is_anomaly", False)) if texture else None,
            "decision_reason": str(cr.get("reason", "")),
            "error_message": str(cr.get("error", {}).get("message", "")) if cr.get("error") else None,
            "overlay_image_base64": overlays.get(cam_id),
        })
    return parsed
