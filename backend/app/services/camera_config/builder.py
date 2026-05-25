"""根据数据库配置生成完整的 seat_defect_core 检测配置 JSON。"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from app.models.camera_config import CameraConfig


class ConfigBuilder:
    """将 DB 中的相机配置与硬编码默认参数合并，生成完整配置 JSON。

    默认参数来自 seat_defect_core/config.example.json，仅暴露相机级的少量字段给用户配置，
    YOLO/ROI/PatchCore/Filter/Color/Rule 等底层参数使用代码内默认值。
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

    DEFAULT_PATCHCORE = {
        "backend": "full",
        "image_size": 256,
        "patch_size": 32,
        "stride": 16,
        "max_memory": 1024,
        "backbone_name": "wide_resnet50_2",
        "feature_layers": ["layer2", "layer3"],
        "backbone_pretrained": True,
        "backbone_device": "cpu",
        "feature_pool_kernel_size": 3,
        "coreset_sampling_ratio": 0.1,
        "texture_input": "lab_l",
        "min_target_coverage": 0.6,
        "max_ignore_overlap": 0.1,
        "min_valid_patch_ratio": 0.4,
        "threshold_quantile": 0.99,
        "training_threshold_upper_quantile": 0.995,
        "decision_score_margin": 1.08,
        "strong_patch_score_ratio": 0.9,
        "min_strong_patch_count": 3,
        "min_strong_component_count": 2,
        "min_strong_patch_ratio": 0.015,
        "min_strong_component_ratio": 0.01,
        "critical_score_margin": 1.35,
        "critical_peak_score_margin": 1.45,
        "critical_min_component_patch_count": 2,
        "min_peak_component_patch_count": 1,
    }

    DEFAULT_COLOR_BRANCH = {
        "enabled": False,
        "threshold_quantile": 0.99,
        "min_valid_pixel_ratio": 0.4,
    }

    DEFAULT_FILTER_CLASSIFIER = {
        "enabled": True,
        "model_path": "../backend/deployed_models/line_a/filter_classifier/",
        "device": "cpu",
        "input_size": 224,
        "confidence_threshold": 0.5,
    }

    DEFAULT_RULE_ENGINE = {
        "enabled": False,
        "rules": [],
        "deployed_rules_path": "../backend/deployed_models/line_a/rules/rules.json",
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
    ) -> dict[str, object]:
        """生成完整的检测配置字典。

        Args:
            model_paths: model_version_id → artifact_path 的映射，由调用方从 model_versions 表查询。
        """
        selected_ids = set(selected_camera_ids) if selected_camera_ids else None

        camera_configs = []
        for cam in cameras:
            if selected_ids is not None and cam.camera_id not in selected_ids:
                continue
            camera_configs.append(self._build_camera_config(cam, model_paths))

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
        self, cam: CameraConfig, model_paths: dict[str, str]
    ) -> dict[str, object]:
        yolo_path = self._resolve_model_path(cam.yolo_model_version_id, model_paths)
        detection = dict(self.DEFAULT_DETECTION)
        detection["model_path"] = yolo_path
        detection["confidence"] = cam.detection_confidence

        patchcore = dict(self.DEFAULT_PATCHCORE)
        patchcore["image_size"] = cam.patchcore_image_size
        patchcore["threshold_quantile"] = cam.patchcore_threshold

        filter_classifier: dict[str, object] = dict(self.DEFAULT_FILTER_CLASSIFIER)
        filter_classifier["model_path"] = self._resolve_path(
            str(filter_classifier["model_path"])
        )

        rule_engine: dict[str, object] = dict(self.DEFAULT_RULE_ENGINE)
        deployed_rules = rule_engine.get("deployed_rules_path")
        if deployed_rules:
            rule_engine["deployed_rules_path"] = self._resolve_path(str(deployed_rules))

        patchcore_path = self._resolve_model_path(
            cam.patchcore_model_version_id, model_paths
        )

        config: dict[str, object] = {
            "camera_id": cam.camera_id,
            "patchcore_model_path": patchcore_path,
            "source": "",
            "enabled": True,
            "color_insensitive_mode": True,
            "quality": dict(self.DEFAULT_QUALITY),
            "detection": detection,
            "roi": dict(self.DEFAULT_ROI),
            "patchcore": patchcore,
            "color_branch": dict(self.DEFAULT_COLOR_BRANCH),
            "filter_classifier": filter_classifier,
            "rule_engine": rule_engine,
            "regions": [],
        }

        if cam.region_mode_enabled:
            region_patchcore_overrides: dict[str, object] = {
                "backbone_pretrained": True,
                "min_target_coverage": 0.5,
                "min_valid_patch_ratio": 0.35,
            }
            config["regions"] = [
                {
                    "region_id": "upper",
                    "box": [0.03, 0.03, 0.97, 0.42],
                    "patchcore_model_path": self._resolve_model_path(
                        cam.region_upper_model_version_id, model_paths
                    ),
                    "enabled": bool(cam.region_upper_model_version_id),
                    "patchcore": region_patchcore_overrides,
                },
                {
                    "region_id": "middle",
                    "box": [0.03, 0.38, 0.97, 0.67],
                    "patchcore_model_path": self._resolve_model_path(
                        cam.region_middle_model_version_id, model_paths
                    ),
                    "enabled": bool(cam.region_middle_model_version_id),
                    "patchcore": region_patchcore_overrides,
                },
                {
                    "region_id": "lower",
                    "box": [0.03, 0.66, 0.97, 0.97],
                    "patchcore_model_path": self._resolve_model_path(
                        cam.region_lower_model_version_id, model_paths
                    ),
                    "enabled": bool(cam.region_lower_model_version_id),
                    "patchcore": region_patchcore_overrides,
                },
            ]

        return config
