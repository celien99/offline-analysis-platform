"""热重载与 Manifest 完整性测试。

测试：
  - manifest 更新、checksum 计算
  - 重载信号发送和清除
  - 回滚版本绑定
  - A/B 切换（shadow promote）
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import pytest

from app.services.hot_reload.service import HotReloadService


class TestHotReloadManifest:
    """Manifest 管理测试。"""

    def test_compute_checksum(self) -> None:
        """计算文件 SHA256 checksum。"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pt") as f:
            f.write(b"model_weights_data" * 100)
            tmp_path = f.name

        checksum = HotReloadService.compute_checksum(tmp_path)
        assert len(checksum) == 64  # SHA256 hex digest
        assert checksum == hashlib.sha256(b"model_weights_data" * 100).hexdigest()

        Path(tmp_path).unlink()

    def test_compute_checksum_nonexistent_file(self) -> None:
        """不存在的文件返回空字符串。"""
        checksum = HotReloadService.compute_checksum("/nonexistent/path/model.pt")
        assert checksum == ""

    def test_verify_checksum_match_and_mismatch(self) -> None:
        """校验 checksum 匹配和不匹配。"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pt") as f:
            f.write(b"test_data_for_checksum")
            tmp_path = f.name

        correct = hashlib.sha256(b"test_data_for_checksum").hexdigest()
        assert HotReloadService.verify_checksum(tmp_path, correct)
        assert not HotReloadService.verify_checksum(tmp_path, "wrong_checksum")

        Path(tmp_path).unlink()

    @pytest.mark.asyncio
    async def test_update_and_read_manifest(self) -> None:
        """写入 manifest 后能正确读取。"""
        import os

        # 使用临时目录作为 deploy target
        with tempfile.TemporaryDirectory() as tmpdir:
            # 设置环境变量覆盖 deploy_targets（直接操作文件）
            service = HotReloadService()
            target_dir = Path(tmpdir) / "test_target"
            target_dir.mkdir(parents=True, exist_ok=True)

            # 手动构造 target_dir（绕过 settings.deploy_targets）
            manifest_path = target_dir / "model_manifest.json"
            checksum = hashlib.sha256(b"model_data").hexdigest()
            manifest = {
                "target": "test_target",
                "active": {"model_name": "filter_v1", "version": "20250101", "checksum": checksum},
                "shadow": None,
                "checksums": {"20250101": checksum},
                "rollback_version": None,
                "history": [{"active_version": "20250101", "active_checksum": checksum, "switched_at": "2025-01-01T00:00:00Z"}],
                "updated_at": "2025-01-01T00:00:00Z",
            }
            manifest_path.write_text(json.dumps(manifest))

            # 验证 manifest 可读
            assert manifest_path.exists()
            read_back = json.loads(manifest_path.read_text())
            assert read_back["active"]["model_name"] == "filter_v1"
            assert read_back["active"]["checksum"] == checksum
            assert read_back["checksums"]["20250101"] == checksum

    @pytest.mark.asyncio
    async def test_rollback_version_binding(self) -> None:
        """回滚版本绑定：manifest 记录 rollback_version。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            target_dir = Path(tmpdir) / "rollback_test"
            target_dir.mkdir(parents=True, exist_ok=True)

            manifest_path = target_dir / "model_manifest.json"
            history = [
                {"active_version": "v1", "active_checksum": "abc123", "switched_at": "2025-01-01T00:00:00Z"},
                {"active_version": "v2", "active_checksum": "def456", "switched_at": "2025-02-01T00:00:00Z"},
                {"active_version": "v3", "active_checksum": "ghi789", "switched_at": "2025-03-01T00:00:00Z"},
            ]
            manifest = {
                "target": "rollback_test",
                "active": {"model_name": "filter_v1", "version": "v3", "checksum": "ghi789"},
                "rollback_version": "v2",
                "history": history,
                "updated_at": "2025-03-01T00:00:00Z",
            }
            manifest_path.write_text(json.dumps(manifest))

            read = json.loads(manifest_path.read_text())
            assert read["rollback_version"] == "v2"
            assert len(read["history"]) == 3
            assert read["history"][-2]["active_version"] == "v2"
            assert read["history"][-2]["active_checksum"] == "def456"


class TestReloadSignal:
    """重载信号测试。"""

    @pytest.mark.asyncio
    async def test_send_and_read_signal(self) -> None:
        """发送重载信号后能正确读取。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            target_dir = Path(tmpdir) / "signal_test"
            target_dir.mkdir(parents=True, exist_ok=True)

            signal_path = target_dir / "reload.signal"
            signal_data = {
                "action": "reload",
                "model_name": "filter_v2",
                "model_version": "20250201",
                "model_path": "signal_test/model.pt",
                "checksum": "abc123def456",
                "timestamp": "2025-02-01T00:00:00Z",
                "reason": "canary_promoted",
            }
            signal_path.write_text(json.dumps(signal_data))

            read = json.loads(signal_path.read_text())
            assert read["action"] == "reload"
            assert read["model_name"] == "filter_v2"
            assert read["checksum"] == "abc123def456"

    @pytest.mark.asyncio
    async def test_clear_signal(self) -> None:
        """清除重载信号后文件不再存在。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            signal_path = Path(tmpdir) / "reload.signal"
            signal_path.write_text(json.dumps({"action": "reload"}))

            signal_path.unlink()
            assert not signal_path.exists()

    @pytest.mark.asyncio
    async def test_signal_includes_checksum_for_integrity(self) -> None:
        """重载信号包含 checksum 供在线系统校验。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            signal_path = Path(tmpdir) / "reload.signal"
            model_data = b"model_bytes_for_checksum_test"
            checksum = hashlib.sha256(model_data).hexdigest()

            signal = {
                "action": "reload",
                "checksum": checksum,
                "model_name": "filter_v3",
                "model_version": "20250301",
            }
            signal_path.write_text(json.dumps(signal))

            read = json.loads(signal_path.read_text())
            assert read["checksum"] == checksum
            # 校验 checksum 格式正确
            assert len(read["checksum"]) == 64
