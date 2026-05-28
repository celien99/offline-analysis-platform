"""Run seat_defect_core inspect on project sample images and save visual results."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import cv2
import numpy as np

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

CAMERA_IMAGE_STEMS = {
    "cam_back": "back",
    "cam_front": "front",
    "cam_left": "left",
    "cam_right": "right",
    "cam_top": "top",
}
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp")


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect sample_images with trained EfficientAD models.")
    parser.add_argument("--config", default="seat_defect_core/config.best.json", help="Base inspect config JSON.")
    parser.add_argument("--images-root", default="sample_images", help="Directory containing sample camera images.")
    parser.add_argument("--models-root", default="models", help="Directory containing *_efficientad.pt models.")
    parser.add_argument("--output-dir", default="outputs/inspect_sample", help="Directory for JSON and heatmaps.")
    parser.add_argument("--seat-model-id", default=None, help="Optional seat model id override.")
    parser.add_argument("--part-id", default="sample_inspect", help="Part id written to result JSON.")
    parser.add_argument("--warmup", action="store_true", help="Preload models before inspection.")
    args = parser.parse_args()

    workspace = WORKSPACE_ROOT
    config_path = _resolve_path(workspace, args.config)
    images_root = _resolve_path(workspace, args.images_root)
    models_root = _resolve_path(workspace, args.models_root)
    output_dir = _resolve_path(workspace, args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    yolo_config_dir = output_dir / "ultralytics_config"
    yolo_config_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("YOLO_CONFIG_DIR", str(yolo_config_dir))

    runtime_config = _build_runtime_config(
        config_path=config_path,
        config_dir=config_path.parent,
        models_root=models_root,
        output_dir=output_dir,
    )
    runtime_config_path = output_dir / "inspect_config.runtime.json"
    runtime_config_path.write_text(
        json.dumps(runtime_config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    image_paths = _collect_sample_images(images_root)
    if not image_paths:
        raise FileNotFoundError(f"No sample images found under {images_root}")

    from seat_defect_core.api import SeatDefectInspector

    inspector = SeatDefectInspector(runtime_config_path)
    if args.warmup:
        inspector.warmup(seat_model_id=args.seat_model_id)

    response, overlay_images = inspector.inspect_paths(
        image_paths,
        part_id=args.part_id,
        seat_model_id=args.seat_model_id,
    )

    result_json = output_dir / "result.json"
    result_json.write_text(
        json.dumps(response.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _save_visual_outputs(response, overlay_images, output_dir)
    _print_summary(response, output_dir)
    return 0


def _resolve_path(workspace: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else workspace / path


def _build_runtime_config(
    *,
    config_path: Path,
    config_dir: Path,
    models_root: Path,
    output_dir: Path,
) -> dict[str, Any]:
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    config = payload.get("seat_defect_inspection", payload)
    if not isinstance(config, dict):
        raise TypeError("Inspection config must be a JSON object.")

    config = dict(config)
    config["upload_base_url"] = ""
    config["output_json_path"] = str(output_dir / "result.core.json")
    config["debug_dir"] = str(output_dir / "debug")
    config["debug_artifacts_enabled"] = True
    config["debug_artifact_names"] = ["overlay"]

    for camera in _iter_cameras(config):
        camera_id = str(camera.get("camera_id", "")).strip()
        if not camera_id:
            continue
        model_path = models_root / f"{camera_id}_efficientad.pt"
        if not model_path.exists():
            raise FileNotFoundError(f"Missing EfficientAD model for {camera_id}: {model_path}")
        meta_path = model_path.with_suffix(".meta.json")
        if not meta_path.exists():
            print(f"warning: missing threshold metadata for {camera_id}: {meta_path}")
        camera["efficientad_model_path"] = str(model_path)
        efficientad = camera.get("efficientad")
        if isinstance(efficientad, dict):
            efficientad["model_path"] = str(model_path)
        detection = camera.get("detection")
        if isinstance(detection, dict) and isinstance(detection.get("model_path"), str):
            detection_path = _resolve_path(config_dir, detection["model_path"])
            if not detection_path.exists():
                raise FileNotFoundError(
                    f"Missing YOLO model for {camera_id}: {detection_path}. "
                    "Full inspect requires detection.model_path to exist locally."
                )
            detection["model_path"] = str(detection_path)

    return config


def _iter_cameras(config: dict[str, Any]) -> list[dict[str, Any]]:
    cameras: list[dict[str, Any]] = []
    for camera in config.get("cameras", []) or []:
        if isinstance(camera, dict):
            cameras.append(camera)
    for seat_model in config.get("seat_models", []) or []:
        if not isinstance(seat_model, dict):
            continue
        for camera in seat_model.get("cameras", []) or []:
            if isinstance(camera, dict):
                cameras.append(camera)
    return cameras


def _collect_sample_images(images_root: Path) -> dict[str, str]:
    image_paths: dict[str, str] = {}
    for camera_id, stem in CAMERA_IMAGE_STEMS.items():
        image_path = _first_existing_image(images_root, (camera_id, stem))
        if image_path is not None:
            image_paths[camera_id] = str(image_path)
    return image_paths


def _first_existing_image(root: Path, stems: tuple[str, ...]) -> Path | None:
    for stem in stems:
        for ext in IMAGE_EXTENSIONS:
            candidate = root / f"{stem}{ext}"
            if candidate.exists():
                return candidate
    return None


def _save_visual_outputs(response: Any, overlay_images: dict[str, Any], output_dir: Path) -> None:
    overlays_dir = output_dir / "overlays"
    heatmaps_dir = output_dir / "heatmaps"
    arrays_dir = output_dir / "arrays"
    overlays_dir.mkdir(parents=True, exist_ok=True)
    heatmaps_dir.mkdir(parents=True, exist_ok=True)
    arrays_dir.mkdir(parents=True, exist_ok=True)

    for camera_id, overlay in overlay_images.items():
        if overlay is not None:
            cv2.imwrite(str(overlays_dir / f"{camera_id}_overlay.png"), overlay)

    for camera_result in response.result.camera_results:
        texture = camera_result.texture_result
        if texture is None:
            continue
        if texture.heatmap is not None:
            heatmap = np.asarray(texture.heatmap, dtype=np.float32)
            cv2.imwrite(str(heatmaps_dir / f"{camera_result.camera_id}_heatmap.png"), _colorize_heatmap(heatmap))
        if texture.anomaly_map is not None:
            anomaly_map = np.asarray(texture.anomaly_map, dtype=np.float32)
            np.save(arrays_dir / f"{camera_result.camera_id}_anomaly_map.npy", anomaly_map)


def _colorize_heatmap(heatmap: np.ndarray) -> np.ndarray:
    if heatmap.size == 0:
        return np.zeros((1, 1, 3), dtype=np.uint8)
    h_min = float(np.nanmin(heatmap))
    h_max = float(np.nanmax(heatmap))
    if h_max > h_min:
        normalized = ((heatmap - h_min) / (h_max - h_min) * 255.0).clip(0, 255).astype(np.uint8)
    else:
        normalized = np.zeros_like(heatmap, dtype=np.uint8)
    return cv2.applyColorMap(normalized, cv2.COLORMAP_JET)


def _print_summary(response: Any, output_dir: Path) -> None:
    print(f"status={response.status} reason={response.decision_reason}")
    for camera_result in response.result.camera_results:
        texture = camera_result.texture_result
        if texture is None:
            error = camera_result.error.message.splitlines()[0] if camera_result.error else ""
            print(
                f"{camera_result.camera_id}: status={camera_result.status} "
                f"reason={camera_result.reason} error={error}"
            )
            continue
        print(
            f"{camera_result.camera_id}: status={camera_result.status} "
            f"reason={camera_result.reason} score={texture.score:.6f} "
            f"threshold={texture.threshold:.6f} anomaly={texture.is_anomaly}"
        )
    print(f"outputs={output_dir}")


if __name__ == "__main__":
    raise SystemExit(main())
