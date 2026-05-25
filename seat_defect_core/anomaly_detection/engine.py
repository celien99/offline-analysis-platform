"""FastFlow 在线推理引擎 — 加载 TorchScript 模型，输出 anomaly score + heatmap。

遵循 FilterClassifierService 的 load/predict 模式。
"""

from __future__ import annotations

import math
from pathlib import Path
from time import perf_counter
from typing import Optional, Union

import cv2
import numpy as np

from ..config import FastFlowConfig
from ..core_types import FastFlowResult

_IMAGE_NET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_IMAGE_NET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


class FastFlowService:
    """加载 FastFlow TorchScript 模型，对 ROI 图像做端到端异常检测。

    PatchCore 作为 teacher 训练得到的 student 模型，
    单次前向传播代替 KNN 检索，延迟约 5-10ms。
    """

    def __init__(
        self,
        config: FastFlowConfig,
        model: Optional["torch.jit.ScriptModule"] = None,
    ) -> None:
        self.config = config
        self._model = model

    @classmethod
    def load(cls, model_path: Union[str, Path]) -> "FastFlowService":
        """从 TorchScript 文件加载 FastFlow 模型。"""
        import torch

        path = str(model_path)
        model = torch.jit.load(path)
        model.eval()
        return cls(
            config=FastFlowConfig(enabled=True, model_path=path),
            model=model,
        )

    def predict(self, roi_bgr_image: np.ndarray) -> FastFlowResult:
        """对单张 ROI BGR 图像做异常检测推理。

        Returns:
            FastFlowResult with anomaly_score, heatmap, is_anomaly
        """
        import torch

        started_at = perf_counter()
        diagnostics: dict[str, float] = {}

        try:
            if self._model is None:
                return FastFlowResult(
                    anomaly_score=0.0,
                    heatmap=np.zeros(roi_bgr_image.shape[:2], dtype=np.float32),
                    is_anomaly=False,
                    threshold=self.config.threshold or 1.5,
                    diagnostics={"error_model_not_loaded": 1.0},
                )

            # 预处理：BGR → RGB → resize → normalize
            pre_start = perf_counter()
            rgb = cv2.cvtColor(roi_bgr_image, cv2.COLOR_BGR2RGB)
            resized = cv2.resize(rgb, (256, 256), interpolation=cv2.INTER_LINEAR)
            tensor = torch.from_numpy(
                resized.astype(np.float32) / 255.0
            ).permute(2, 0, 1).unsqueeze(0)

            mean = torch.as_tensor(_IMAGE_NET_MEAN).view(1, 3, 1, 1)
            std = torch.as_tensor(_IMAGE_NET_STD).view(1, 3, 1, 1)
            tensor = (tensor - mean) / std
            diagnostics["preprocess_ms"] = (perf_counter() - pre_start) * 1000.0

            # 推理 — 将输入移到模型所在设备
            infer_start = perf_counter()
            device = next(self._model.parameters()).device
            tensor = tensor.to(device)
            with torch.no_grad():
                latents: list[torch.Tensor] = self._model(tensor)
            diagnostics["inference_ms"] = (perf_counter() - infer_start) * 1000.0

            # 计算 anomaly score + heatmap
            anomaly_score, heatmap = self._compute_score(latents, roi_bgr_image.shape[:2])
            threshold = self.config.threshold or 1.5
            is_anomaly = bool(anomaly_score > threshold)

            diagnostics["total_ms"] = (perf_counter() - started_at) * 1000.0

            return FastFlowResult(
                anomaly_score=float(anomaly_score),
                heatmap=heatmap,
                is_anomaly=is_anomaly,
                threshold=threshold,
                diagnostics=diagnostics,
            )

        except Exception:
            # 故障安全：推理失败时不抑制 PatchCore
            diagnostics["total_ms"] = (perf_counter() - started_at) * 1000.0
            diagnostics["error_prediction_failed"] = 1.0
            return FastFlowResult(
                anomaly_score=float("inf"),
                heatmap=np.zeros(roi_bgr_image.shape[:2], dtype=np.float32),
                is_anomaly=True,  # 故障安全：假设有异常
                threshold=self.config.threshold or 1.5,
                diagnostics=diagnostics,
            )

    @staticmethod
    def _compute_score(
        latents: list["torch.Tensor"],
        original_shape: tuple[int, int],
    ) -> tuple[float, np.ndarray]:
        """从 multi-scale latent 计算 anomaly score + heatmap。"""
        h, w = original_shape
        nll_list = []
        total_score = 0.0

        for z in latents:
            z_np = z.squeeze(0).cpu().numpy()
            # per-pixel NLL: 0.5 * z^2 + 0.5 * log(2*pi)
            nll = 0.5 * (z_np ** 2) + 0.5 * math.log(2 * math.pi)
            # 通道取均值
            nll_mean = nll.mean(axis=0)
            nll_resized = cv2.resize(nll_mean, (w, h), interpolation=cv2.INTER_LINEAR)
            nll_list.append(nll_resized)
            total_score += float(nll_mean.mean())

        heatmap = np.mean(nll_list, axis=0).astype(np.float32)
        return total_score, heatmap
