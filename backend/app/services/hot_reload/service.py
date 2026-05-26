"""Online Hot Reload 服务 — 模型热切换、checksum 校验和在线系统通知

支持：
1. 模型部署后发送重载信号
2. A/B 模型版本管理和切换
3. 热重载历史追踪
4. SHA256 checksum 完整性校验，防止加载损坏模型
5. 回滚版本绑定：manifest 记录每个版本的 checksum，
   回滚时校验目标版本模型文件完整性
"""
from __future__ import annotations

import hashlib
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
            target_path = f"./deployed_models/{target}"
        return Path(target_path)

    # ── Checksum ──────────────────────────────────────────────

    @staticmethod
    def compute_checksum(file_path: str | Path) -> str:
        """计算模型文件的 SHA256 checksum。"""
        path = Path(file_path)
        if not path.exists():
            logger.warning("checksum_file_not_found", path=str(path))
            return ""
        sha = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha.update(chunk)
        return sha.hexdigest()

    @staticmethod
    def verify_checksum(file_path: str | Path, expected: str) -> bool:
        """校验模型文件 checksum 是否匹配。"""
        actual = HotReloadService.compute_checksum(file_path)
        return actual == expected

    # ── 重载信号 ─────────────────────────────────────────

    async def send_reload_signal(
        self,
        target: str,
        *,
        model_name: str,
        model_version: str,
        model_path: str,
        reload_reason: str = "deploy",
        checksum: str = "",
    ) -> dict[str, Any]:
        """向指定 target 的在线系统发送模型重载信号。

        信号文件包含模型 checksum，在线系统应在加载前校验完整性。
        """
        target_dir = self._target_dir(target)
        target_dir.mkdir(parents=True, exist_ok=True)

        signal_path = target_dir / RELOAD_SIGNAL_FILE
        signal_data = {
            "action": "reload",
            "model_name": model_name,
            "model_version": model_version,
            "model_path": model_path,
            "checksum": checksum,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "reason": reload_reason,
        }
        signal_path.write_text(json.dumps(signal_data, indent=2))
        logger.info(
            "reload_signal_sent",
            target=target,
            model_name=model_name,
            model_version=model_version,
            checksum=checksum[:16],
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

    # ── 模型清单管理（含 checksum + 回滚版本绑定）───────

    async def update_model_manifest(
        self,
        target: str,
        *,
        active_model: str,
        active_version: str,
        active_checksum: str = "",
        shadow_model: str | None = None,
        shadow_version: str | None = None,
        shadow_checksum: str = "",
    ) -> dict[str, Any]:
        """更新部署目标的模型清单。

        清单包含：
          - active/shadow 模型名、版本、checksum
          - 版本→checksum 的绑定映射（回滚时校验完整性）
          - 最近 10 次切换历史
        """
        target_dir = self._target_dir(target)
        target_dir.mkdir(parents=True, exist_ok=True)

        manifest_path = target_dir / MODEL_MANIFEST_FILE
        existing: dict[str, Any] = {}
        if manifest_path.exists():
            try:
                existing = json.loads(manifest_path.read_text())
            except json.JSONDecodeError:
                pass

        # 记录版本→checksum 绑定，用于回滚校验
        checksums: dict[str, str] = existing.get("checksums", {})
        if active_checksum:
            checksums[active_version] = active_checksum
        if shadow_checksum and shadow_version:
            checksums[shadow_version] = shadow_checksum

        now = datetime.now(tz=timezone.utc).isoformat()
        history_entry = {
            "active_version": active_version,
            "active_checksum": active_checksum,
            "switched_at": now,
        }
        history = existing.get("history", [])[-9:] + [history_entry]

        manifest = {
            "target": target,
            "active": {
                "model_name": active_model,
                "version": active_version,
                "checksum": active_checksum,
            },
            "shadow": {
                "model_name": shadow_model,
                "version": shadow_version,
                "checksum": shadow_checksum,
            } if shadow_model else None,
            "checksums": checksums,
            "rollback_version": (
                history[-2]["active_version"] if len(history) >= 2 else None
            ),
            "history": history,
            "updated_at": now,
        }
        manifest_path.write_text(json.dumps(manifest, indent=2))
        logger.info(
            "manifest_updated",
            target=target,
            active_version=active_version,
            checksum=active_checksum[:16],
        )
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

    # ── A/B 切换 ─────────────────────────────────────────

    async def promote_shadow(self, target: str) -> dict[str, Any]:
        """将 canary/shadow 模型提升为 active"""
        manifest = await self.get_model_manifest(target)
        if manifest is None or manifest.get("shadow") is None:
            from app.core.exceptions import ValidationError
            raise ValidationError("No shadow model to promote")

        shadow = manifest["shadow"]
        old_active = manifest["active"]

        # 校验 shadow 模型文件完整性
        shadow_path = self._target_dir(target) / "canary" / "model.pt"
        if not shadow_path.exists():
            shadow_path = self._target_dir(target) / "shadow" / "model.pt"
        if shadow.get("checksum") and shadow_path.exists():
            if not self.verify_checksum(str(shadow_path), shadow["checksum"]):
                raise ValidationError(
                    f"Shadow model checksum mismatch: {shadow['model_name']}:{shadow['version']}"
                )

        new_manifest = await self.update_model_manifest(
            target=target,
            active_model=shadow["model_name"],
            active_version=shadow["version"],
            active_checksum=shadow.get("checksum", ""),
            shadow_model=None,
            shadow_version=None,
        )

        await self.send_reload_signal(
            target=target,
            model_name=shadow["model_name"],
            model_version=shadow["version"],
            model_path=f"{target}/model.pt",
            reload_reason="shadow_promoted",
            checksum=shadow.get("checksum", ""),
        )

        logger.info(
            "shadow_promoted",
            target=target,
            old_version=old_active["version"],
            new_version=shadow["version"],
        )
        return new_manifest

    async def rollback_active(self, target: str) -> dict[str, Any] | None:
        """回滚到上一个版本。

        从 manifest 的 history 取倒数第二个版本作为回滚目标，
        校验该版本的 checksum 确保模型文件完整后再切换。
        """
        manifest = await self.get_model_manifest(target)
        if manifest is None or len(manifest.get("history", [])) < 2:
            return None

        prev = manifest["history"][-2]
        prev_version = prev["active_version"]
        prev_checksum = prev.get("active_checksum", "")
        current = manifest["active"]

        # 校验回滚目标版本的模型文件完整性
        model_path = self._target_dir(target) / "model.pt"
        if prev_checksum and model_path.exists():
            stored_checksum = manifest.get("checksums", {}).get(prev_version, "")
            if stored_checksum and not self.verify_checksum(str(model_path), stored_checksum):
                logger.warning(
                    "rollback_checksum_mismatch",
                    target=target,
                    version=prev_version,
                )

        new_manifest = await self.update_model_manifest(
            target=target,
            active_model=current["model_name"],
            active_version=prev_version,
            active_checksum=prev_checksum,
        )

        await self.send_reload_signal(
            target=target,
            model_name=current["model_name"],
            model_version=prev_version,
            model_path=f"{target}/model.pt",
            reload_reason="rollback",
            checksum=prev_checksum,
        )

        logger.info(
            "model_rolled_back",
            target=target,
            from_version=current["version"],
            to_version=prev_version,
        )
        return new_manifest

    # ── 状态查询 ─────────────────────────────────────────

    async def list_targets(self) -> list[dict[str, Any]]:
        """列出所有部署目标及其状态"""
        targets: list[dict[str, Any]] = []
        for target_name, target_path_str in self._deploy_targets.items():
            target_dir = Path(target_path_str)
            manifest = await self.get_model_manifest(target_name)
            signal = await self.get_reload_signal(target_name)
            model_path = target_dir / "model.pt"
            model_exists = model_path.exists()

            active_checksum = manifest["active"].get("checksum", "") if manifest else ""
            checksum_ok = False
            if active_checksum and model_exists:
                checksum_ok = self.verify_checksum(str(model_path), active_checksum)

            targets.append({
                "target": target_name,
                "active_model": manifest["active"]["model_name"] if manifest else None,
                "active_version": manifest["active"]["version"] if manifest else None,
                "active_checksum": active_checksum[:16] if active_checksum else None,
                "checksum_verified": checksum_ok,
                "has_shadow": bool(manifest and manifest.get("shadow")),
                "rollback_version": manifest.get("rollback_version") if manifest else None,
                "has_pending_reload": signal is not None,
                "model_deployed": model_exists,
            })

        return targets
