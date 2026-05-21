from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ReviewSubmitRequest(BaseModel):
    cluster_id: str = Field(...)
    reviewer: str = Field(..., max_length=64)
    action: str = Field(
        ...,
        pattern=r"^(confirm_defect|mark_false_alarm|rename|split|merge|ignore)$",
    )
    defect_type: str | None = Field(
        default=None,
        pattern=r"^(wrinkle|scratch|reflection|stain|seam_shift)$",
    )
    comment: str | None = Field(default=None, max_length=2000)
    new_cluster_name: str | None = Field(default=None, max_length=128)


class ReviewResponse(BaseModel):
    review_id: str
    cluster_id: str
    reviewer: str
    action: str
    defect_type: str | None
    comment: str | None
    new_status: str
    reviewed_at: datetime

    model_config = {"from_attributes": True}


class KnowledgeEntryRequest(BaseModel):
    cluster_id: str | None = None
    category: str = Field(..., pattern=r"^(defect|false_alarm|camera_issue|lighting|process)$")
    defect_type: str | None = None
    title: str = Field(..., max_length=256)
    description: str | None = None
    action: str = Field(default="ignore", pattern=r"^(ignore|NG|review_required)$")
    camera_ids: list[str] = []


class KnowledgeEntryResponse(BaseModel):
    knowledge_id: str
    cluster_id: str | None
    category: str
    defect_type: str | None
    title: str
    description: str | None
    action: str
    camera_ids: list[str] = []
    created_at: datetime

    model_config = {"from_attributes": True}
