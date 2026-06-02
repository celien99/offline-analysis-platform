from __future__ import annotations

from datetime import datetime, timezone

from app.models.camera_config import CameraConfig, CameraConfigRegion
from app.schemas.camera_config import CameraConfigResponse
from app.services.camera_config.builder import ConfigBuilder


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
