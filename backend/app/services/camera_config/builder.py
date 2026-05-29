"""根据数据库配置生成完整的 seat_defect_core 检测配置 JSON。"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from app.models.camera_config import CameraConfig


class ConfigBuilder:
    """将 DB 中的相机配置与硬编码默认参数合并，生成完整配置 JSON。

    默认参数来自 seat_defect_core/config.example.json，仅暴露相机级的少量字段给用户配置，
    YOLO/ROI/EfficientAD/Filter/Rule 等底层参数使用代码内默认值。
    """

    DEFAULT_QUALITY = {
        "min_laplacian_variance": 80.0,
        "min_brightness_mean": 30.0,
        "max_brightness_mean": 225.0,
        "max_overexposed_ratio": 0.25,
        "max_underexposed_ratio": 0.35,
    }

    DEFAULT_DETECTION = {
        "target_class": "seat",
        "confidence": 0.25,
        "iou": 0.45,
        "device": "cpu",
        "imgsz": 960,
        "fill_segmentation_holes": True,
        "segmentation_hole_fill_max_area_ratio": 0.08,
    }

    DEFAULT_ROI = {
        "crop_expand_ratio": 0.02,
        "crop_shrink_ratio": 0.0,
        "mask_erode_pixels": 1,
        "edge_ignore_pixels": 4,
        "alignment": {"output_width": 256, "output_height": 256},
    }

    DEFAULT_EFFICIENTAD = {
        "device": "cpu",
        "input_size": 256,
        "teacher_backbone": "wide_resnet50_2",
        "student_backbone": "resnet18",
        "min_valid_pixel_ratio": 0.3,
        "image_threshold": 0.0,
        "pixel_threshold": 0.0,
    }

    DEFAULT_COLOR_BRANCH = {
        "enabled": False,
        "threshold_quantile": 0.99,
        "min_valid_pixel_ratio": 0.4,
    }

    DEFAULT_FILTER_CLASSIFIER = {
        "enabled": True,
        "model_path": "backend/deployed_models/line_a/filter_classifier/",
        "device": "cpu",
        "input_size": 224,
        "confidence_threshold": 0.5,
    }

    DEFAULT_RULE_ENGINE = {
        "enabled": False,
        "rules": [],
        "deployed_rules_path": "backend/deployed_models/line_a/rules/rules.json",
    }

    DEFAULT_PROPOSAL = {
        "heatmap_threshold_mode": "adaptive",
        "heatmap_adaptive_std_multiplier": 1.5,
        "min_component_area": 16,
        "max_proposals": 20,
        "context_padding_ratio": 0.10,
        "aggregation_method": "weighted_confidence",
        "budget": {
            "enabled": True,
            "target_latency_ms": 15.0,
            "hard_limit_ms": 20.0,
        },
    }

    DEFAULT_TRACKING = {
        "max_age": 30,
        "min_hits": 3,
        "iou_threshold": 0.3,
        "feature_similarity_threshold": 0.7,
    }

    DEFAULT_CALIBRATION = {
        "enabled": False,
        "camera_norm": {
            "enabled": True,
            "stats_path": "",
        },
        "projection": {
            "enabled": False,
            "projector_path": "",
        },
        "whitening": {
            "enabled": False,
            "matrix_path": "",
        },
        "ema_center": {
            "enabled": False,
            "centers_path": "",
        },
    }

    def __init__(self, repo_root: str | None = None) -> None:
        self._repo_root = (
            Path(repo_root)
            if repo_root
            else Path(__file__).resolve().parent.parent.parent.parent.parent
        )

    def build(
        self,
        seat_model_id: str,
        display_name: str,
        cameras: Sequence[CameraConfig],
        model_paths: dict[str, str],
        selected_camera_ids: list[str] | None = None,
        *,
        part_id: str = "seat_demo",
        upload_base_url: str = "http://localhost:8000",
        seat_yolo_path: str = "",
        projector_path: str = "",
        whitening_matrix_path: str = "",
    ) -> dict[str, object]:
        """生成完整的检测配置字典。

        Args:
            model_paths: model_version_id → artifact_path 的映射，由调用方从 model_versions 表查询。
        """
        selected_ids = set(selected_camera_ids) if selected_camera_ids else None

        resolved_yolo = self._resolve_path(seat_yolo_path) if seat_yolo_path else ""
        resolved_projector = self._resolve_path(projector_path) if projector_path else ""
        resolved_whitening = self._resolve_path(whitening_matrix_path) if whitening_matrix_path else ""

        camera_configs = []
        for cam in cameras:
            if selected_ids is not None and cam.camera_id not in selected_ids:
                continue
            camera_configs.append(self._build_camera_config(cam, model_paths, resolved_yolo))

        # 全局校准配置
        calibration: dict[str, object] = dict(self.DEFAULT_CALIBRATION)
        if resolved_projector:
            calibration["projection"] = {"enabled": True, "projector_path": resolved_projector}
        if resolved_whitening:
            calibration["whitening"] = {"enabled": True, "matrix_path": resolved_whitening}

        return {
            "seat_defect_inspection": {
                "part_id": part_id,
                "default_seat_model_id": seat_model_id,
                "output_json_path": "../outputs/seat_defect_inspection/results.json",
                "debug_dir": "../outputs/seat_defect_inspection/debug",
                "debug_artifacts_enabled": False,
                "debug_artifact_names": ["overlay"],
                "upload_base_url": upload_base_url,
                "fusion": {
                    "reject_on_any_reject": True,
                    "ng_strategy": "any",
                    "defect_overrides_reject": True,
                },
                "cameras": [],
                "seat_models": [
                    {
                        "seat_model_id": seat_model_id,
                        "display_name": display_name,
                        "cameras": camera_configs,
                    }
                ],
                "calibration": calibration,
            }
        }

    def _resolve_path(self, raw: str) -> str:
        """将相对路径转为绝对路径，使其在临时配置目录中也能正确解析。"""
        p = Path(raw)
        if p.is_absolute():
            return str(p)
        return str(self._repo_root / raw)

    def _resolve_model_path(
        self, model_version_id: str | None, model_paths: dict[str, str]
    ) -> str:
        """从 model_paths 映射中解析模型文件路径。"""
        if not model_version_id:
            return ""
        path = model_paths.get(model_version_id, "")
        return self._resolve_path(path) if path else ""

    def _build_camera_config(
        self, cam: CameraConfig, model_paths: dict[str, str], yolo_path: str = ""
    ) -> dict[str, object]:
        detection = dict(self.DEFAULT_DETECTION)
        detection["model_path"] = yolo_path
        detection["confidence"] = cam.detection_confidence

        efficientad = dict(self.DEFAULT_EFFICIENTAD)
        efficientad["input_size"] = cam.efficientad_image_size
        efficientad["image_threshold"] = cam.efficientad_threshold

        filter_classifier: dict[str, object] = dict(self.DEFAULT_FILTER_CLASSIFIER)
        filter_clf_path = self._resolve_model_path(
            cam.filter_classifier_model_version_id, model_paths
        )
        if filter_clf_path:
            filter_classifier["model_path"] = filter_clf_path
        else:
            filter_classifier["model_path"] = self._resolve_path(
                str(filter_classifier["model_path"])
            )

        rule_engine: dict[str, object] = dict(self.DEFAULT_RULE_ENGINE)
        deployed_rules = rule_engine.get("deployed_rules_path")
        if deployed_rules:
            rule_engine["deployed_rules_path"] = self._resolve_path(str(deployed_rules))

        proposal: dict[str, object] = dict(self.DEFAULT_PROPOSAL)
        tracking: dict[str, object] = dict(self.DEFAULT_TRACKING)
        calibration: dict[str, object] = dict(self.DEFAULT_CALIBRATION)

        # 每机位 CameraNormalizer stats 路径
        normalizer_path = self._resolve_model_path(
            cam.normalizer_model_version_id, model_paths
        )
        if normalizer_path:
            calibration["camera_norm"] = {
                "enabled": True,
                "stats_path": normalizer_path,
            }

        efficientad_path = self._resolve_model_path(
            cam.efficientad_model_version_id, model_paths
        )

        config: dict[str, object] = {
            "camera_id": cam.camera_id,
            "efficientad_model_path": efficientad_path,
            "source": "",
            "enabled": True,
            "color_insensitive_mode": True,
            "quality": dict(self.DEFAULT_QUALITY),
            "detection": detection,
            "roi": dict(self.DEFAULT_ROI),
            "efficientad": efficientad,
            "filter_classifier": filter_classifier,
            "rule_engine": rule_engine,
            "proposal": proposal,
            "track": tracking,
            "calibration": calibration,
        }

        return config
