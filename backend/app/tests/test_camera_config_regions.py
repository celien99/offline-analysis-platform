from __future__ import annotations

from datetime import datetime, timezone

from app.models.camera_config import CameraConfig, CameraConfigRegion
from app.schemas.camera_config import CameraConfigResponse
from app.services.camera_config.builder import ConfigBuilder
from app.api.camera_config.router import _build_region_binding_entities


def test_camera_region_response_keeps_binding_metadata() -> None:
    now = datetime.now(tz=timezone.utc)
    camera = CameraConfig(
        id="camera-db-id",
        camera_id="cam_front",
        seat_model_id="seat_a",
        efficientad_model_version_id="full_patchcore_model",
        filter_classifier_model_version_id=None,
        normalizer_model_version_id=None,
        detection_confidence=0.25,
        efficientad_image_size=256,
        efficientad_threshold=0.99,
    )
    camera.created_at = now
    camera.updated_at = now
    region = CameraConfigRegion(
        id="region-db-id",
        region_id="upper",
        x1=0.0,
        y1=0.0,
        x2=1.0,
        y2=0.5,
        patchcore_model_version_id="upper_patchcore_model",
        enabled=True,
        sort_order=0,
    )
    region.created_at = now
    region.updated_at = now
    camera.regions = [region]

    response = CameraConfigResponse.model_validate(camera)
    assert response.regions[0].region_id == "upper"
    assert response.regions[0].patchcore_model_version_id == "upper_patchcore_model"
    assert response.regions[0].box == [0.0, 0.0, 1.0, 0.5]


def test_builder_uses_core_config_geometry_and_overrides_region_model() -> None:
    now = datetime.now(tz=timezone.utc)
    camera = CameraConfig(
        id="camera-db-id",
        camera_id="cam_back",
        seat_model_id="seat_model_a",
        efficientad_model_version_id="full_patchcore_model",
        filter_classifier_model_version_id=None,
        normalizer_model_version_id=None,
        detection_confidence=0.25,
        efficientad_image_size=256,
        efficientad_threshold=0.99,
    )
    camera.created_at = now
    camera.updated_at = now
    region = CameraConfigRegion(
        id="region-db-id",
        region_id="upper",
        x1=0.0,
        y1=0.0,
        x2=1.0,
        y2=1.0,
        patchcore_model_version_id="upper_patchcore_model",
        enabled=True,
        sort_order=0,
    )
    region.created_at = now
    region.updated_at = now
    camera.regions = [region]

    config = ConfigBuilder(repo_root=".").build(
        seat_model_id="seat_model_a",
        display_name="Seat A",
        cameras=[camera],
        model_paths={
            "full_patchcore_model": "/models/full.npz",
            "upper_patchcore_model": "/models/upper.npz",
        },
    )

    camera_config = config["seat_defect_inspection"]["seat_models"][0]["cameras"][0]
    assert camera_config["patchcore_model_path"] == "/models/full.npz"
    upper = camera_config["regions"][0]
    assert upper["region_id"] == "upper"
    assert upper["box"] == [0.03, 0.03, 0.97, 0.42]
    assert upper["patchcore_model_path"] == "/models/upper.npz"
    assert upper["patchcore"] == {
        "backbone_pretrained": True,
        "min_target_coverage": 0.5,
        "min_valid_patch_ratio": 0.35,
    }


def test_builder_matches_template_camera_case_insensitively() -> None:
    now = datetime.now(tz=timezone.utc)
    camera = CameraConfig(
        id="camera-db-id",
        camera_id="cam_back",
        seat_model_id="seat_model_A",
        efficientad_model_version_id="full_patchcore_model",
        filter_classifier_model_version_id=None,
        normalizer_model_version_id=None,
        detection_confidence=0.25,
        efficientad_image_size=256,
        efficientad_threshold=0.99,
    )
    camera.created_at = now
    camera.updated_at = now
    region = CameraConfigRegion(
        id="region-db-id",
        region_id="middle",
        x1=0.0,
        y1=0.0,
        x2=1.0,
        y2=1.0,
        patchcore_model_version_id="middle_patchcore_model",
        enabled=True,
        sort_order=0,
    )
    region.created_at = now
    region.updated_at = now
    camera.regions = [region]

    config = ConfigBuilder(repo_root=".").build(
        seat_model_id="seat_model_A",
        display_name="Seat A",
        cameras=[camera],
        model_paths={
            "full_patchcore_model": "/models/full.npz",
            "middle_patchcore_model": "/models/middle.npz",
        },
    )

    camera_config = config["seat_defect_inspection"]["seat_models"][0]["cameras"][0]
    assert camera_config["patchcore"]["backbone_pretrained"] is True
    assert camera_config["regions"][1]["region_id"] == "middle"
    assert camera_config["regions"][1]["box"] == [0.03, 0.38, 0.97, 0.67]
    assert camera_config["regions"][1]["patchcore_model_path"] == "/models/middle.npz"


def test_builder_fallback_patchcore_full_has_backbone_weights_source() -> None:
    now = datetime.now(tz=timezone.utc)
    camera = CameraConfig(
        id="camera-db-id",
        camera_id="unknown_camera",
        seat_model_id="unknown_seat_model",
        efficientad_model_version_id="full_patchcore_model",
        filter_classifier_model_version_id=None,
        normalizer_model_version_id=None,
        detection_confidence=0.25,
        efficientad_image_size=256,
        efficientad_threshold=0.99,
    )
    camera.created_at = now
    camera.updated_at = now
    camera.regions = []

    config = ConfigBuilder(repo_root=".").build(
        seat_model_id="unknown_seat_model",
        display_name="Unknown",
        cameras=[camera],
        model_paths={"full_patchcore_model": "/models/full.npz"},
    )

    camera_config = config["seat_defect_inspection"]["seat_models"][0]["cameras"][0]
    assert camera_config["patchcore"]["backend"] == "full"
    assert camera_config["patchcore"]["backbone_pretrained"] is True


def test_region_binding_entities_do_not_require_geometry() -> None:
    entities = _build_region_binding_entities(
        regions=[
            {"region_id": "upper", "patchcore_model_version_id": "upper_model"},
        ],
    )

    assert len(entities) == 1
    assert entities[0].region_id == "upper"
    assert entities[0].patchcore_model_version_id == "upper_model"
    assert [entities[0].x1, entities[0].y1, entities[0].x2, entities[0].y2] == [
        0.0,
        0.0,
        1.0,
        1.0,
    ]
