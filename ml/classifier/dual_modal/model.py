from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision import models


class EfficientADFeatureProjector(nn.Module):
    """将 EfficientAD teacher/student/difference 特征图投影到固定维度。

    接收 _extract_features() 产出的 (teacher, student, difference) 三组特征图，
    通过 1×1 conv + global avg pool 投影到统一维度后 concat。
    """

    def __init__(
        self,
        teacher_channels: int = 384,
        student_channels: int = 768,
        diff_channels: int = 384,
        proj_dim: int = 128,
    ):
        super().__init__()
        self.teacher_proj = nn.Conv2d(teacher_channels, proj_dim, 1)
        self.student_proj = nn.Conv2d(student_channels, proj_dim, 1)
        self.diff_proj = nn.Conv2d(diff_channels, proj_dim, 1)
        self.output_dim = proj_dim * 3  # 384

    def forward(
        self,
        teacher: torch.Tensor,
        student: torch.Tensor,
        difference: torch.Tensor,
    ) -> torch.Tensor:
        ft = F.adaptive_avg_pool2d(self.teacher_proj(teacher), 1).flatten(1)
        fs = F.adaptive_avg_pool2d(self.student_proj(student), 1).flatten(1)
        fd = F.adaptive_avg_pool2d(self.diff_proj(difference), 1).flatten(1)
        return torch.cat([ft, fs, fd], dim=1)


class DualModalFilter(nn.Module):
    """Dual-modal filter: image patch + EfficientAD features -> binary classifier."""

    def __init__(
        self,
        num_classes: int = 2,
        image_size: int = 448,
        feature_dropout_rate: float = 0.0,
    ):
        super().__init__()
        # Image branch: MobileNetV3-Small (pretrained), remove classifier head
        backbone = models.mobilenet_v3_small(
            weights=models.MobileNet_V3_Small_Weights.IMAGENET1K_V1
        )
        self.image_backbone = nn.Sequential(*list(backbone.children())[:-1])
        # MobileNetV3-Small last channel is 576
        self.image_proj = nn.Sequential(
            nn.Linear(576, 256),
            nn.ReLU(inplace=True),
        )

        # EfficientAD feature branch (output_dim=384 for 3×128 proj)
        self.ead_projector = EfficientADFeatureProjector()
        self.ead_proj = nn.Sequential(
            nn.Linear(384, 256),
            nn.ReLU(inplace=True),
        )

        # Unified embedding projection (384d → 256d, from EmbeddingSpaceContract)
        self.uni_proj = nn.Sequential(
            nn.Linear(384, 256),
            nn.ReLU(inplace=True),
        )

        # Fusion head
        self.fusion = nn.Sequential(
            nn.Linear(768, 128),
            nn.ReLU(inplace=True),
            nn.Dropout(0.3),
            nn.Linear(128, 64),
            nn.ReLU(inplace=True),
            nn.Linear(64, num_classes),
        )

        self.feature_dropout_rate = feature_dropout_rate
        self.image_size = image_size

    def forward(
        self,
        patch_image: torch.Tensor,
        ead_features: dict[str, torch.Tensor] | None = None,
        unified_emb: torch.Tensor | None = None,
    ) -> torch.Tensor:
        # Image branch
        img_feat = self.image_backbone(patch_image)
        img_feat = img_feat.flatten(1)
        f_img = self.image_proj(img_feat)

        # EfficientAD feature branch (with optional dropout for fallback training)
        if ead_features is not None and self.training and self.feature_dropout_rate > 0:
            if torch.rand(1).item() < self.feature_dropout_rate:
                ead_features = None

        if ead_features is not None:
            ead_feat = self.ead_projector(
                ead_features["teacher"],
                ead_features["student"],
                ead_features["difference"],
            )
            f_ead = self.ead_proj(ead_feat)
        else:
            f_ead = torch.zeros_like(f_img)

        # Unified embedding (DINOv2-aligned, from EmbeddingSpaceContract)
        if unified_emb is not None:
            f_uni = self.uni_proj(unified_emb)
        else:
            f_uni = torch.zeros(f_img.size(0), 256, device=f_img.device)

        # Late fusion (three modalities: image + EAD + unified_emb)
        fused = torch.cat([f_img, f_ead, f_uni], dim=1)
        return self.fusion(fused)

    def to_torchscript(self, output_path: str) -> None:
        """Export to TorchScript for online inference."""
        self.eval()
        example_img = torch.randn(1, 3, self.image_size, self.image_size)
        example_features = {
            "teacher": torch.randn(1, 384, 64, 64),
            "student": torch.randn(1, 768, 64, 64),
            "difference": torch.randn(1, 384, 64, 64),
        }
        traced = torch.jit.trace(self, (example_img, example_features))
        traced.save(output_path)
