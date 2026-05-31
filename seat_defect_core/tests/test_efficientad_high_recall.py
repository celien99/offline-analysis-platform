import numpy as np
import cv2

from types import SimpleNamespace

from seat_defect_core.artifacts.debug import _overlay_heatmap
from seat_defect_core.efficientad.engine import (
    _compute_masked_topk_score,
    _compute_pixel_anomaly_stats,
)
from seat_defect_core.training import efficientad as efficientad_training


def test_masked_topk_score_uses_roi_peak_values() -> None:
    anomaly_map = np.zeros((10, 10), dtype=np.float32)
    anomaly_map[5, 5] = 10.0
    anomaly_map[5, 6] = 8.0
    target_mask = np.ones((10, 10), dtype=np.uint8)

    score = _compute_masked_topk_score(anomaly_map, target_mask, ratio=0.02)

    assert score == 9.0


def test_pixel_anomaly_stats_requires_minimum_area() -> None:
    anomaly_map = np.zeros((20, 20), dtype=np.float32)
    anomaly_map[4:6, 4:6] = 5.0
    target_mask = np.ones((20, 20), dtype=np.uint8)

    is_anomaly, area, ratio = _compute_pixel_anomaly_stats(
        anomaly_map,
        target_mask,
        threshold=3.0,
        min_area=4,
        min_area_ratio=0.0,
    )

    assert is_anomaly is True
    assert area == 4
    assert ratio == 0.01


def test_overlay_heatmap_makes_peak_visually_dominant() -> None:
    image = np.full((64, 64, 3), 40, dtype=np.uint8)
    heatmap = np.zeros((64, 64), dtype=np.float32)
    heatmap[30:34, 30:34] = 1.0
    heatmap[10:20, 10:20] = 0.2

    overlay = _overlay_heatmap(image, heatmap)

    peak_patch = overlay[30:34, 30:34].astype(np.int16)
    low_patch = overlay[10:20, 10:20].astype(np.int16)
    assert peak_patch.mean() > low_patch.mean() + 80
    assert peak_patch.max() >= 240


def test_prepare_training_images_persists_online_texture_input(tmp_path) -> None:
    source = tmp_path / "source.png"
    source_image = np.full((32, 32, 3), 80, dtype=np.uint8)
    assert cv2.imwrite(str(source), source_image)

    aligned = np.full((16, 16, 3), 120, dtype=np.uint8)
    target_mask = np.ones((16, 16), dtype=np.uint8)
    ignore_mask = np.zeros((16, 16), dtype=np.uint8)
    ignore_mask[:2, :] = 1

    class FakePipeline:
        def __init__(self, _camera_config) -> None:
            pass

        def prepare_image(self, _image):
            return SimpleNamespace(
                roi=SimpleNamespace(
                    aligned_roi_image=aligned,
                    target_mask=target_mask,
                    ignore_mask=ignore_mask,
                ),
                rejection_reason=None,
            )

    result = efficientad_training._prepare_training_images(
        SimpleNamespace(camera_id="cam_test"),
        [source],
        tmp_path / "prepared",
        reset_output=True,
        pipeline_cls=FakePipeline,
    )

    saved_image = cv2.imread(str(result["image_paths"][0]))
    saved_target = cv2.imread(str(result["target_mask_paths"][0]), cv2.IMREAD_GRAYSCALE)
    saved_ignore = cv2.imread(str(result["ignore_mask_paths"][0]), cv2.IMREAD_GRAYSCALE)
    assert np.array_equal(saved_image, aligned)
    assert saved_target.sum() == 16 * 16 * 255
    assert saved_ignore[:2, :].sum() == 2 * 16 * 255
