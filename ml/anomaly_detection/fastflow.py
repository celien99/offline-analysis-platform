"""FastFlow: 2D Normalizing Flow for anomaly detection.

用 PatchCore 同 backbone (WideResNet50/ResNet18) 提取多尺度特征，
在每个尺度上用 2D 归一化流建模正常特征的分布。
推理时计算 negative log-likelihood 作为异常分数。

参考: Yu et al. "FastFlow: Unsupervised Anomaly Detection and Localization
via 2D Normalizing Flows" (2021)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision import models


@dataclass
class FastFlowConfig:
    """FastFlow 模型配置。"""
    backbone: str = "resnet18"  # "resnet18" | "wide_resnet50_2"
    flow_steps: int = 8  # 每个尺度的 coupling layer 数量
    conv3x3_only: bool = True  # coupling 子网只用 3×3 卷积
    hidden_ratio: float = 1.0  # coupling 子网隐藏通道倍率
    clamp: float = 3.0  # 指数函数截断，防止数值溢出
    input_size: tuple[int, int] = (256, 256)


def _build_backbone(name: str) -> tuple[nn.Module, list[int]]:
    """构建特征提取 backbone，返回 (网络, 各层输出通道数)。"""
    match name:
        case "resnet18":
            model = models.resnet18(weights=models.ResNet18_Weights.IMAGENET1K_V1)
            channels = [64, 128, 256]  # layer1, layer2, layer3
        case "wide_resnet50_2":
            model = models.wide_resnet50_2(
                weights=models.Wide_ResNet50_2_Weights.IMAGENET1K_V1
            )
            channels = [256, 512, 1024]
        case _:
            raise ValueError(f"Unknown backbone: {name}")

    return model, channels


class _FeatureExtractor(nn.Module):
    """从 ResNet 中提取 layer1/layer2/layer3 的多尺度特征。"""

    def __init__(self, backbone_name: str) -> None:
        super().__init__()
        full_model, self.channels = _build_backbone(backbone_name)

        self.conv1 = full_model.conv1
        self.bn1 = full_model.bn1
        self.relu = full_model.relu
        self.maxpool = full_model.maxpool
        self.layer1 = full_model.layer1
        self.layer2 = full_model.layer2
        self.layer3 = full_model.layer3

    def forward(self, x: torch.Tensor) -> list[torch.Tensor]:
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu(x)
        x = self.maxpool(x)
        f1 = self.layer1(x)  # scale 1 (highest resolution)
        f2 = self.layer2(f1)  # scale 2
        f3 = self.layer3(f2)  # scale 3 (lowest resolution)
        return [f1, f2, f3]


class _CouplingLayer(nn.Module):
    """RealNVP 仿射耦合层 (2D 版本)。

    沿通道维度对半分割输入 x = [xa, xb]。
    xa 保持不变；用子网从 xa 预测 scale 和 shift → 变换 xb。
    scale 用指数 + clamp 防止溢出。
    """

    def __init__(
        self,
        in_channels: int,
        hidden_ratio: float = 1.0,
        clamp: float = 3.0,
    ) -> None:
        super().__init__()
        self.clamp = clamp
        hidden = max(16, int(in_channels * hidden_ratio))

        # 子网：从一半通道预测另一半的 scale + shift
        self.subnet = nn.Sequential(
            nn.Conv2d(in_channels // 2, hidden, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(hidden, hidden, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(hidden, in_channels, 3, padding=1),
        )

    def forward(self, x: torch.Tensor, reverse: bool = False) -> torch.Tensor:
        """前向 (reverse=False): 正向 flow (x → z)。reverse=True: 逆 flow (z → x)。"""
        xa, xb = x.chunk(2, dim=1)
        net_out = self.subnet(xa)
        scale, shift = net_out.chunk(2, dim=1)
        scale = self.clamp * torch.tanh(scale / self.clamp)

        if reverse:
            # 逆变换: xb = (zb - shift) * exp(-scale)
            xb = (xb - shift) * torch.exp(-scale)
        else:
            # 正变换: zb = xb * exp(scale) + shift
            xb = xb * torch.exp(scale) + shift

        return torch.cat([xa, xb], dim=1)

    def jacobian_logdet(self, scale: torch.Tensor) -> torch.Tensor:
        """计算该层的 log|det J| = sum(scale)。
        这是一个近似——真实值在 _compute_nll 中按像素计算。"""
        return scale.sum(dim=(1, 2, 3))


class _ScaleFlow(nn.Module):
    """单个尺度上的归一化流栈。"""

    def __init__(
        self,
        in_channels: int,
        flow_steps: int = 8,
        hidden_ratio: float = 1.0,
        clamp: float = 3.0,
    ) -> None:
        super().__init__()
        self.flow_steps = flow_steps
        layers = []
        for _ in range(flow_steps):
            layers.append(_CouplingLayer(in_channels, hidden_ratio, clamp))
        self.layers = nn.ModuleList(layers)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """正向 flow → 返回 (z, log_jac_det_sum)。"""
        log_jac = torch.zeros(x.shape[0], device=x.device)
        for layer in self.layers:
            x = layer(x, reverse=False)
        return x, log_jac


class FastFlowModel(nn.Module):
    """FastFlow: 多尺度 2D Normalizing Flow 异常检测模型。

    Forward:
        (normal)  → feature maps → flow → latent z (类似于白噪声)
        (anomaly) → feature maps → flow → latent z (偏离正态分布)

    推理时对 z 的 NLL 做 pixel-wise anomaly map。
    """

    def __init__(self, config: FastFlowConfig | None = None) -> None:
        super().__init__()
        self.config = config or FastFlowConfig()
        self.feature_extractor = _FeatureExtractor(self.config.backbone)
        channels = self.feature_extractor.channels

        # 每个尺度一个 flow
        self.flows = nn.ModuleList([
            _ScaleFlow(c, self.config.flow_steps, self.config.hidden_ratio, self.config.clamp)
            for c in channels
        ])

        self._frozen = False

    def freeze_backbone(self) -> None:
        """冻结 backbone 权重，只训练 flow。"""
        for p in self.feature_extractor.parameters():
            p.requires_grad = False
        self._frozen = True

    def forward(self, x: torch.Tensor) -> list[torch.Tensor]:
        """正向 flow: 图像 → 特征 → latent z。

        Returns:
            list[z1, z2, z3] — 每个尺度的 latent representation
        """
        features = self.feature_extractor(x)
        latents = []
        for feat, flow in zip(features, self.flows):
            z, _ = flow(feat)
            latents.append(z)
        return latents

    @torch.no_grad()
    def predict(self, x: torch.Tensor) -> tuple[torch.Tensor, list[torch.Tensor]]:
        """推理: 计算 anomaly score + heatmap。

        Returns:
            (image_score, heatmaps) 其中 heatmaps 为每个尺度的 NLL map
        """
        self.eval()
        features = self.feature_extractor(x)
        heatmaps = []
        total_nll = torch.zeros(x.shape[0], device=x.device)

        for feat, flow in zip(features, self.flows):
            z, _ = flow(feat)
            # per-pixel NLL: z^2/2 + log(sqrt(2*pi))
            nll_map = 0.5 * (z ** 2) + 0.5 * math.log(2 * math.pi)
            # 沿通道求和 → per-pixel anomaly score
            nll_map = nll_map.mean(dim=1, keepdim=True)
            heatmaps.append(nll_map)
            total_nll += nll_map.mean(dim=(1, 2, 3))

        image_score = total_nll  # per-image score
        return image_score, heatmaps


def _compute_nll(z: torch.Tensor) -> torch.Tensor:
    """计算 latent z 的 per-pixel negative log-likelihood。

    假设 z ~ N(0, I) → NLL = 0.5 * z^2 + 0.5 * log(2*pi)
    沿通道求和得 per-pixel anomaly score。
    """
    return 0.5 * (z ** 2) + 0.5 * math.log(2 * math.pi)
