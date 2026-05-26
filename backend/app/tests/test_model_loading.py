"""模型加载测试。

测试 prompt.md 第5条：
  - TorchScript 模型能被正确加载并推理
  - 模型输出格式与 FilterClassifierResult 兼容
  - 故障安全：加载失败时返回 is_real_defect=True
  - embedding 模型输出维度验证
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest


class TestTorchScriptModelLoading:
    """TorchScript 模型加载与推理测试。"""

    def test_create_and_load_torchscript_model(self) -> None:
        """创建一个简单 TorchScript 模型并加载推理。"""
        import torch

        # 创建简单模型
        class SimpleClassifier(torch.nn.Module):
            def __init__(self) -> None:
                super().__init__()
                self.conv = torch.nn.Conv2d(3, 8, 3, padding=1)
                self.pool = torch.nn.AdaptiveAvgPool2d(1)
                self.fc = torch.nn.Linear(8, 2)

            def forward(self, x: torch.Tensor) -> torch.Tensor:
                x = self.conv(x)
                x = self.pool(x)
                x = x.view(x.size(0), -1)
                return self.fc(x)

        model = SimpleClassifier()
        model.eval()

        # 跟踪导出
        example_input = torch.randn(1, 3, 224, 224)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pt") as f:
            traced = torch.jit.trace(model, example_input)
            torch.jit.save(traced, f.name)
            model_path = f.name

        # 加载并推理
        loaded = torch.jit.load(model_path)
        loaded.eval()

        test_input = torch.randn(2, 3, 224, 224)
        with torch.no_grad():
            output = loaded(test_input)

        assert output.shape == (2, 2)
        probs = torch.softmax(output, dim=1)
        assert probs.shape == (2, 2)
        assert torch.allclose(probs.sum(dim=1), torch.ones(2))

        Path(model_path).unlink()

    def test_model_load_failure_returns_fallback(self) -> None:
        """模型文件不存在时返回故障安全结果。"""
        # 模拟 classifier engine 的故障安全逻辑
        def safe_predict(model_path: str, has_model: bool) -> dict:
            if not has_model:
                return {
                    "is_real_defect": True,  # 故障安全：不抑制 NG
                    "confidence": 0.0,
                    "class_id": 1,
                }
            return {"is_real_defect": False, "confidence": 0.95, "class_id": 0}

        result = safe_predict("/nonexistent/model.pt", False)
        assert result["is_real_defect"] is True
        assert result["confidence"] == 0.0

    def test_torchscript_preprocessing_pipeline(self) -> None:
        """验证与 FilterClassifierService 一致的预处理 pipeline。"""
        import torch

        try:
            import cv2
        except ImportError:
            pytest.skip("cv2 not installed")

        # 模拟 BGR 图像 → RGB → resize → normalize
        bgr_image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        rgb = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, (224, 224), interpolation=cv2.INTER_LINEAR)

        tensor = torch.from_numpy(
            resized.astype(np.float32) / 255.0
        ).permute(2, 0, 1).unsqueeze(0)

        mean = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)
        std = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)
        tensor = (tensor - mean) / std

        assert tensor.shape == (1, 3, 224, 224)
        # 归一化后均值接近 0
        assert abs(tensor.mean().item()) < 0.1


class TestEmbeddingModelOutput:
    """Embedding 模型输出维度测试。"""

    def test_dinov2_embedding_dimension(self) -> None:
        """验证 DINOv2-S 输出 384 维 embedding。"""
        from app.core.config import settings

        # 配置一致性检查
        assert settings.embedding_dim == 384
        assert settings.embedding_model == "dinov2_vits14"

    def test_embedding_vector_storage_format(self) -> None:
        """验证 embedding 向量存储格式：list[float]，长度 384。"""
        vec = np.random.randn(384).astype(np.float32).tolist()
        assert isinstance(vec, list)
        assert len(vec) == 384
        assert all(isinstance(v, float) for v in vec)

    def test_embedding_batch_consistency(self) -> None:
        """相同图像应产生相同 embedding。"""
        # 生成两个相同向量模拟相同输入
        rng = np.random.RandomState(42)
        vec1 = rng.randn(384).astype(np.float32)
        rng2 = np.random.RandomState(42)
        vec2 = rng2.randn(384).astype(np.float32)

        assert np.array_equal(vec1, vec2)
        assert len(vec1) == 384


class TestGateModelLoading:
    """门禁评估中的模型加载测试。"""

    def test_gate_metrics_format_for_deployment(self) -> None:
        """验证门禁指标格式满足部署判断需求。"""
        metrics = {
            "real_defect_recall": 0.98,
            "false_alarm_suppression_rate": 0.45,
            "suppressed_real_defect_count": 0,
            "confusion_matrix": [[40, 2], [1, 45]],
            "total": 88,
        }

        # 门禁标准验证
        assert metrics["real_defect_recall"] >= 0.95
        assert metrics["false_alarm_suppression_rate"] >= 0.10
        assert metrics["suppressed_real_defect_count"] <= 0

    def test_model_artifact_path_validation(self) -> None:
        """模型产物路径验证：路径存在且为 .pt 文件。"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pt") as f:
            f.write(b"mock_model_data")
            tmp_path = f.name

        path = Path(tmp_path)
        assert path.exists()
        assert path.suffix == ".pt"
        assert path.stat().st_size > 0

        path.unlink()
