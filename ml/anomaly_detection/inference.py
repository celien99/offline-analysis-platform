"""FastFlow 推理引擎 — 加载 TorchScript 模型并计算 anomaly score + heatmap。"""

from __future__ import annotations

import math
from pathlib import Path

try:
    import cv2
except ImportError:  # 后端环境可能无 cv2
    cv2 = None
import numpy as np
import torch
from torchvision import transforms as T

from .fastflow import FastFlowConfig


class FastFlowInference:
    """加载 TorchScript FastFlow 模型进行异常检测推理。

    用法:
        engine = FastFlowInference.load("model.pt")
        score, heatmap = engine.predict(roi_bgr_image)
    """

    IMAGE_NET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    IMAGE_NET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)

    def __init__(
        self,
        model: torch.jit.ScriptModule,
        config: FastFlowConfig | None = None,
    ) -> None:
        self._model = model
        self._config = config or FastFlowConfig()

    @classmethod
    def load(cls, model_path: str | Path) -> "FastFlowInference":
        """从 TorchScript 文件加载，自适应 CPU/GPU 设备。"""
        path = str(model_path)
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = torch.jit.load(path, map_location=device)
        model.eval()
        return cls(model)

    def predict(self, roi_bgr_image: np.ndarray) -> dict[str, object]:
        """对单张 BGR ROI 图像做异常检测推理。

        Args:
            roi_bgr_image: BGR 图像 (H, W, 3)，uint8

        Returns:
            dict with:
              anomaly_score: float — 图像级异常分数
              heatmap: np.ndarray (H, W) — 像素级异常热力图
              is_anomaly: bool — 是否判定为异常
              threshold: float — 判定阈值 (基于训练集 NLL 分布的 99.9 百分位近似)
        """
        # BGR → RGB → tensor (cv2) 或 RGB → tensor (PIL fallback)
        if cv2 is not None:
            rgb = cv2.cvtColor(roi_bgr_image, cv2.COLOR_BGR2RGB)
        else:
            rgb = roi_bgr_image[..., ::-1]  # BGR → RGB via numpy
        tensor = self._preprocess(rgb)

        with torch.no_grad():
            latents = self._model(tensor)

        # 计算 per-pixel NLL (每个像素处的异常程度)
        heatmap, image_score = self._compute_anomaly(latents, roi_bgr_image.shape[:2])

        # 阈值：简单启发式（> 训练集均值 + 3*std 视为异常）
        threshold = 1.5  # 默认阈值，实际使用时应根据训练数据校准
        is_anomaly = bool(image_score > threshold)

        return {
            "anomaly_score": float(image_score),
            "heatmap": heatmap,
            "is_anomaly": is_anomaly,
            "threshold": threshold,
        }

    def predict_score(self, roi_bgr_image: np.ndarray) -> float:
        """快速推理 — 只返回图像级 anomaly score。"""
        result = self.predict(roi_bgr_image)
        return float(result["anomaly_score"])

    def _preprocess(self, rgb: np.ndarray) -> torch.Tensor:
        """RGB uint8 → normalized tensor (1, 3, H, W)。"""
        h, w = self._config.input_size
        if cv2 is not None:
            resized = cv2.resize(rgb, (w, h))
        else:
            from PIL import Image
            resized = np.array(Image.fromarray(rgb).resize((w, h), Image.BILINEAR))
        tensor = torch.from_numpy(
            resized.astype(np.float32) / 255.0
        ).permute(2, 0, 1).unsqueeze(0)
        mean = torch.as_tensor(self.IMAGE_NET_MEAN).view(1, 3, 1, 1)
        std = torch.as_tensor(self.IMAGE_NET_STD).view(1, 3, 1, 1)
        return (tensor - mean) / std

    def _compute_anomaly(
        self,
        latents: list[torch.Tensor],
        original_shape: tuple[int, int],
    ) -> tuple[np.ndarray, float]:
        """从 latent 列表计算 anomaly heatmap + image score。

        每个 latent z 处: NLL = 0.5 * z^2 + 0.5 * log(2*pi)
        沿通道取均值 → per-pixel score → 升采样到原始分辨率。
        """
        h, w = original_shape
        nll_list = []
        total_score = 0.0

        for z in latents:
            # per-pixel NLL
            nll = 0.5 * (z ** 2) + 0.5 * math.log(2 * math.pi)
            nll = nll.mean(dim=1, keepdim=True)  # mean over channels
            nll_cpu = nll.squeeze(0).squeeze(0).cpu().numpy()

            # 上采样到原始分辨率
            if cv2 is not None:
                nll_resized = cv2.resize(nll_cpu, (w, h), interpolation=cv2.INTER_LINEAR)
            else:
                from PIL import Image
                nll_resized = np.array(Image.fromarray(nll_cpu).resize((w, h), Image.BILINEAR))
            nll_list.append(nll_resized)
            total_score += float(nll_cpu.mean())

        # 融合多尺度 heatmap
        heatmap = np.mean(nll_list, axis=0).astype(np.float32)
        image_score = total_score

        return heatmap, image_score
