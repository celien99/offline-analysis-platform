# Camera Config Page & Inspection Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a camera configuration management page with database-backed storage, and integrate it with the inspection page via dropdown selection.

**Architecture:** New `seat_models` and `camera_configs` tables store user-editable config; a `ConfigBuilder` service merges DB config with hardcoded defaults to generate the full JSON for `seat_defect_core`; the inspection flow switches from reading `config.example.json` to using dynamically generated config.

**Tech Stack:** FastAPI + SQLAlchemy (async) + Alembic + Pydantic + React + Ant Design + React Query

---

## File Structure

```
Backend (create/modify):
  backend/app/models/camera_config.py          # NEW: SeatModel + CameraConfig ORM models
  backend/app/models/__init__.py               # MODIFY: export new models
  backend/alembic/versions/007_add_camera_config.py  # NEW: migration
  backend/app/schemas/camera_config.py         # NEW: Pydantic request/response schemas
  backend/app/repositories/camera_config.py    # NEW: SeatModelRepo + CameraConfigRepo
  backend/app/services/camera_config/          # NEW: ConfigBuilder service
    __init__.py
    builder.py
  backend/app/api/camera_config/               # NEW: CRUD + options router
    __init__.py
    router.py
  backend/app/api/inspection/router.py         # MODIFY: use DB config instead of file

Frontend (create/modify):
  frontend/src/types/camera-config.ts          # NEW: TypeScript types
  frontend/src/api/camera-config.ts            # NEW: API functions
  frontend/src/hooks/queries.ts                # MODIFY: add camera config hooks
  frontend/src/features/camera-config/         # NEW: Camera config page
    index.tsx
  frontend/src/features/inspection/index.tsx   # MODIFY: dropdown selection
  frontend/src/app/router.tsx                  # MODIFY: add /cameras route
  frontend/src/app/layout.tsx                  # MODIFY: add menu item
```

---

### Task 1: ORM Models

**Files:**
- Create: `backend/app/models/camera_config.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Write the ORM models**

```python
# backend/app/models/camera_config.py
from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class SeatModel(BaseModel):
    __tablename__ = "seat_models"

    seat_model_id: Mapped[str] = mapped_column(
        String(128), unique=True, nullable=False, index=True,
        comment="座椅型号标识符，如 seat_model_a",
    )
    display_name: Mapped[str] = mapped_column(
        String(256), nullable=False, comment="前端显示名称",
    )


class CameraConfig(BaseModel):
    __tablename__ = "camera_configs"
    __table_args__ = (
        UniqueConstraint("seat_model_id", "camera_id", name="uq_seat_camera"),
    )

    camera_id: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="相机标识符",
    )
    seat_model_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("seat_models.seat_model_id", ondelete="CASCADE"),
        nullable=False, index=True, comment="所属座椅型号",
    )
    patchcore_model_path: Mapped[str] = mapped_column(
        String(512), nullable=False, comment="整体 PatchCore 模型路径",
    )
    yolo_model_path: Mapped[str] = mapped_column(
        String(512), nullable=False, comment="YOLO 检测模型路径",
    )
    detection_confidence: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.25, comment="YOLO 置信度阈值",
    )
    patchcore_image_size: Mapped[int] = mapped_column(
        Integer, nullable=False, default=256, comment="PatchCore 输入图像尺寸",
    )
    patchcore_threshold: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.99, comment="PatchCore 异常阈值分位数",
    )
    region_mode_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="是否启用三分区模式",
    )
    region_upper_model_path: Mapped[str | None] = mapped_column(
        String(512), nullable=True, comment="upper 区域 PatchCore 模型路径",
    )
    region_middle_model_path: Mapped[str | None] = mapped_column(
        String(512), nullable=True, comment="middle 区域 PatchCore 模型路径",
    )
    region_lower_model_path: Mapped[str | None] = mapped_column(
        String(512), nullable=True, comment="lower 区域 PatchCore 模型路径",
    )
```

- [ ] **Step 2: Register models in __init__.py**

```python
# backend/app/models/__init__.py — add these lines after existing imports:
from app.models.camera_config import CameraConfig, SeatModel

# and add to __all__:
"CameraConfig",
"SeatModel",
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/models/camera_config.py backend/app/models/__init__.py
git commit -m "feat: add SeatModel and CameraConfig ORM models"
```

---

### Task 2: Database Migration

**Files:**
- Create: `backend/alembic/versions/007_add_camera_config.py`

- [ ] **Step 1: Write migration**

```python
# backend/alembic/versions/007_add_camera_config.py
"""Add seat_models and camera_configs tables.

Revision ID: 007
Revises: 006
Create Date: 2026-05-25
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: str | None = "006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "seat_models",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "seat_model_id", sa.String(128), unique=True, nullable=False, index=True,
            comment="座椅型号标识符",
        ),
        sa.Column(
            "display_name", sa.String(256), nullable=False,
            comment="前端显示名称",
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trace_id", sa.String(32), nullable=True),
    )

    op.create_table(
        "camera_configs",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "camera_id", sa.String(128), nullable=False,
            comment="相机标识符",
        ),
        sa.Column(
            "seat_model_id", sa.String(128),
            sa.ForeignKey("seat_models.seat_model_id", ondelete="CASCADE"),
            nullable=False, index=True, comment="所属座椅型号",
        ),
        sa.Column(
            "patchcore_model_path", sa.String(512), nullable=False,
            comment="整体 PatchCore 模型路径",
        ),
        sa.Column(
            "yolo_model_path", sa.String(512), nullable=False,
            comment="YOLO 检测模型路径",
        ),
        sa.Column(
            "detection_confidence", sa.Float, nullable=False, server_default="0.25",
            comment="YOLO 置信度阈值",
        ),
        sa.Column(
            "patchcore_image_size", sa.Integer, nullable=False, server_default="256",
            comment="PatchCore 输入图像尺寸",
        ),
        sa.Column(
            "patchcore_threshold", sa.Float, nullable=False, server_default="0.99",
            comment="PatchCore 异常阈值分位数",
        ),
        sa.Column(
            "region_mode_enabled", sa.Boolean, nullable=False, server_default="0",
            comment="是否启用三分区模式",
        ),
        sa.Column(
            "region_upper_model_path", sa.String(512), nullable=True,
            comment="upper 区域 PatchCore 模型路径",
        ),
        sa.Column(
            "region_middle_model_path", sa.String(512), nullable=True,
            comment="middle 区域 PatchCore 模型路径",
        ),
        sa.Column(
            "region_lower_model_path", sa.String(512), nullable=True,
            comment="lower 区域 PatchCore 模型路径",
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trace_id", sa.String(32), nullable=True),
        sa.UniqueConstraint("seat_model_id", "camera_id", name="uq_seat_camera"),
    )


def downgrade() -> None:
    op.drop_table("camera_configs")
    op.drop_table("seat_models")
```

- [ ] **Step 2: Run migration**

```bash
cd backend && uv run alembic upgrade head
```
Expected: "Running upgrade 006 -> 007"

- [ ] **Step 3: Commit**

```bash
git add backend/alembic/versions/007_add_camera_config.py
git commit -m "feat: add seat_models and camera_configs migration"
```

---

### Task 3: Pydantic Schemas

**Files:**
- Create: `backend/app/schemas/camera_config.py`

- [ ] **Step 1: Write schemas**

```python
# backend/app/schemas/camera_config.py
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# ── Seat Model ──

class SeatModelCreate(BaseModel):
    seat_model_id: str = Field(..., max_length=128, description="座椅型号标识符")
    display_name: str = Field(..., max_length=256, description="显示名称")


class SeatModelUpdate(BaseModel):
    seat_model_id: str | None = Field(default=None, max_length=128)
    display_name: str | None = Field(default=None, max_length=256)


class SeatModelResponse(BaseModel):
    id: str
    seat_model_id: str
    display_name: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SeatModelWithCameras(SeatModelResponse):
    cameras: list[CameraConfigResponse] = []


# ── Camera Config ──

class CameraConfigCreate(BaseModel):
    camera_id: str = Field(..., max_length=128, description="相机标识符")
    patchcore_model_path: str = Field(..., max_length=512, description="PatchCore 模型路径")
    yolo_model_path: str = Field(..., max_length=512, description="YOLO 检测模型路径")
    detection_confidence: float = Field(default=0.25, ge=0.0, le=1.0)
    patchcore_image_size: int = Field(default=256, ge=64, le=1024)
    patchcore_threshold: float = Field(default=0.99, ge=0.0, le=1.0)
    region_mode_enabled: bool = False
    region_upper_model_path: str | None = Field(default=None, max_length=512)
    region_middle_model_path: str | None = Field(default=None, max_length=512)
    region_lower_model_path: str | None = Field(default=None, max_length=512)


class CameraConfigUpdate(BaseModel):
    camera_id: str | None = Field(default=None, max_length=128)
    patchcore_model_path: str | None = Field(default=None, max_length=512)
    yolo_model_path: str | None = Field(default=None, max_length=512)
    detection_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    patchcore_image_size: int | None = Field(default=None, ge=64, le=1024)
    patchcore_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    region_mode_enabled: bool | None = None
    region_upper_model_path: str | None = Field(default=None, max_length=512)
    region_middle_model_path: str | None = Field(default=None, max_length=512)
    region_lower_model_path: str | None = Field(default=None, max_length=512)


class CameraConfigResponse(BaseModel):
    id: str
    camera_id: str
    seat_model_id: str
    patchcore_model_path: str
    yolo_model_path: str
    detection_confidence: float
    patchcore_image_size: int
    patchcore_threshold: float
    region_mode_enabled: bool
    region_upper_model_path: str | None
    region_middle_model_path: str | None
    region_lower_model_path: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Options (dropdown) ──

class CameraOption(BaseModel):
    camera_id: str


class SeatModelOption(BaseModel):
    seat_model_id: str
    display_name: str
    cameras: list[CameraOption] = []
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/schemas/camera_config.py
git commit -m "feat: add camera config Pydantic schemas"
```

---

### Task 4: Repositories

**Files:**
- Create: `backend/app/repositories/camera_config.py`

- [ ] **Step 1: Write repositories**

```python
# backend/app/repositories/camera_config.py
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.camera_config import CameraConfig, SeatModel
from app.repositories.base import BaseRepository


class SeatModelRepository(BaseRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, SeatModel)

    async def get_by_seat_model_id(self, seat_model_id: str) -> SeatModel | None:
        stmt = select(self._model).where(
            self._model.seat_model_id == seat_model_id,
            self._model.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_with_cameras(self) -> list[SeatModel]:
        stmt = (
            select(self._model)
            .where(self._model.deleted_at.is_(None))
            .order_by(self._model.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class CameraConfigRepository(BaseRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, CameraConfig)

    async def list_by_seat_model(self, seat_model_id: str) -> list[CameraConfig]:
        stmt = (
            select(self._model)
            .where(
                self._model.seat_model_id == seat_model_id,
                self._model.deleted_at.is_(None),
            )
            .order_by(self._model.camera_id)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_camera_id(
        self, seat_model_id: str, camera_id: str
    ) -> CameraConfig | None:
        stmt = select(self._model).where(
            self._model.seat_model_id == seat_model_id,
            self._model.camera_id == camera_id,
            self._model.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/repositories/camera_config.py
git commit -m "feat: add SeatModel and CameraConfig repositories"
```

---

### Task 5: Config Builder Service

**Files:**
- Create: `backend/app/services/camera_config/__init__.py`
- Create: `backend/app/services/camera_config/builder.py`

- [ ] **Step 1: Write builder service**

```python
# backend/app/services/camera_config/__init__.py
from __future__ import annotations

from app.services.camera_config.builder import ConfigBuilder

__all__ = ["ConfigBuilder"]
```

```python
# backend/app/services/camera_config/builder.py
"""根据数据库配置生成完整的 seat_defect_core 检测配置 JSON。"""

from __future__ import annotations

import json
from pathlib import Path

from app.models.camera_config import CameraConfig


class ConfigBuilder:
    """将 DB 中的相机配置与硬编码默认参数合并，生成完整配置 JSON。

    默认参数来自 seat_defect_core/config.example.json，仅暴露相机级的少量字段给用户配置，
    YOLO/ROI/PatchCore/Filter/Color/Rule 等底层参数使用代码内默认值。
    """

    # 默认参数模板（仅包含用户不可配的底层字段）
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
        "alignment": {
            "output_width": 256,
            "output_height": 256,
        },
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
        self._repo_root = Path(repo_root) if repo_root else Path(__file__).resolve().parent.parent.parent.parent.parent

    def build(
        self,
        seat_model_id: str,
        display_name: str,
        cameras: list[CameraConfig],
        selected_camera_ids: list[str] | None = None,
        *,
        part_id: str = "seat_demo",
        upload_base_url: str = "http://localhost:8000",
    ) -> dict:
        """生成完整的检测配置字典。

        Args:
            seat_model_id: 座椅型号 ID
            display_name: 显示名称
            cameras: 该型号下的所有相机配置
            selected_camera_ids: 本次检测选中的 camera_id 列表，None 表示全部
            part_id: 零件 ID
            upload_base_url: 异常上传地址
        """
        selected_ids = set(selected_camera_ids) if selected_camera_ids else None

        camera_configs = []
        for cam in cameras:
            if selected_ids is not None and cam.camera_id not in selected_ids:
                continue
            camera_configs.append(self._build_camera_config(cam))

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
        """将用户输入的相对路径转为绝对路径，使其在临时配置目录中也能正确解析。"""
        p = Path(raw)
        if p.is_absolute():
            return str(p)
        return str(self._repo_root / raw)

    def _build_camera_config(self, cam: CameraConfig) -> dict:
        detection = dict(self.DEFAULT_DETECTION)
        detection["model_path"] = self._resolve_path(cam.yolo_model_path)
        detection["confidence"] = cam.detection_confidence

        patchcore = dict(self.DEFAULT_PATCHCORE)
        patchcore["image_size"] = cam.patchcore_image_size
        patchcore["threshold_quantile"] = cam.patchcore_threshold

        config: dict = {
            "camera_id": cam.camera_id,
            "patchcore_model_path": self._resolve_path(cam.patchcore_model_path),
            "source": "",
            "enabled": True,
            "color_insensitive_mode": True,
            "quality": dict(self.DEFAULT_QUALITY),
            "detection": detection,
            "roi": dict(self.DEFAULT_ROI),
            "patchcore": patchcore,
            "color_branch": dict(self.DEFAULT_COLOR_BRANCH),
            "filter_classifier": _resolve_default_filter_classifier(),
            "rule_engine": _resolve_default_rule_engine(),
            "rule_engine": dict(self.DEFAULT_RULE_ENGINE),
            "regions": [],
        }

        # 三分区模式
        if cam.region_mode_enabled:
            region_patchcore_overrides = {
                "backbone_pretrained": True,
                "min_target_coverage": 0.5,
                "min_valid_patch_ratio": 0.35,
            }
            config["regions"] = [
                {
                    "region_id": "upper",
                    "box": [0.03, 0.03, 0.97, 0.42],
                    "patchcore_model_path": self._resolve_path(cam.region_upper_model_path) if cam.region_upper_model_path else "",
                    "enabled": bool(cam.region_upper_model_path),
                    "patchcore": region_patchcore_overrides,
                },
                {
                    "region_id": "middle",
                    "box": [0.03, 0.38, 0.97, 0.67],
                    "patchcore_model_path": self._resolve_path(cam.region_middle_model_path) if cam.region_middle_model_path else "",
                    "enabled": bool(cam.region_middle_model_path),
                    "patchcore": region_patchcore_overrides,
                },
                {
                    "region_id": "lower",
                    "box": [0.03, 0.66, 0.97, 0.97],
                    "patchcore_model_path": self._resolve_path(cam.region_lower_model_path) if cam.region_lower_model_path else "",
                    "enabled": bool(cam.region_lower_model_path),
                    "patchcore": region_patchcore_overrides,
                },
            ]

        return config
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/camera_config/
git commit -m "feat: add ConfigBuilder service for dynamic config generation"
```

---

### Task 6: API Router — CRUD + Options

**Files:**
- Create: `backend/app/api/camera_config/__init__.py`
- Create: `backend/app/api/camera_config/router.py`

- [ ] **Step 1: Write router**

```python
# backend/app/api/camera_config/__init__.py
from __future__ import annotations

from app.api.camera_config.router import router

__all__ = ["router"]
```

```python
# backend/app/api/camera_config/router.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.repositories.camera_config import CameraConfigRepository, SeatModelRepository
from app.schemas.camera_config import (
    CameraConfigCreate,
    CameraConfigResponse,
    CameraConfigUpdate,
    SeatModelCreate,
    SeatModelOption,
    SeatModelResponse,
    SeatModelUpdate,
    SeatModelWithCameras,
)

router = APIRouter(prefix="/api/seat-models", tags=["camera-config"])


# ── Seat Models CRUD ──

@router.get("/options", response_model=list[SeatModelOption])
async def list_seat_model_options(
    session: AsyncSession = Depends(get_session),
) -> list[SeatModelOption]:
    """获取所有座椅型号及关联相机，供检测页面下拉框使用。"""
    seat_repo = SeatModelRepository(session)
    cam_repo = CameraConfigRepository(session)
    seat_models = await seat_repo.list_with_cameras()
    result: list[SeatModelOption] = []
    for sm in seat_models:
        cameras = await cam_repo.list_by_seat_model(sm.seat_model_id)
        result.append(
            SeatModelOption(
                seat_model_id=sm.seat_model_id,
                display_name=sm.display_name,
                cameras=[
                    {"camera_id": c.camera_id}
                    for c in cameras
                ],
            )
        )
    return result


@router.get("", response_model=list[SeatModelResponse])
async def list_seat_models(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> list[SeatModelResponse]:
    seat_repo = SeatModelRepository(session)
    offset = (page - 1) * page_size
    models = await seat_repo.list_all(offset=offset, limit=page_size)
    return [SeatModelResponse.model_validate(m) for m in models]


@router.post("", response_model=SeatModelResponse, status_code=201)
async def create_seat_model(
    data: SeatModelCreate,
    session: AsyncSession = Depends(get_session),
) -> SeatModelResponse:
    seat_repo = SeatModelRepository(session)
    existing = await seat_repo.get_by_seat_model_id(data.seat_model_id)
    if existing:
        raise HTTPException(status_code=409, detail="seat_model_id 已存在")
    from app.models.camera_config import SeatModel
    entity = SeatModel(
        seat_model_id=data.seat_model_id,
        display_name=data.display_name,
    )
    await seat_repo.create(entity)
    await session.commit()
    return SeatModelResponse.model_validate(entity)


@router.put("/{seat_model_db_id}", response_model=SeatModelResponse)
async def update_seat_model(
    seat_model_db_id: str,
    data: SeatModelUpdate,
    session: AsyncSession = Depends(get_session),
) -> SeatModelResponse:
    seat_repo = SeatModelRepository(session)
    entity = await seat_repo.get_by_id(seat_model_db_id)
    if not entity:
        raise HTTPException(status_code=404, detail="座椅型号不存在")
    if data.seat_model_id is not None:
        entity.seat_model_id = data.seat_model_id
    if data.display_name is not None:
        entity.display_name = data.display_name
    await seat_repo.update(entity)
    await session.commit()
    return SeatModelResponse.model_validate(entity)


@router.delete("/{seat_model_db_id}", status_code=204)
async def delete_seat_model(
    seat_model_db_id: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    seat_repo = SeatModelRepository(session)
    entity = await seat_repo.get_by_id(seat_model_db_id)
    if not entity:
        raise HTTPException(status_code=404, detail="座椅型号不存在")
    await seat_repo.soft_delete(seat_model_db_id)
    await session.commit()


# ── Camera Config CRUD ──

@router.get(
    "/{seat_model_id}/cameras",
    response_model=list[CameraConfigResponse],
)
async def list_cameras(
    seat_model_id: str,
    session: AsyncSession = Depends(get_session),
) -> list[CameraConfigResponse]:
    cam_repo = CameraConfigRepository(session)
    cameras = await cam_repo.list_by_seat_model(seat_model_id)
    return [CameraConfigResponse.model_validate(c) for c in cameras]


@router.post(
    "/{seat_model_id}/cameras",
    response_model=CameraConfigResponse,
    status_code=201,
)
async def create_camera(
    seat_model_id: str,
    data: CameraConfigCreate,
    session: AsyncSession = Depends(get_session),
) -> CameraConfigResponse:
    seat_repo = SeatModelRepository(session)
    seat_model = await seat_repo.get_by_seat_model_id(seat_model_id)
    if not seat_model:
        raise HTTPException(status_code=404, detail="座椅型号不存在")

    cam_repo = CameraConfigRepository(session)
    existing = await cam_repo.get_by_camera_id(seat_model_id, data.camera_id)
    if existing:
        raise HTTPException(status_code=409, detail="同一座椅型号下 camera_id 已存在")

    from app.models.camera_config import CameraConfig
    entity = CameraConfig(
        seat_model_id=seat_model_id,
        **data.model_dump(),
    )
    await cam_repo.create(entity)
    await session.commit()
    return CameraConfigResponse.model_validate(entity)


@router.put(
    "/{seat_model_id}/cameras/{camera_db_id}",
    response_model=CameraConfigResponse,
)
async def update_camera(
    seat_model_id: str,
    camera_db_id: str,
    data: CameraConfigUpdate,
    session: AsyncSession = Depends(get_session),
) -> CameraConfigResponse:
    cam_repo = CameraConfigRepository(session)
    entity = await cam_repo.get_by_id(camera_db_id)
    if not entity:
        raise HTTPException(status_code=404, detail="相机配置不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(entity, key, value)
    await cam_repo.update(entity)
    await session.commit()
    return CameraConfigResponse.model_validate(entity)


@router.delete("/{seat_model_id}/cameras/{camera_db_id}", status_code=204)
async def delete_camera(
    seat_model_id: str,
    camera_db_id: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    cam_repo = CameraConfigRepository(session)
    entity = await cam_repo.get_by_id(camera_db_id)
    if not entity:
        raise HTTPException(status_code=404, detail="相机配置不存在")
    await cam_repo.soft_delete(camera_db_id)
    await session.commit()
```

- [ ] **Step 2: Register router in FastAPI app**

Find the main app file to register the router.

```bash
grep -rn "include_router" backend/app/main.py
```

Add after the last `include_router` line:
```python
from app.api.camera_config import router as camera_config_router
app.include_router(camera_config_router)
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/camera_config/ backend/app/main.py
git commit -m "feat: add camera config CRUD API endpoints"
```

---

### Task 7: Modify Inspection Router to Use DB Config

**Files:**
- Modify: `backend/app/api/inspection/router.py`

- [ ] **Step 1: Rewrite run-inspection endpoint**

Replace the `run_inspection_with_files` function to:
1. Accept `seat_model_id` (required) + `camera_ids` (comma-separated)
2. Read camera configs from DB
3. Generate config JSON via ConfigBuilder
4. Write config to temp file for seat_defect_core

```python
# backend/app/api/inspection/router.py — replace the POST endpoint:

@router.post("/run-with-files", response_model=StatusResponse)
async def run_inspection_with_files(
    seat_model_id: str = Form(..., description="座椅型号 ID"),
    camera_ids: str = Form(..., description="逗号分隔的 camera_id 列表"),
    image_files: list[UploadFile] = File(..., description="与 camera_ids 顺序对应的图像文件"),
    part_id: str | None = Form(None),
    session: AsyncSession = Depends(get_session),
) -> StatusResponse:
    camera_id_list = [cid.strip() for cid in camera_ids.split(",") if cid.strip()]

    if len(camera_id_list) != len(image_files):
        return StatusResponse(
            status="error",
            message=f"camera_ids 数量 ({len(camera_id_list)}) 与 image_files 数量 ({len(image_files)}) 不匹配",
        )

    # 从数据库读取相机配置
    cam_repo = CameraConfigRepository(session)
    seat_repo = SeatModelRepository(session)
    seat_model = await seat_repo.get_by_seat_model_id(seat_model_id)
    if not seat_model:
        return StatusResponse(status="error", message=f"座椅型号不存在: {seat_model_id}")

    # 验证所有 camera_id 都有配置
    cameras = await cam_repo.list_by_seat_model(seat_model_id)
    db_camera_ids = {c.camera_id for c in cameras}
    for cid in camera_id_list:
        if cid not in db_camera_ids:
            return StatusResponse(
                status="error",
                message=f"相机 {cid} 在座椅型号 {seat_model_id} 下无配置",
            )

    # 生成完整配置文件
    from app.services.camera_config.builder import ConfigBuilder
    builder = ConfigBuilder()
    config_dict = builder.build(
        seat_model_id=seat_model_id,
        display_name=seat_model.display_name,
        cameras=cameras,
        selected_camera_ids=camera_id_list,
        upload_base_url=settings.backend_base_url,
    )

    # 保存图像到临时目录
    tmp_dir = tempfile.mkdtemp(prefix="inspection_images_")
    camera_image_paths: dict[str, str] = {}

    try:
        import json
        # 将配置写入临时文件
        config_path = str(Path(tmp_dir) / "config.json")
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_dict, f, ensure_ascii=False, indent=2)

        for i, (camera_id, img_file) in enumerate(zip(camera_id_list, image_files)):
            content = await img_file.read()
            ext = Path(img_file.filename or f"image_{i}").suffix or ".jpg"
            save_path = str(Path(tmp_dir) / f"{camera_id}{ext}")
            with open(save_path, "wb") as f:
                f.write(content)
            camera_image_paths[camera_id] = save_path

        task = run_inspection_task.delay(
            config_path=config_path,
            camera_image_paths=camera_image_paths,
            seat_model_id=seat_model_id,
            part_id=part_id,
        )

        logger.info(
            "inspection_dispatched",
            task_id=task.id,
            seat_model_id=seat_model_id,
            camera_count=len(camera_id_list),
        )
        return StatusResponse(
            status="queued",
            message=f"Inspection task {task.id} dispatched",
            task_id=task.id,
        )
    except Exception as e:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise e
```

Also add the new imports at the top:
```python
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_session
from app.repositories.camera_config import CameraConfigRepository, SeatModelRepository
```

- [ ] **Step 2: Verify the old config_path logic is removed**

The old code had:
```python
config_path = Path(settings.default_inspection_config).resolve()
```
This should be replaced by the dynamic config generation above.

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/inspection/router.py
git commit -m "feat: switch inspection to use DB camera config instead of static file"
```

---

### Task 8: Frontend Types

**Files:**
- Create: `frontend/src/types/camera-config.ts`

- [ ] **Step 1: Write types**

```typescript
// frontend/src/types/camera-config.ts
export interface CameraOption {
  camera_id: string;
}

export interface SeatModelOption {
  seat_model_id: string;
  display_name: string;
  cameras: CameraOption[];
}

export interface SeatModel {
  id: string;
  seat_model_id: string;
  display_name: string;
  created_at: string;
  updated_at: string;
}

export interface CameraConfig {
  id: string;
  camera_id: string;
  seat_model_id: string;
  patchcore_model_path: string;
  yolo_model_path: string;
  detection_confidence: number;
  patchcore_image_size: number;
  patchcore_threshold: number;
  region_mode_enabled: boolean;
  region_upper_model_path: string | null;
  region_middle_model_path: string | null;
  region_lower_model_path: string | null;
  created_at: string;
  updated_at: string;
}

export interface CameraConfigFormData {
  camera_id: string;
  patchcore_model_path: string;
  yolo_model_path: string;
  detection_confidence: number;
  patchcore_image_size: number;
  patchcore_threshold: number;
  region_mode_enabled: boolean;
  region_upper_model_path: string;
  region_middle_model_path: string;
  region_lower_model_path: string;
}

export interface SeatModelFormData {
  seat_model_id: string;
  display_name: string;
}
```

- [ ] **Step 2: Re-export from types/index.ts**

Check if there is a barrel export:
```bash
grep -r "export.*from.*types" frontend/src/types/ 2>/dev/null || echo "check types/index.ts"
```

If `frontend/src/types/index.ts` exists, add: `export * from "./camera-config";`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/camera-config.ts frontend/src/types/index.ts
git commit -m "feat: add camera config TypeScript types"
```

---

### Task 9: Frontend API Functions

**Files:**
- Create: `frontend/src/api/camera-config.ts`

- [ ] **Step 1: Write API functions**

```typescript
// frontend/src/api/camera-config.ts
import { get, post, del } from "./client";
import http from "./client";
import type {
  SeatModel,
  SeatModelOption,
  CameraConfig,
  SeatModelFormData,
  CameraConfigFormData,
} from "../types";

export const cameraConfigApi = {
  // ── Seat Models ──
  listOptions: () => get<SeatModelOption[]>("/seat-models/options"),

  listSeatModels: (params?: { page: number; page_size: number }) =>
    get<SeatModel[]>("/seat-models", { params }),

  createSeatModel: (data: SeatModelFormData) =>
    post<SeatModel>("/seat-models", data),

  updateSeatModel: (id: string, data: Partial<SeatModelFormData>) =>
    http.put<SeatModel>(`/seat-models/${id}`, data).then((res) => res.data),

  deleteSeatModel: (id: string) => del(`/seat-models/${id}`),

  // ── Camera Configs ──
  listCameras: (seatModelId: string) =>
    get<CameraConfig[]>(`/seat-models/${seatModelId}/cameras`),

  createCamera: (seatModelId: string, data: CameraConfigFormData) =>
    post<CameraConfig>(`/seat-models/${seatModelId}/cameras`, data),

  updateCamera: (
    seatModelId: string,
    cameraDbId: string,
    data: Partial<CameraConfigFormData>,
  ) =>
    http
      .put<CameraConfig>(`/seat-models/${seatModelId}/cameras/${cameraDbId}`, data)
      .then((res) => res.data),

  deleteCamera: (seatModelId: string, cameraDbId: string) =>
    del(`/seat-models/${seatModelId}/cameras/${cameraDbId}`),
};
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/api/camera-config.ts
git commit -m "feat: add camera config API functions"
```

---

### Task 10: Frontend React Query Hooks

**Files:**
- Modify: `frontend/src/hooks/queries.ts`

- [ ] **Step 1: Add camera config hooks**

After the existing inspection hooks (around line 325), add:

```typescript
import { cameraConfigApi } from "../api/camera-config";

// ── Camera Config hooks ──

export function useSeatModelOptions() {
  return useQuery({
    queryKey: ["seat-models", "options"],
    queryFn: cameraConfigApi.listOptions,
    staleTime: 60_000,
  });
}

export function useSeatModels(page: number, pageSize: number) {
  return useQuery({
    queryKey: ["seat-models", page, pageSize],
    queryFn: () => cameraConfigApi.listSeatModels({ page, page_size: pageSize }),
  });
}

export function useCreateSeatModel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: cameraConfigApi.createSeatModel,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["seat-models"] });
    },
  });
}

export function useUpdateSeatModel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<SeatModelFormData> }) =>
      cameraConfigApi.updateSeatModel(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["seat-models"] });
    },
  });
}

export function useDeleteSeatModel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: cameraConfigApi.deleteSeatModel,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["seat-models"] });
    },
  });
}

export function useCameras(seatModelId: string | null) {
  return useQuery({
    queryKey: ["cameras", seatModelId],
    queryFn: () => cameraConfigApi.listCameras(seatModelId!),
    enabled: !!seatModelId,
  });
}

export function useCreateCamera() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      seatModelId,
      data,
    }: {
      seatModelId: string;
      data: CameraConfigFormData;
    }) => cameraConfigApi.createCamera(seatModelId, data),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["cameras", variables.seatModelId] });
      queryClient.invalidateQueries({ queryKey: ["seat-models", "options"] });
    },
  });
}

export function useUpdateCamera() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      seatModelId,
      cameraDbId,
      data,
    }: {
      seatModelId: string;
      cameraDbId: string;
      data: Partial<CameraConfigFormData>;
    }) => cameraConfigApi.updateCamera(seatModelId, cameraDbId, data),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["cameras", variables.seatModelId] });
      queryClient.invalidateQueries({ queryKey: ["seat-models", "options"] });
    },
  });
}

export function useDeleteCamera() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      seatModelId,
      cameraDbId,
    }: {
      seatModelId: string;
      cameraDbId: string;
    }) => cameraConfigApi.deleteCamera(seatModelId, cameraDbId),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["cameras", variables.seatModelId] });
      queryClient.invalidateQueries({ queryKey: ["seat-models", "options"] });
    },
  });
}
```

Also add the TypeScript import for the form types at the top of queries.ts:
```typescript
import type { SeatModelFormData, CameraConfigFormData } from "../types";
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/hooks/queries.ts
git commit -m "feat: add camera config React Query hooks"
```

---

### Task 11: Camera Config Page

**Files:**
- Create: `frontend/src/features/camera-config/index.tsx`

- [ ] **Step 1: Write the camera config page**

```tsx
import { useState } from "react";
import {
  Card,
  Table,
  Button,
  Modal,
  Form,
  Input,
  InputNumber,
  Switch,
  Space,
  message,
  Typography,
  Row,
  Col,
  List,
  Tag,
  Popconfirm,
} from "antd";
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  SettingOutlined,
} from "@ant-design/icons";
import PageHeader from "../../components/ui/PageHeader";
import {
  useSeatModels,
  useCreateSeatModel,
  useUpdateSeatModel,
  useDeleteSeatModel,
  useCameras,
  useCreateCamera,
  useUpdateCamera,
  useDeleteCamera,
} from "../../hooks/queries";
import type { CameraConfigFormData, SeatModelFormData, SeatModel, CameraConfig } from "../../types";

const PAGE_SIZE = 20;

export default function CameraConfigPage() {
  const [page, setPage] = useState(1);
  const [selectedSeatModel, setSelectedSeatModel] = useState<string | null>(null);
  const [seatModalOpen, setSeatModalOpen] = useState(false);
  const [editingSeat, setEditingSeat] = useState<SeatModel | null>(null);
  const [cameraModalOpen, setCameraModalOpen] = useState(false);
  const [editingCamera, setEditingCamera] = useState<CameraConfig | null>(null);
  const [seatForm] = Form.useForm<SeatModelFormData>();
  const [cameraForm] = Form.useForm<CameraConfigFormData>();

  const { data: seatModels, isLoading: seatLoading } = useSeatModels(page, PAGE_SIZE);
  const { data: cameras, isLoading: camerasLoading } = useCameras(selectedSeatModel);

  const createSeatMut = useCreateSeatModel();
  const updateSeatMut = useUpdateSeatModel();
  const deleteSeatMut = useDeleteSeatModel();
  const createCamMut = useCreateCamera();
  const updateCamMut = useUpdateCamera();
  const deleteCamMut = useDeleteCamera();

  // ── Seat Model handlers ──
  const openSeatCreate = () => {
    setEditingSeat(null);
    seatForm.resetFields();
    setSeatModalOpen(true);
  };

  const openSeatEdit = (record: SeatModel) => {
    setEditingSeat(record);
    seatForm.setFieldsValue({
      seat_model_id: record.seat_model_id,
      display_name: record.display_name,
    });
    setSeatModalOpen(true);
  };

  const handleSeatSubmit = async () => {
    const values = await seatForm.validateFields();
    if (editingSeat) {
      await updateSeatMut.mutateAsync({ id: editingSeat.id, data: values });
      message.success("座椅型号已更新");
    } else {
      await createSeatMut.mutateAsync(values);
      message.success("座椅型号已创建");
    }
    setSeatModalOpen(false);
  };

  const handleSeatDelete = async (id: string) => {
    await deleteSeatMut.mutateAsync(id);
    if (selectedSeatModel && seatModels?.find((s) => s.id === id)?.seat_model_id === selectedSeatModel) {
      setSelectedSeatModel(null);
    }
    message.success("座椅型号已删除");
  };

  // ── Camera Config handlers ──
  const openCameraCreate = () => {
    setEditingCamera(null);
    cameraForm.resetFields();
    cameraForm.setFieldsValue({
      detection_confidence: 0.25,
      patchcore_image_size: 256,
      patchcore_threshold: 0.99,
      region_mode_enabled: false,
      region_upper_model_path: "",
      region_middle_model_path: "",
      region_lower_model_path: "",
    });
    setCameraModalOpen(true);
  };

  const openCameraEdit = (record: CameraConfig) => {
    setEditingCamera(record);
    cameraForm.setFieldsValue({
      camera_id: record.camera_id,
      patchcore_model_path: record.patchcore_model_path,
      yolo_model_path: record.yolo_model_path,
      detection_confidence: record.detection_confidence,
      patchcore_image_size: record.patchcore_image_size,
      patchcore_threshold: record.patchcore_threshold,
      region_mode_enabled: record.region_mode_enabled,
      region_upper_model_path: record.region_upper_model_path ?? "",
      region_middle_model_path: record.region_middle_model_path ?? "",
      region_lower_model_path: record.region_lower_model_path ?? "",
    });
    setCameraModalOpen(true);
  };

  const handleCameraSubmit = async () => {
    const values = await cameraForm.validateFields();
    if (!selectedSeatModel) {
      message.error("请先选择一个座椅型号");
      return;
    }
    if (editingCamera) {
      await updateCamMut.mutateAsync({
        seatModelId: selectedSeatModel,
        cameraDbId: editingCamera.id,
        data: values,
      });
      message.success("相机配置已更新");
    } else {
      await createCamMut.mutateAsync({
        seatModelId: selectedSeatModel,
        data: values,
      });
      message.success("相机配置已创建");
    }
    setCameraModalOpen(false);
  };

  const handleCameraDelete = async (cameraDbId: string) => {
    if (!selectedSeatModel) return;
    await deleteCamMut.mutateAsync({ seatModelId: selectedSeatModel, cameraDbId });
    message.success("相机配置已删除");
  };

  const regionModeEnabled = Form.useWatch("region_mode_enabled", cameraForm);

  return (
    <div>
      <PageHeader title="相机配置" />

      <Row gutter={24}>
        {/* 左侧：座椅型号列表 */}
        <Col span={8}>
          <Card
            title="座椅型号"
            extra={
              <Button icon={<PlusOutlined />} size="small" onClick={openSeatCreate}>
                新建
              </Button>
            }
          >
            <List
              loading={seatLoading}
              dataSource={seatModels ?? []}
              renderItem={(item) => (
                <List.Item
                  onClick={() => setSelectedSeatModel(item.seat_model_id)}
                  className={
                    selectedSeatModel === item.seat_model_id
                      ? "bg-blue-50 cursor-pointer px-2 rounded"
                      : "cursor-pointer px-2 rounded"
                  }
                  actions={[
                    <Button
                      key="edit"
                      type="link"
                      size="small"
                      icon={<EditOutlined />}
                      onClick={(e) => {
                        e.stopPropagation();
                        openSeatEdit(item);
                      }}
                    />,
                    <Popconfirm
                      key="delete"
                      title="确定删除此座椅型号？"
                      onConfirm={(e) => {
                        e?.stopPropagation();
                        handleSeatDelete(item.id);
                      }}
                      onCancel={(e) => e?.stopPropagation()}
                    >
                      <Button
                        type="link"
                        size="small"
                        danger
                        icon={<DeleteOutlined />}
                        onClick={(e) => e.stopPropagation()}
                      />
                    </Popconfirm>,
                  ]}
                >
                  <List.Item.Meta
                    title={item.display_name}
                    description={item.seat_model_id}
                  />
                </List.Item>
              )}
            />
          </Card>
        </Col>

        {/* 右侧：相机配置表格 */}
        <Col span={16}>
          <Card
            title={
              selectedSeatModel
                ? `相机列表 — ${selectedSeatModel}`
                : "请选择左侧座椅型号"
            }
            extra={
              selectedSeatModel && (
                <Button icon={<PlusOutlined />} size="small" onClick={openCameraCreate}>
                  添加相机
                </Button>
              )
            }
          >
            {!selectedSeatModel && (
              <div className="text-center py-8">
                <SettingOutlined className="text-4xl text-gray-300 block mb-3" />
                <Typography.Text type="secondary">
                  请先选择左侧座椅型号
                </Typography.Text>
              </div>
            )}

            {selectedSeatModel && (
              <Table
                columns={[
                  { title: "相机ID", dataIndex: "camera_id", width: 120 },
                  {
                    title: "YOLO 模型",
                    dataIndex: "yolo_model_path",
                    ellipsis: true,
                    width: 200,
                  },
                  {
                    title: "PatchCore 模型",
                    dataIndex: "patchcore_model_path",
                    ellipsis: true,
                    width: 200,
                  },
                  {
                    title: "Region 模式",
                    dataIndex: "region_mode_enabled",
                    width: 100,
                    render: (v: boolean) => (
                      <Tag color={v ? "blue" : "default"}>{v ? "三分区" : "整体"}</Tag>
                    ),
                  },
                  {
                    title: "操作",
                    width: 120,
                    render: (_: unknown, record: CameraConfig) => (
                      <Space>
                        <Button
                          size="small"
                          icon={<EditOutlined />}
                          onClick={() => openCameraEdit(record)}
                        />
                        <Popconfirm
                          title="确定删除此相机配置？"
                          onConfirm={() => handleCameraDelete(record.id)}
                        >
                          <Button size="small" danger icon={<DeleteOutlined />} />
                        </Popconfirm>
                      </Space>
                    ),
                  },
                ]}
                dataSource={cameras ?? []}
                rowKey="id"
                loading={camerasLoading}
                pagination={false}
                size="small"
              />
            )}
          </Card>
        </Col>
      </Row>

      {/* 座椅型号 Modal */}
      <Modal
        title={editingSeat ? "编辑座椅型号" : "新建座椅型号"}
        open={seatModalOpen}
        onOk={handleSeatSubmit}
        onCancel={() => setSeatModalOpen(false)}
        confirmLoading={createSeatMut.isPending || updateSeatMut.isPending}
        destroyOnClose
      >
        <Form form={seatForm} layout="vertical">
          <Form.Item
            name="seat_model_id"
            label="座椅型号 ID"
            rules={[{ required: true, message: "请输入座椅型号 ID" }]}
          >
            <Input placeholder="如 seat_model_a" disabled={!!editingSeat} />
          </Form.Item>
          <Form.Item
            name="display_name"
            label="显示名称"
            rules={[{ required: true, message: "请输入显示名称" }]}
          >
            <Input placeholder="如 座椅型号A" />
          </Form.Item>
        </Form>
      </Modal>

      {/* 相机配置 Modal */}
      <Modal
        title={editingCamera ? "编辑相机配置" : "新建相机配置"}
        open={cameraModalOpen}
        onOk={handleCameraSubmit}
        onCancel={() => setCameraModalOpen(false)}
        confirmLoading={createCamMut.isPending || updateCamMut.isPending}
        width={640}
        destroyOnClose
      >
        <Form form={cameraForm} layout="vertical">
          <Form.Item
            name="camera_id"
            label="相机 ID"
            rules={[{ required: true, message: "请输入相机 ID" }]}
          >
            <Input placeholder="如 cam_back" disabled={!!editingCamera} />
          </Form.Item>
          <Form.Item
            name="yolo_model_path"
            label="YOLO 检测模型路径"
            rules={[{ required: true, message: "请输入 YOLO 模型路径" }]}
          >
            <Input placeholder="../models/yolo/best.pt" />
          </Form.Item>
          <Form.Item
            name="patchcore_model_path"
            label="PatchCore 模型路径"
            rules={[{ required: true, message: "请输入 PatchCore 模型路径" }]}
          >
            <Input placeholder="../models/seat_model_a/cam_0_lower_patchcore.npz" />
          </Form.Item>

          <Typography.Title level={5}>高级参数</Typography.Title>
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="detection_confidence" label="YOLO 置信度">
                <InputNumber min={0} max={1} step={0.05} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="patchcore_image_size" label="PatchCore 图像尺寸">
                <InputNumber min={64} max={1024} step={32} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="patchcore_threshold" label="PatchCore 阈值">
                <InputNumber min={0} max={1} step={0.01} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item name="region_mode_enabled" label="Region 分区模式" valuePropName="checked">
            <Switch />
          </Form.Item>

          {regionModeEnabled && (
            <>
              <Form.Item
                name="region_upper_model_path"
                label="Upper 区域 PatchCore 模型"
                rules={[{ required: true, message: "请输入 upper 区域模型路径" }]}
              >
                <Input placeholder="../models/.../cam_0_upper_patchcore.npz" />
              </Form.Item>
              <Form.Item
                name="region_middle_model_path"
                label="Middle 区域 PatchCore 模型"
                rules={[{ required: true, message: "请输入 middle 区域模型路径" }]}
              >
                <Input placeholder="../models/.../cam_0_middle_patchcore.npz" />
              </Form.Item>
              <Form.Item
                name="region_lower_model_path"
                label="Lower 区域 PatchCore 模型"
                rules={[{ required: true, message: "请输入 lower 区域模型路径" }]}
              >
                <Input placeholder="../models/.../cam_0_lower_patchcore.npz" />
              </Form.Item>
            </>
          )}
        </Form>
      </Modal>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/features/camera-config/
git commit -m "feat: add camera config management page"
```

---

### Task 12: Inspection Page — Dropdown Integration

**Files:**
- Modify: `frontend/src/features/inspection/index.tsx`

- [ ] **Step 1: Rewrite inspection page with dropdown selection**

```tsx
import { useState } from "react";
import {
  Card,
  Table,
  Button,
  Tag,
  Upload,
  Space,
  message,
  Typography,
  Descriptions,
  Row,
  Col,
  Progress,
  Spin,
  Select,
} from "antd";
import {
  PlayCircleOutlined,
  InboxOutlined,
  ScanOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import PageHeader from "../../components/ui/PageHeader";
import { useInspectionRun, useInspectionResult, useSeatModelOptions } from "../../hooks/queries";
import type { SeatModelOption, CameraOption } from "../../types";

const { Dragger } = Upload;

interface CameraSlot {
  cameraId: string;
  file: File | null;
}

export default function InspectionPage() {
  const [selectedSeatModel, setSelectedSeatModel] = useState<string | null>(null);
  const [selectedCameras, setSelectedCameras] = useState<string[]>([]);
  const [slots, setSlots] = useState<CameraSlot[]>([]);
  const [taskId, setTaskId] = useState<string | null>(null);

  const { data: seatModelOptions, isLoading: optionsLoading } = useSeatModelOptions();
  const runMutation = useInspectionRun();
  const { data: result } = useInspectionResult(taskId);

  // 找到当前选中座椅型号的配置
  const currentSeatModel: SeatModelOption | undefined = seatModelOptions?.find(
    (s) => s.seat_model_id === selectedSeatModel,
  );

  // 座椅型号切换时，自动生成相机槽位
  const handleSeatModelChange = (seatModelId: string) => {
    setSelectedSeatModel(seatModelId);
    // 默认选中所有相机
    const model = seatModelOptions?.find((s) => s.seat_model_id === seatModelId);
    if (model) {
      const allCameraIds = model.cameras.map((c) => c.camera_id);
      setSelectedCameras(allCameraIds);
      setSlots(allCameraIds.map((cid) => ({ cameraId: cid, file: null })));
    }
  };

  // 相机多选变化时更新槽位
  const handleCamerasChange = (cameraIds: string[]) => {
    setSelectedCameras(cameraIds);
    setSlots(
      cameraIds.map((cid) => {
        const existing = slots.find((s) => s.cameraId === cid);
        return existing ?? { cameraId: cid, file: null };
      }),
    );
  };

  const updateSlotFile = (cameraId: string, file: File | null) => {
    setSlots(slots.map((s) => (s.cameraId === cameraId ? { ...s, file } : s)));
  };

  const handleRun = () => {
    if (!selectedSeatModel) {
      message.error("请选择座椅型号");
      return;
    }
    const filled = slots.filter((s) => s.file);
    if (filled.length === 0) {
      message.error("请至少上传一张图像");
      return;
    }

    const formData = new FormData();
    formData.append("seat_model_id", selectedSeatModel);
    formData.append("camera_ids", filled.map((s) => s.cameraId).join(","));
    filled.forEach((s) => formData.append("image_files", s.file!));

    runMutation.mutate(formData, {
      onSuccess: (data) => {
        message.success("检测任务已提交");
        setTaskId(data.task_id ?? null);
      },
      onError: () => message.error("检测任务提交失败"),
    });
  };

  const handleReset = () => {
    setTaskId(null);
    if (currentSeatModel) {
      setSlots(currentSeatModel.cameras.map((c) => ({ cameraId: c.camera_id, file: null })));
    }
  };

  const statusColor = (s: string) => {
    if (s === "OK" || s === "SUCCESS") return "green";
    if (s === "NG") return "red";
    if (s === "REJECT") return "orange";
    if (s === "FAILURE" || s === "FAILED") return "red";
    if (s === "PENDING" || s === "STARTED") return "blue";
    return "default";
  };

  const isRunning = !!taskId && (!result || result.status === "PENDING" || result.status === "STARTED");

  return (
    <div>
      <PageHeader
        title="在线检测"
        extra={
          <Button icon={<ReloadOutlined />} onClick={handleReset} disabled={isRunning}>
            重置
          </Button>
        }
      />

      <Row gutter={24}>
        {/* 左侧：配置区 */}
        <Col span={10}>
          <Card title={<Space><ScanOutlined />检测配置</Space>}>
            {/* Step 1: 选择座椅型号 */}
            <Typography.Text strong>1. 选择座椅型号</Typography.Text>
            <Select
              className="w-full mt-1 mb-4"
              placeholder="选择座椅型号"
              loading={optionsLoading}
              value={selectedSeatModel}
              onChange={handleSeatModelChange}
              disabled={isRunning}
              allowClear
              options={(seatModelOptions ?? []).map((s) => ({
                value: s.seat_model_id,
                label: `${s.display_name} (${s.seat_model_id})`,
              }))}
            />

            {/* Step 2: 选择相机 */}
            {currentSeatModel && (
              <>
                <Typography.Text strong>2. 选择相机</Typography.Text>
                <Select
                  className="w-full mt-1 mb-4"
                  mode="multiple"
                  placeholder="勾选检测相机"
                  value={selectedCameras}
                  onChange={handleCamerasChange}
                  disabled={isRunning}
                  options={currentSeatModel.cameras.map((c) => ({
                    value: c.camera_id,
                    label: c.camera_id,
                  }))}
                />
              </>
            )}

            {/* Step 3: 上传图像 */}
            {slots.length > 0 && (
              <>
                <Typography.Text strong>3. 上传图像</Typography.Text>
                {slots.map((slot) => (
                  <div key={slot.cameraId} className="mb-3 p-3 border rounded-lg border-gray-200">
                    <Typography.Text className="font-bold">{slot.cameraId}</Typography.Text>
                    <Dragger
                      accept="image/*"
                      maxCount={1}
                      disabled={isRunning}
                      beforeUpload={(file) => {
                        updateSlotFile(slot.cameraId, file);
                        return false;
                      }}
                      onRemove={() => updateSlotFile(slot.cameraId, null)}
                      className={slot.file ? "border-green-400" : ""}
                    >
                      <p className="ant-upload-drag-icon"><InboxOutlined /></p>
                      <p className="ant-upload-text">
                        {slot.file ? slot.file.name : "点击或拖拽图像到此区域"}
                      </p>
                    </Dragger>
                  </div>
                ))}
              </>
            )}

            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              size="large"
              block
              onClick={handleRun}
              loading={runMutation.isPending}
              disabled={isRunning || !selectedSeatModel || slots.length === 0}
            >
              开始检测
            </Button>
          </Card>
        </Col>

        {/* 右侧：检测结果 */}
        <Col span={14}>
          <Card title="检测结果">
            {isRunning && (
              <div className="text-center py-8">
                <Spin size="large" tip="检测运行中，请稍候..." />
              </div>
            )}

            {result && !isRunning && (
              <>
                <Descriptions column={2} size="small" bordered className="mb-4">
                  <Descriptions.Item label="任务 ID" span={2}>
                    {result.task_id}
                  </Descriptions.Item>
                  <Descriptions.Item label="任务状态">
                    <Tag color={statusColor(result.status)}>{result.status}</Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="整体结果">
                    <Tag color={statusColor(result.overall_status ?? "")}>
                      {result.overall_status ?? "-"}
                    </Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="决策原因" span={2}>
                    {result.decision_reason ?? "-"}
                  </Descriptions.Item>
                </Descriptions>

                {result.error_message && (
                  <Typography.Text type="danger" className="block mb-4">
                    {result.error_message}
                  </Typography.Text>
                )}

                {result.camera_results.length > 0 && (
                  <>
                    <Typography.Title level={5}>各相机结果</Typography.Title>
                    <Table
                      columns={[
                        { title: "相机ID", dataIndex: "camera_id", width: 120 },
                        {
                          title: "状态",
                          dataIndex: "status",
                          width: 90,
                          render: (s: string) => <Tag color={statusColor(s)}>{s}</Tag>,
                        },
                        {
                          title: "异常分数",
                          dataIndex: "anomaly_score",
                          width: 120,
                          render: (v: number | null) =>
                            v != null ? (
                              <Space size={4}>
                                <span className="text-xs">{v.toFixed(4)}</span>
                                <Progress
                                  percent={Math.min(v * 100, 100)}
                                  showInfo={false}
                                  size="small"
                                  strokeColor={v > 0.5 ? "#ff4d4f" : "#52c41a"}
                                  className="w-12 inline-block"
                                />
                              </Space>
                            ) : "-",
                        },
                        {
                          title: "是否异常",
                          dataIndex: "is_anomaly",
                          width: 90,
                          render: (v: boolean | null) =>
                            v == null ? "-" : <Tag color={v ? "red" : "green"}>{v ? "是" : "否"}</Tag>,
                        },
                        { title: "原因", dataIndex: "decision_reason", ellipsis: true },
                      ]}
                      dataSource={result.camera_results.map((r, i) => ({ ...r, key: i }))}
                      pagination={false}
                      size="small"
                    />

                    <Typography.Title level={5} className="mt-4">检测图像</Typography.Title>
                    <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
                      {result.camera_results.map((r) =>
                        r.overlay_image_base64 ? (
                          <Card
                            key={r.camera_id}
                            size="small"
                            title={r.camera_id}
                            extra={<Tag color={statusColor(r.status)}>{r.status}</Tag>}
                            style={{ width: 420 }}
                            styles={{ body: { padding: 0 } }}
                          >
                            <img
                              src={`data:image/jpeg;base64,${r.overlay_image_base64}`}
                              alt={`${r.camera_id} overlay`}
                              style={{ width: "100%", maxHeight: 400, objectFit: "contain", display: "block" }}
                            />
                          </Card>
                        ) : null,
                      )}
                    </div>
                  </>
                )}
              </>
            )}

            {!taskId && !result && (
              <div className="text-center py-8">
                <ScanOutlined className="text-4xl text-gray-300 block mb-3" />
                <Typography.Text type="secondary">
                  选择座椅型号和相机，上传图像后点击「开始检测」
                </Typography.Text>
              </div>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/features/inspection/index.tsx
git commit -m "feat: refactor inspection page with dropdown camera selection"
```

---

### Task 13: Router & Layout

**Files:**
- Modify: `frontend/src/app/router.tsx`
- Modify: `frontend/src/app/layout.tsx`

- [ ] **Step 1: Add route**

In `router.tsx`, add after the existing lazy imports:
```tsx
const CameraConfig = lazy(() => import("../features/camera-config"));
```

Add after existing routes:
```tsx
<Route path="/cameras" element={<CameraConfig />} />
```

- [ ] **Step 2: Add menu item**

In `layout.tsx`, add after the inspection menu item:
```tsx
{ key: "/cameras", icon: <SettingOutlined />, label: "相机配置" },
```

Also add `SettingOutlined` to the icon imports from `@ant-design/icons`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/router.tsx frontend/src/app/layout.tsx
git commit -m "feat: add /cameras route and menu item"
```

---

### Task 14: Final Verification

- [ ] **Step 1: Run backend type check**

```bash
cd backend && uv run mypy app/models/camera_config.py app/repositories/camera_config.py app/schemas/camera_config.py app/services/camera_config/ app/api/camera_config/
```

- [ ] **Step 2: Run frontend type check**

```bash
cd frontend && pnpm run build
```

- [ ] **Step 3: Test backend API**

Start the backend and verify:
```bash
# Create a seat model
curl -X POST http://localhost:8000/api/seat-models \
  -H "Content-Type: application/json" \
  -d '{"seat_model_id":"seat_model_a","display_name":"座椅型号A"}'

# Create a camera config
curl -X POST http://localhost:8000/api/seat-models/seat_model_a/cameras \
  -H "Content-Type: application/json" \
  -d '{"camera_id":"cam_back","patchcore_model_path":"../models/test.npz","yolo_model_path":"../models/yolo/best.pt"}'

# Get options
curl http://localhost:8000/api/seat-models/options
```

- [ ] **Step 4: Commit any fixes from verification**

```bash
git add -A && git commit -m "fix: type check and verification fixes"
```
