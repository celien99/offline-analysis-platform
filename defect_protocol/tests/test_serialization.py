from __future__ import annotations

from defect_protocol import (
    AnomalyContext,
    BoundingBox,
    EfficientADFeatures,
    FilterResult,
    ImageRef,
    PatchProposal,
    ProposalMetadata,
    ROIContext,
    proposal_from_dict,
    proposal_to_dict,
    proposals_from_json,
    proposals_to_json,
)


def make_proposal() -> PatchProposal:
    return PatchProposal(
        proposal_id="test-pid-001",
        isolation_key="model_a|cam_front|region_seat",
        source_roi=ROIContext(
            roi_bbox=BoundingBox(10, 20, 200, 300),
            roi_image_ref=ImageRef(key="roi/test.jpg", width=224, height=224),
            roi_size=(224, 224),
        ),
        patch_image=ImageRef(key="patches/test_patch.png", width=64, height=64),
        patch_bbox=BoundingBox(50, 60, 114, 124),
        anomaly_context=AnomalyContext(
            anomaly_score=0.92,
            anomaly_threshold=0.5,
            heatmap_ref=ImageRef(key="heatmaps/test.png"),
            feature_ref="features/model_a/cam_front/2026-05-26/test-pid-001",
        ),
        efficientad_features=EfficientADFeatures(
            teacher_l1_ref="features/.../teacher_l1.npy",
            teacher_l2_ref="features/.../teacher_l2.npy",
            teacher_l3_ref="features/.../teacher_l3.npy",
            difference_ref="features/.../difference.npy",
        ),
        proposal_metadata=ProposalMetadata(
            component_area=1024,
            component_solidity=0.85,
            rank=1,
            total_proposals=3,
        ),
        filter_result=FilterResult(
            is_real_defect=True,
            confidence=0.87,
            real_defect_score=0.87,
            false_alarm_score=0.13,
            class_id=1,
        ),
    )


def test_proposal_round_trip():
    p = make_proposal()
    d = proposal_to_dict(p)
    p2 = proposal_from_dict(d)
    assert p2.proposal_id == p.proposal_id
    assert p2.isolation_key == p.isolation_key
    assert p2.patch_bbox.x1 == p.patch_bbox.x1
    assert p2.anomaly_context.anomaly_score == p.anomaly_context.anomaly_score
    assert p2.efficientad_features.teacher_l1_ref == p.efficientad_features.teacher_l1_ref
    assert p2.filter_result is not None
    assert p2.filter_result.confidence == 0.87


def test_proposal_without_filter_result():
    p = make_proposal()
    p.filter_result = None
    d = proposal_to_dict(p)
    assert "filter_result" not in d
    p2 = proposal_from_dict(d)
    assert p2.filter_result is None


def test_proposals_json_round_trip():
    proposals = [make_proposal(), make_proposal()]
    proposals[1].proposal_id = "test-pid-002"
    json_str = proposals_to_json(proposals)
    loaded = proposals_from_json(json_str)
    assert len(loaded) == 2
    assert loaded[1].proposal_id == "test-pid-002"


def test_bounding_box_area():
    b = BoundingBox(0, 0, 10, 20)
    assert b.area() == 200.0


def test_bounding_box_tuple():
    b = BoundingBox(1.0, 2.0, 3.0, 4.0)
    assert b.to_tuple() == (1.0, 2.0, 3.0, 4.0)
    b2 = BoundingBox.from_tuple((5.0, 6.0, 7.0, 8.0))
    assert b2.x1 == 5.0
