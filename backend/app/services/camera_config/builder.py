"""根据数据库配置生成完整的 seat_defect_core 检测配置 JSON。"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from app.models.camera_config import CameraConfig


class ConfigBuilder:
    """将 DB 中的相机配置与硬编码默认参数合并，生成完整配置 JSON。

    默认参数对齐 seat_defect_core/config.best.json（device 统一为 cpu，whitening 关闭），
    仅暴露相机级的少量字段给用户配置。
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
        "confidence": 0.15,
        "iou": 0.45,
        "device": "cpu",
        "imgsz": 960,
        "fill_segmentation_holes": True,
        "segmentation_hole_fill_max_area_ratio": 0.08,
    }

    DEFAULT_ROI = {
        "crop_expand_ratio": 0.0,
        "crop_shrink_ratio": 0.0,
        "mask_erode_pixels": 3,
        "edge_ignore_pixels": 12,
        "alignment": {"output_width": 256, "output_height": 256},
    }

    DEFAULT_PATCHCORE = {
        "backend": "full",
        "image_size": 256,
        "patch_size": 32,
        "stride": 16,
        "max_memory": 1024,
        "threshold_quantile": 0.99,
        "texture_input": "lab_l",
        "min_target_coverage": 0.8,
        "max_ignore_overlap": 0.1,
        "min_valid_patch_ratio": 0.65,
        "backbone_name": "wide_resnet50_2",
        "feature_layers": ["layer2", "layer3"],
        "backbone_pretrained": False,
        "backbone_device": "cpu",
        "feature_pool_kernel_size": 3,
        "coreset_sampling_ratio": 0.1,
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
        "input_size": 448,
        "confidence_threshold": 0.3,
    }

    DEFAULT_RULE_ENGINE = {
        "enabled": True,
        "rules": [],
        "deployed_rules_path": "backend/deployed_models/line_a/rules/rules.json",
    }

    DEFAULT_PROPOSAL = {
        "heatmap_threshold_mode": "adaptive",
        "heatmap_threshold_fixed": 0.5,
        "heatmap_adaptive_std_multiplier": 1.0,
        "min_component_area": 8,
        "min_solidity": 0.2,
        "max_proposals": 30,
        "open_kernel_size": 3,
        "close_kernel_size": 5,
        "context_padding_ratio": 0.10,
        "min_crop_size": 20,
        "aggregation_method": "weighted_confidence",
        "area_exponent": 0.5,
        "confidence_threshold": 0.3,
        "budget": {
            "enabled": True,
            "scope": "proposal_and_filter",
            "target_latency_ms": 15.0,
            "hard_limit_ms": 20.0,
            "max_cc_before_emergency": 50,
            "avg_filter_latency_ms": 3.0,
            "window_size": 100,
            "threshold_multiplier_step": 0.5,
            "threshold_multiplier_max": 3.0,
            "recovery_rate": 0.01,
        },
    }

    DEFAULT_TRACKING = {
        "max_age": 30,
        "min_hits": 2,
        "mature_hits": 5,
        "iou_threshold": 0.3,
        "mahalanobis_threshold": 9.5,
        "feature_cosine_threshold": 0.85,
        "feature_match_margin": 0.15,
        "nms_iou_threshold": 0.5,
        "cross_camera_cosine_threshold": 0.9,
        "epipolar_distance_threshold": 50.0,
    }

    DEFAULT_CALIBRATION = {
        "enabled": True,
        "camera_norm": {
            "enabled": True,
            "stats_path": "",
        },
        "projection": {
            "enabled": True,
            "projector_path": "",
        },
        "whitening": {
            "enabled": False,
            "method": "zca",
            "regularization": 0.0001,
            "matrix_path": "",
        },
        "ema_center": {
            "enabled": True,
            "alpha": 0.99,
            "min_samples": 10,
            "novelty_threshold": 0.2,
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

        patchcore = dict(self.DEFAULT_PATCHCORE)
        patchcore["image_size"] = cam.efficientad_image_size
        patchcore["threshold_quantile"] = cam.efficientad_threshold

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

        patchcore_path = self._resolve_model_path(
            cam.efficientad_model_version_id, model_paths
        )
        regions = self._build_region_configs(cam, model_paths)

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
            "regions": regions,
        }

        return config

    def _build_region_configs(
        self,
        cam: CameraConfig,
        model_paths: dict[str, str],
    ) -> list[dict[str, object]]:
        region_configs: list[dict[str, object]] = []
        for region in cam.regions:
            if region.deleted_at is not None:
                continue
            patchcore_path = self._resolve_model_path(
                region.patchcore_model_version_id,
                model_paths,
            )
            region_config: dict[str, object] = {
                "region_id": region.region_id,
                "box": [region.x1, region.y1, region.x2, region.y2],
                "patchcore_model_path": patchcore_path,
                "enabled": region.enabled,
            }
            if region.patchcore_overrides_json:
                try:
                    overrides = json.loads(region.patchcore_overrides_json)
                except json.JSONDecodeError:
                    overrides = None
                if isinstance(overrides, dict):
                    region_config["patchcore"] = overrides
            region_configs.append(region_config)
        return region_configs
