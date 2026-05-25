"""Hot Reload API — 模型热切换、A/B 管理、重载信号"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.common.logging import get_logger
from app.services.hot_reload import HotReloadService

router = APIRouter(prefix="/api/hot-reload", tags=["hot_reload"])
logger = get_logger(__name__)


def _get_service() -> HotReloadService:
    return HotReloadService()


# ── 重载信号 ─────────────────────────────────────────

@router.post("/signal/{target}")
async def send_reload_signal(
    target: str,
    model_name: str = Query(...),
    model_version: str = Query(...),
    model_path: str = Query(default="model.pt"),
    reload_reason: str = Query(default="deploy"),
) -> dict:
    service = _get_service()
    signal = await service.send_reload_signal(
        target=target,
        model_name=model_name,
        model_version=model_version,
        model_path=model_path,
        reload_reason=reload_reason,
    )
    return {"status": "sent", "target": target, "signal": signal}


@router.get("/signal/{target}")
async def get_reload_signal(target: str) -> dict:
    service = _get_service()
    signal = await service.get_reload_signal(target)
    if signal is None:
        return {"status": "no_signal", "target": target}
    return {"status": "pending", "target": target, "signal": signal}


@router.delete("/signal/{target}")
async def clear_reload_signal(target: str) -> dict:
    service = _get_service()
    cleared = await service.clear_reload_signal(target)
    return {"status": "cleared" if cleared else "no_signal", "target": target}


# ── 清单管理 ─────────────────────────────────────────

@router.get("/manifest/{target}")
async def get_manifest(target: str) -> dict:
    service = _get_service()
    manifest = await service.get_model_manifest(target)
    if manifest is None:
        raise HTTPException(status_code=404, detail=f"No manifest for target: {target}")
    return manifest


@router.put("/manifest/{target}")
async def update_manifest(
    target: str,
    active_model: str = Query(...),
    active_version: str = Query(...),
    shadow_model: str | None = Query(default=None),
    shadow_version: str | None = Query(default=None),
) -> dict:
    service = _get_service()
    manifest = await service.update_model_manifest(
        target=target,
        active_model=active_model,
        active_version=active_version,
        shadow_model=shadow_model,
        shadow_version=shadow_version,
    )
    return manifest


# ── A/B 操作 ─────────────────────────────────────────

@router.post("/promote/{target}")
async def promote_shadow(target: str) -> dict:
    service = _get_service()
    manifest = await service.promote_shadow(target)
    return {"status": "promoted", "target": target, "manifest": manifest}


@router.post("/rollback/{target}")
async def rollback_model(target: str) -> dict:
    service = _get_service()
    manifest = await service.rollback_active(target)
    if manifest is None:
        raise HTTPException(
            status_code=400,
            detail=f"No rollback target available for: {target}",
        )
    return {"status": "rolled_back", "target": target, "manifest": manifest}


# ── 状态 ────────────────────────────────────────────

@router.get("/targets")
async def list_targets() -> dict:
    service = _get_service()
    targets = await service.list_targets()
    return {"total": len(targets), "targets": targets}
