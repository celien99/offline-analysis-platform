from __future__ import annotations

from datetime import datetime, timezone

from app.models.camera_config import CameraConfig, CameraConfigRegion
from app.schemas.camera_config import CameraConfigResponse
from app.services.camera_config.region_definitions import RegionDefinitionLoader
from app.services.camera_config.builder import ConfigBuilder
from app.api.camera_config.router import _build_region_entities_from_config


def test_camera_region_response_and_builder_mapping() -> None:
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
    assert response.regions[0].box == [0.0, 0.0, 1.0, 0.5]

    config = ConfigBuilder(repo_root=".").build(
        seat_model_id="seat_a",
        display_name="Seat A",
        cameras=[camera],
        model_paths={
            "full_patchcore_model": "/models/full.npz",
            "upper_patchcore_model": "/models/upper.npz",
        },
    )

    camera_config = config["seat_defect_inspection"]["seat_models"][0]["cameras"][0]
    assert camera_config["patchcore_model_path"] == "/models/full.npz"
    assert camera_config["regions"] == [
        {
            "region_id": "upper",
            "box": [0.0, 0.0, 1.0, 0.5],
            "patchcore_model_path": "/models/upper.npz",
            "enabled": True,
        }
    ]


def test_region_definitions_loaded_from_inspection_config() -> None:
    loader = RegionDefinitionLoader(config_path="../seat_defect_core/config.example.json")

    regions = loader.load_for_camera(seat_model_id="seat_model_a", camera_id="cam_back")

    assert [region.region_id for region in regions] == ["upper", "middle", "lower"]
    assert regions[0].box == [0.03, 0.03, 0.97, 0.42]
    assert regions[0].enabled is True
    assert regions[0].patchcore is not None


def test_region_entities_use_geometry_from_config() -> None:
    entities = _build_region_entities_from_config(
        seat_model_id="seat_model_a",
        camera_id="cam_back",
        regions=[
            {"region_id": "upper", "patchcore_model_version_id": "upper_model"},
        ],
        loader=RegionDefinitionLoader(config_path="../seat_defect_core/config.example.json"),
    )

    assert len(entities) == 1
    assert entities[0].region_id == "upper"
    assert entities[0].patchcore_model_version_id == "upper_model"
    assert [entities[0].x1, entities[0].y1, entities[0].x2, entities[0].y2] == [
        0.03,
        0.03,
        0.97,
        0.42,
    ]


def test_unknown_region_id_is_rejected() -> None:
    from fastapi import HTTPException

    try:
        _build_region_entities_from_config(
            seat_model_id="seat_model_a",
            camera_id="cam_back",
            regions=[
                {"region_id": "unknown", "patchcore_model_version_id": "model"},
            ],
            loader=RegionDefinitionLoader(config_path="../seat_defect_core/config.example.json"),
        )
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "不存在于检测配置文件" in str(exc.detail)
    else:
        raise AssertionError("unknown region should be rejected")
