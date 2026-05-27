"""Single-camera core inspection details."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

import numpy as np

from ..artifacts import generate_overlay_image, save_debug_artifacts
from ..config import CameraConfig
from ..cvops import split_roi_regions
from ..cvops.regions import RegionRoiSample
from ..efficientad import EfficientADService
from ..rule_engine import apply_rules, merge_rules
from ..core_types import BoundingBox, CameraInspectionResult, FramePacket, InspectionError, RegionAnomalyResult
from ..util import select_texture_input
from ..proposal import BudgetController, BudgetConfig, ProposalGenerator, ProposalConfig, aggregate_proposals
from .._protocol import FilterResult

if TYPE_CHECKING:
    from .core import CameraPipeline, InspectionService


@dataclass
class RegionAnomalyPlan:
    """Deferred region anomaly work for cross-camera batching."""

    frame_packet: FramePacket
    camera: CameraConfig
    prepared: Any
    seat_model_id: Optional[str]
    shared_result_fields: dict
    quality_rejected: bool
    camera_timer: "_StageTimer"
    region_results: List[RegionAnomalyResult]
    anomaly_items: List[Tuple[EfficientADService, Any, Any, Any]]
    runnable_regions: List[Tuple[Any, RegionRoiSample]]


def inspect_one_camera(
    service: "InspectionService",
    frame_packet: FramePacket,
    camera: CameraConfig,
    pipeline: "CameraPipeline",
    seat_model_id: Optional[str],
) -> CameraInspectionResult:
    """Run one camera through detection, ROI, anomaly detection and artifacts."""
    camera_timer = _StageTimer()
    prepared = pipeline.prepare_image(frame_packet.image)
    camera_timer.mark("prepare")
    outcome = inspect_prepared_camera(
        service,
        frame_packet,
        camera,
        prepared,
        seat_model_id,
        camera_timer,
    )
    if isinstance(outcome, RegionAnomalyPlan):
        texture_results = service.predict_anomaly_batch(outcome.anomaly_items)
        anomaly_elapsed_ms = camera_timer.mark("region_anomaly_batch")
        return finish_region_anomaly_plan(
            service,
            outcome,
            texture_results,
            anomaly_elapsed_ms=anomaly_elapsed_ms,
        )
    return outcome


def inspect_prepared_camera(
    service: "InspectionService",
    frame_packet: FramePacket,
    camera: CameraConfig,
    prepared,
    seat_model_id: Optional[str],
    camera_timer: "_StageTimer",
) -> Union[CameraInspectionResult, RegionAnomalyPlan]:
    """Finish one camera after prepare, optionally deferring region anomaly."""
    shared_result_fields = {
        "camera_id": frame_packet.camera_id,
        "frame_id": frame_packet.frame_id,
        "source": frame_packet.source,
        "source_kind": frame_packet.source_kind,
        "seat_model_id": seat_model_id,
        "quality": prepared.quality,
        "detection": prepared.detection,
    }

    quality_rejected = (
        prepared.rejection_reason is not None
        and prepared.rejection_reason.startswith("quality_")
    )
    if prepared.roi is None or (prepared.rejection_reason is not None and not quality_rejected):
        result = CameraInspectionResult(
            status="REJECT",
            reason=prepared.rejection_reason or "camera_prepare_failed",
            crop_box=(prepared.roi.crop_box if prepared.roi is not None else None),
            error=_error_from_reason(
                prepared.rejection_reason or "camera_prepare_failed",
                stage="prepare",
            ),
            **shared_result_fields,
        )
        return _finish_camera_result(
            service,
            frame_packet,
            prepared,
            seat_model_id,
            result,
            camera_timer,
        )

    active_regions = [region for region in camera.regions if region.enabled]
    if active_regions:
        return build_region_anomaly_plan(
            service,
            frame_packet,
            camera,
            prepared,
            seat_model_id,
            shared_result_fields,
            quality_rejected,
            camera_timer,
        )

    model_bundle = service.load_model_bundle(camera, seat_model_id)
    texture_input = select_texture_input(prepared.roi)
    texture_result = model_bundle.predict(
        texture_input,
        prepared.roi.target_mask,
        prepared.roi.ignore_mask,
    )
    camera_timer.mark("anomaly")
    if texture_result.valid_pixel_ratio < camera.efficientad.min_valid_pixel_ratio:
        result = CameraInspectionResult(
            status="REJECT",
            reason="low_valid_pixel_ratio",
            texture_result=texture_result,
            crop_box=prepared.roi.crop_box,
            error=_error_from_reason("low_valid_pixel_ratio", stage="anomaly"),
            **shared_result_fields,
        )
        return _finish_camera_result(
            service,
            frame_packet,
            prepared,
            seat_model_id,
            result,
            camera_timer,
            texture_result,
        )

    if texture_result.is_anomaly:
        status = "NG"
        reason = "texture_anomaly_quality_override" if quality_rejected else "texture_anomaly"
    elif quality_rejected:
        status = "REJECT"
        reason = prepared.rejection_reason or "quality_reject"
    else:
        status = "OK"
        reason = "all_checks_passed"

    # --- Region Proposal + Dual-Modal Filter (with Calibration & Cascading Budget) ---
    filter_result: Optional[FilterResult] = None
    proposals: list[Any] = []

    if texture_result.is_anomaly:
        filter_svc = getattr(service, 'filter_service', None)
        if filter_svc is not None:
            try:
                proposal_cfg = getattr(camera, 'proposal', None) or ProposalConfig()
                proposal_budget_cfg = proposal_cfg.budget
                cascading_budget_ctrl = None
                if proposal_budget_cfg is not None:
                    from ..proposal import CascadingBudgetConfig, CascadingBudgetController
                    try:
                        cascade_cfg = CascadingBudgetConfig(proposal=proposal_budget_cfg)
                        cascading_budget_ctrl = CascadingBudgetController(cascade_cfg)
                    except Exception:
                        pass
                if cascading_budget_ctrl is not None:
                    generator = ProposalGenerator(proposal_cfg, budget_ctrl=cascading_budget_ctrl)
                else:
                    budget_ctrl = BudgetController(
                        proposal_budget_cfg if proposal_budget_cfg else BudgetConfig()
                    )
                    generator = ProposalGenerator(proposal_cfg, budget_ctrl=budget_ctrl)
                isolation_key = f"{seat_model_id or 'unknown'}|{camera.camera_id}|default"

                roi_h, roi_w = prepared.roi.aligned_roi_image.shape[:2]
                roi_bbox = (
                    int(prepared.roi.crop_box.x1) if prepared.roi.crop_box is not None else 0,
                    int(prepared.roi.crop_box.y1) if prepared.roi.crop_box is not None else 0,
                    roi_w, roi_h,
                )

                proposals = generator.generate(
                    heatmap=texture_result.anomaly_map,
                    roi_image=prepared.roi.aligned_roi_image,
                    efficientad_features=texture_result.features,
                    anomaly_score=texture_result.score,
                    anomaly_threshold=texture_result.threshold,
                    roi_bbox=roi_bbox,
                    isolation_key=isolation_key,
                )

                # --- Calibration: normalize + project + whiten ---
                unified_emb: Optional[np.ndarray] = None
                calibration = getattr(service, 'calibration', None)
                if calibration is not None and texture_result.features:
                    calibrated = calibration.calibrate(camera.camera_id, texture_result.features)
                    if calibrated is not None:
                        unified_emb = np.array(calibrated.vector, dtype=np.float32)

                # --- Identity Linking (with unified embedding) ---
                if proposals:
                    tracker = getattr(service, '_trackers', {})
                    cam_tracker = tracker.get(camera.camera_id)
                    if cam_tracker is None and getattr(camera, 'track', None) is not None:
                        from ..tracking import DefectTracker
                        cam_tracker = DefectTracker(camera.camera_id, camera.track)
                        tracker[camera.camera_id] = cam_tracker
                        service._trackers = tracker
                    if cam_tracker is not None:
                        proposals = cam_tracker.update(proposals)

                # --- Cascading Budget: schedule which proposals get Filter ---
                if proposals:
                    if cascading_budget_ctrl is not None:
                        to_filter, skip_list, filter_mode = cascading_budget_ctrl.schedule_filter(proposals)
                    else:
                        to_filter, skip_list, filter_mode = proposals, [], "full"

                    patch_crops = generator.extract_patch_crops(
                        prepared.roi.aligned_roi_image, to_filter)
                    patch_features_list = []
                    if texture_result.features:
                        patch_features_list = generator.extract_patch_features(
                            texture_result.features, to_filter, (roi_h, roi_w))

                    filter_start_ms = perf_counter()
                    for i, proposal in enumerate(to_filter):
                        patch_img = patch_crops[i] if i < len(patch_crops) else None
                        patch_feats = patch_features_list[i] if i < len(patch_features_list) else None
                        if patch_img is not None:
                            pf_result = filter_svc.predict_dual_modal(
                                patch_img, patch_feats,
                                unified_emb=unified_emb.tolist() if unified_emb is not None else None,
                            )
                            proposal.filter_result = pf_result

                    if cascading_budget_ctrl is not None:
                        cascading_budget_ctrl.record_filter_cost(
                            len(to_filter),
                            (perf_counter() - filter_start_ms) * 1000.0,
                        )

                    # Aggregate to ROI-level decision
                    filter_result = aggregate_proposals(proposals)

            except Exception:
                import traceback
                traceback.print_exc()
                filter_result = FilterResult(
                    is_real_defect=True, confidence=0.0,
                    real_defect_score=0.0, false_alarm_score=0.0,
                    class_id=1, diagnostics={"mode": "error_fallback"},
                )

    # Override status if filter suppressed the anomaly
    if filter_result is not None and not filter_result.is_real_defect:
        status = "OK"
        reason = "filter_suppressed"

    result = CameraInspectionResult(
        status=status,
        reason=reason,
        texture_result=texture_result,
        crop_box=prepared.roi.crop_box,
        filter_result=filter_result,
        proposals=proposals,
        **shared_result_fields,
    )
    # 应用规则引擎后处理（合并本地规则 + 离线平台部署规则）
    if camera.rule_engine.enabled:
        all_rules = merge_rules(camera.rule_engine.rules, camera.rule_engine.deployed_rules_path)
        if all_rules:
            result = apply_rules(result, all_rules)
    return _finish_camera_result(
        service,
        frame_packet,
        prepared,
        seat_model_id,
        result,
        camera_timer,
        texture_result,
    )


def build_region_anomaly_plan(
    service: "InspectionService",
    frame_packet: FramePacket,
    camera: CameraConfig,
    prepared,
    seat_model_id: Optional[str],
    shared_result_fields: dict,
    quality_rejected: bool,
    camera_timer: "_StageTimer",
) -> RegionAnomalyPlan:
    region_samples: Dict[str, RegionRoiSample] = {
        sample.region_id: sample
        for sample in split_roi_regions(prepared.roi, camera.regions)
    }
    camera_timer.mark("split_regions")
    region_results: List[RegionAnomalyResult] = []
    anomaly_items = []
    runnable_regions = []
    for region in camera.regions:
        if not region.enabled:
            continue
        region_sample = region_samples.get(region.region_id)
        if region_sample is None:
            region_results.append(
                RegionAnomalyResult(
                    region_id=region.region_id,
                    status="REJECT",
                    reason="region_empty",
                    box=_region_config_box_to_roi_box(region.box, prepared.roi.aligned_roi_image.shape[:2]),
                    efficientad_model_path=region.efficientad_model_path,
                    timings_ms={},
                    error=_error_from_reason("region_empty", stage="region_prepare"),
                )
            )
            continue

        model_bundle = service.load_region_model_bundle(camera, region, seat_model_id)
        anomaly_items.append(
            (
                model_bundle,
                region_sample.image,
                region_sample.target_mask,
                region_sample.ignore_mask,
            )
        )
        runnable_regions.append((region, region_sample))

    return RegionAnomalyPlan(
        frame_packet=frame_packet,
        camera=camera,
        prepared=prepared,
        seat_model_id=seat_model_id,
        shared_result_fields=shared_result_fields,
        quality_rejected=quality_rejected,
        camera_timer=camera_timer,
        region_results=region_results,
        anomaly_items=anomaly_items,
        runnable_regions=runnable_regions,
    )


def finish_region_anomaly_plan(
    service: "InspectionService",
    plan: RegionAnomalyPlan,
    texture_results,
    *,
    anomaly_elapsed_ms: float,
) -> CameraInspectionResult:
    region_results = list(plan.region_results)
    per_region_anomaly_ms = (
        anomaly_elapsed_ms / len(texture_results)
        if texture_results
        else 0.0
    )
    for (region, region_sample), texture_result in zip(plan.runnable_regions, texture_results):
        min_valid_pixel_ratio = (
            region.efficientad.min_valid_pixel_ratio
            if region.efficientad is not None
            else plan.camera.efficientad.min_valid_pixel_ratio
        )
        if texture_result.valid_pixel_ratio < min_valid_pixel_ratio:
            status = "REJECT"
            reason = "low_valid_pixel_ratio"
            error = _error_from_reason(reason, stage="anomaly")
        elif texture_result.is_anomaly:
            status = "NG"
            reason = (
                "texture_anomaly_quality_override"
                if plan.quality_rejected
                else "texture_anomaly"
            )
            error = None
        else:
            status = "OK"
            reason = "all_checks_passed"
            error = None
        region_results.append(
            RegionAnomalyResult(
                region_id=region.region_id,
                status=status,
                reason=reason,
                box=region_sample.box,
                texture_result=texture_result,
                efficientad_model_path=region.efficientad_model_path,
                timings_ms={"anomaly": per_region_anomaly_ms},
                error=error,
                sample=region_sample,
            )
        )

    if not region_results:
        result = CameraInspectionResult(
            status="REJECT",
            reason="no_enabled_regions",
            crop_box=plan.prepared.roi.crop_box,
            error=_error_from_reason("no_enabled_regions", stage="region_prepare"),
            **plan.shared_result_fields,
        )
        return _finish_camera_result(
            service,
            plan.frame_packet,
            plan.prepared,
            plan.seat_model_id,
            result,
            plan.camera_timer,
        )

    status, reason = _merge_region_status(
        region_results,
        plan.quality_rejected,
        plan.prepared,
    )
    result = CameraInspectionResult(
        status=status,
        reason=reason,
        region_results=region_results,
        crop_box=plan.prepared.roi.crop_box,
        **plan.shared_result_fields,
    )
    if status == "REJECT":
        result.error = _error_from_reason(reason, stage="region_merge")
    # 应用规则引擎后处理（合并本地规则 + 离线平台部署规则）
    if plan.camera.rule_engine.enabled:
        all_rules = merge_rules(plan.camera.rule_engine.rules, plan.camera.rule_engine.deployed_rules_path)
        if all_rules:
            result = apply_rules(result, all_rules)
    result = _finish_camera_result(
        service,
        plan.frame_packet,
        plan.prepared,
        plan.seat_model_id,
        result,
        plan.camera_timer,
        region_results=region_results,
    )
    return result


class _StageTimer:
    """Small monotonic stage timer for one camera."""

    def __init__(self) -> None:
        self._started_at = perf_counter()
        self._last_at = self._started_at
        self.timings_ms: Dict[str, float] = {}

    def mark(self, name: str) -> float:
        now = perf_counter()
        elapsed_ms = (now - self._last_at) * 1000.0
        self.timings_ms[name] = elapsed_ms
        self._last_at = now
        return elapsed_ms

    def record(self, name: str, elapsed_ms: float) -> None:
        self.timings_ms[name] = elapsed_ms
        self._last_at = perf_counter()

    def finish(self) -> Dict[str, float]:
        total_ms = (perf_counter() - self._started_at) * 1000.0
        self.timings_ms["total"] = total_ms
        return dict(self.timings_ms)


def _merge_region_status(
    region_results: List[RegionAnomalyResult],
    quality_rejected: bool,
    prepared,
) -> Tuple[str, str]:
    ng_regions = [item for item in region_results if item.status == "NG"]
    reject_regions = [item for item in region_results if item.status == "REJECT"]

    if ng_regions:
        region_ids = ",".join(item.region_id for item in ng_regions)
        prefix = "region_texture_anomaly_quality_override" if quality_rejected else "region_texture_anomaly"
        reason = f"{prefix}:{region_ids}"
        if reject_regions:
            reject_ids = ",".join(item.region_id for item in reject_regions)
            reason += f"_with_reject:{reject_ids}"
        return "NG", reason
    if reject_regions:
        return "REJECT", f"region_reject:{reject_regions[0].region_id}:{reject_regions[0].reason}"
    if quality_rejected:
        return "REJECT", prepared.rejection_reason or "quality_reject"
    return "OK", "all_regions_passed"


def _region_config_box_to_roi_box(
    box: List[float],
    roi_shape: Tuple[int, int],
) -> BoundingBox:
    height, width = roi_shape
    return BoundingBox(
        x1=float(round(box[0] * width)),
        y1=float(round(box[1] * height)),
        x2=float(round(box[2] * width)),
        y2=float(round(box[3] * height)),
    )


def _attach_debug_artifacts(
    service: "InspectionService",
    frame_packet: FramePacket,
    prepared,
    seat_model_id: Optional[str],
    result: CameraInspectionResult,
    texture_result=None,
    region_results=None,
) -> CameraInspectionResult:
    if not getattr(service.config, "debug_artifacts_enabled", True):
        result.artifact_paths = {}
        return result
    result.artifact_paths = save_debug_artifacts(
        debug_dir=service.config.debug_dir,
        artifact_names=getattr(service.config, "debug_artifact_names", None),
        frame_packet=frame_packet,
        prepared=prepared,
        texture_result=texture_result,
        region_results=region_results,
        seat_model_id=seat_model_id,
    )
    return result


def _finish_camera_result(
    service: "InspectionService",
    frame_packet: FramePacket,
    prepared,
    seat_model_id: Optional[str],
    result: CameraInspectionResult,
    timer: _StageTimer,
    texture_result=None,
    region_results=None,
) -> CameraInspectionResult:
    before_artifacts = perf_counter()
    result.overlay_image = generate_overlay_image(
        frame_packet,
        prepared,
        texture_result=texture_result,
        region_results=region_results,
    )
    # 保存干净图像，供 anomaly_uploader 按 original / roi 语义上传。
    if frame_packet.image is not None:
        result.original_image = frame_packet.image.copy()
    if prepared is not None and prepared.roi is not None:
        if prepared.roi.roi_image is not None:
            result.roi_image = prepared.roi.roi_image.copy()
        if prepared.roi.aligned_roi_image is not None:
            result.roi_aligned_image = prepared.roi.aligned_roi_image.copy()
    result = _attach_debug_artifacts(
        service,
        frame_packet,
        prepared,
        seat_model_id,
        result,
        texture_result=texture_result,
        region_results=region_results,
    )
    result.timings_ms = timer.finish()
    result.timings_ms["debug_artifacts"] = (perf_counter() - before_artifacts) * 1000.0
    return result


def _error_from_reason(reason: str, *, stage: str) -> InspectionError:
    code = _normalize_error_code(reason)
    return InspectionError(code=code, message=reason, stage=stage)


def _normalize_error_code(reason: str) -> str:
    normalized = reason.split(":", 1)[0].strip().lower()
    normalized = normalized.replace("-", "_").replace(" ", "_")
    return normalized or "unknown_error"
