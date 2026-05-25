"""Online Hot Reload 服务 — 模型热切换和在线系统通知

支持：
1. 模型部署后发送重载信号
2. A/B 模型版本管理和切换
3. 热重载历史追踪
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.common.logging import get_logger
from app.core.config import settings

logger = get_logger(__name__)

RELOAD_SIGNAL_FILE = "reload.signal"
MODEL_MANIFEST_FILE = "model_manifest.json"


class HotReloadService:
    """管理在线系统的模型热重载"""

    def __init__(self) -> None:
        self._deploy_targets: dict[str, str] = dict(settings.deploy_targets)

    def _target_dir(self, target: str) -> Path:
        """根据 target 名称解析实际部署目录路径"""
        target_path = self._deploy_targets.get(target)
        if target_path is None:
            # 兼容：如果 target 不在配置中，当作相对路径
            target_path = f"./deployed_models/{target}"
        return Path(target_path)

    # ── 重载信号 ──────────────────────────────────────

    async def send_reload_signal(
        self,
        target: str,
        *,
        model_name: str,
        model_version: str,
        model_path: str,
        reload_reason: str = "deploy",
    ) -> dict[str, Any]:
        """向指定 target 的在线系统发送模型重载信号"""
        target_dir = self._target_dir(target)
        target_dir.mkdir(parents=True, exist_ok=True)

        signal_path = target_dir / RELOAD_SIGNAL_FILE
        signal_data = {
            "action": "reload",
            "model_name": model_name,
            "model_version": model_version,
            "model_path": model_path,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "reason": reload_reason,
        }
        signal_path.write_text(json.dumps(signal_data, indent=2))
        logger.info(
            "reload_signal_sent",
            target=target,
            model_name=model_name,
            model_version=model_version,
        )
        return signal_data

    async def get_reload_signal(self, target: str) -> dict[str, Any] | None:
        """读取指定 target 的当前重载信号"""
        signal_path = self._target_dir(target) / RELOAD_SIGNAL_FILE
        if not signal_path.exists():
            return None
        try:
            return json.loads(signal_path.read_text())
        except (json.JSONDecodeError, OSError):
            return None

    async def clear_reload_signal(self, target: str) -> bool:
        """清除重载信号（指示在线系统已响应）"""
        signal_path = self._target_dir(target) / RELOAD_SIGNAL_FILE
        if signal_path.exists():
            signal_path.unlink()
            return True
        return False

    # ── 模型清单管理 ──────────────────────────────────

    async def update_model_manifest(
        self,
        target: str,
        *,
        active_model: str,
        active_version: str,
        shadow_model: str | None = None,
        shadow_version: str | None = None,
    ) -> dict[str, Any]:
        """更新部署目标的模型清单"""
        target_dir = self._target_dir(target)
        target_dir.mkdir(parents=True, exist_ok=True)

        manifest_path = target_dir / MODEL_MANIFEST_FILE
        existing: dict[str, Any] = {}
        if manifest_path.exists():
            try:
                existing = json.loads(manifest_path.read_text())
            except json.JSONDecodeError:
                pass

        manifest = {
            "target": target,
            "active": {
                "model_name": active_model,
                "version": active_version,
            },
            "shadow": {
                "model_name": shadow_model,
                "version": shadow_version,
            } if shadow_model else None,
            "history": existing.get("history", [])[-9:] + [{
                "active_version": active_version,
                "switched_at": datetime.now(tz=timezone.utc).isoformat(),
            }],
            "updated_at": datetime.now(tz=timezone.utc).isoformat(),
        }
        manifest_path.write_text(json.dumps(manifest, indent=2))
        logger.info("manifest_updated", target=target, active_version=active_version)
        return manifest

    async def get_model_manifest(self, target: str) -> dict[str, Any] | None:
        """获取部署目标的当前模型清单"""
        manifest_path = self._target_dir(target) / MODEL_MANIFEST_FILE
        if not manifest_path.exists():
            return None
        try:
            return json.loads(manifest_path.read_text())
        except (json.JSONDecodeError, OSError):
            return None

    # ── A/B 切换 ─────────────────────────────────────

    async def promote_shadow(self, target: str) -> dict[str, Any]:
        """将 canary/shadow 模型提升为 active"""
        manifest = await self.get_model_manifest(target)
        if manifest is None or manifest.get("shadow") is None:
            from app.core.exceptions import ValidationError
            raise ValidationError("No shadow model to promote")

        shadow = manifest["shadow"]
        old_active = manifest["active"]

        new_manifest = await self.update_model_manifest(
            target=target,
            active_model=shadow["model_name"],
            active_version=shadow["version"],
            shadow_model=None,
            shadow_version=None,
        )

        await self.send_reload_signal(
            target=target,
            model_name=shadow["model_name"],
            model_version=shadow["version"],
            model_path=f"{target}/model.pt",
            reload_reason="shadow_promoted",
        )

        logger.info(
            "shadow_promoted",
            target=target,
            old_version=old_active["version"],
            new_version=shadow["version"],
        )
        return new_manifest

    async def rollback_active(self, target: str) -> dict[str, Any] | None:
        """回滚到上一个版本"""
        manifest = await self.get_model_manifest(target)
        if manifest is None or len(manifest.get("history", [])) < 2:
            return None

        # 取倒数第二个版本作为回滚目标
        prev_version = manifest["history"][-2]["active_version"]
        current = manifest["active"]

        new_manifest = await self.update_model_manifest(
            target=target,
            active_model=current["model_name"],
            active_version=prev_version,
        )

        await self.send_reload_signal(
            target=target,
            model_name=current["model_name"],
            model_version=prev_version,
            model_path=f"{target}/model.pt",
            reload_reason="rollback",
        )

        logger.info(
            "model_rolled_back",
            target=target,
            from_version=current["version"],
            to_version=prev_version,
        )
        return new_manifest

    # ── 状态查询 ─────────────────────────────────────

    async def list_targets(self) -> list[dict[str, Any]]:
        """列出所有部署目标及其状态"""
        targets: list[dict[str, Any]] = []
        for target_name, target_path_str in self._deploy_targets.items():
            target_dir = Path(target_path_str)
            manifest = await self.get_model_manifest(target_name)
            signal = await self.get_reload_signal(target_name)
            model_exists = target_dir.exists() and (target_dir / "model.pt").exists()

            targets.append({
                "target": target_name,
                "active_model": manifest["active"]["model_name"] if manifest else None,
                "active_version": manifest["active"]["version"] if manifest else None,
                "has_shadow": bool(manifest and manifest.get("shadow")),
                "has_pending_reload": signal is not None,
                "model_deployed": model_exists,
            })

        return targets
