from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision import models


class EfficientADFeatureProjector(nn.Module):
    """Project multi-scale EfficientAD features to fixed-dim embeddings."""

    def __init__(
        self,
        l1_channels: int = 64,
        l2_channels: int = 128,
        l3_channels: int = 256,
        diff_channels: int = 64,
        proj_dim: int = 64,
    ):
        super().__init__()
        self.l1_proj = nn.Conv2d(l1_channels, proj_dim, 1)
        self.l2_proj = nn.Conv2d(l2_channels, proj_dim, 1)
        self.l3_proj = nn.Conv2d(l3_channels, proj_dim, 1)
        self.diff_proj = nn.Conv2d(diff_channels, proj_dim, 1)
        self.output_dim = proj_dim * 4  # 256

    def forward(
        self,
        teacher_l1: torch.Tensor,
        teacher_l2: torch.Tensor,
        teacher_l3: torch.Tensor,
        difference: torch.Tensor,
    ) -> torch.Tensor:
        f1 = F.adaptive_avg_pool2d(self.l1_proj(teacher_l1), 1).flatten(1)
        f2 = F.adaptive_avg_pool2d(self.l2_proj(teacher_l2), 1).flatten(1)
        f3 = F.adaptive_avg_pool2d(self.l3_proj(teacher_l3), 1).flatten(1)
        fd = F.adaptive_avg_pool2d(self.diff_proj(difference), 1).flatten(1)
        return torch.cat([f1, f2, f3, fd], dim=1)


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

        # EfficientAD feature branch
        self.ead_projector = EfficientADFeatureProjector()
        self.ead_proj = nn.Sequential(
            nn.Linear(256, 256),
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
                ead_features["teacher_l1"],
                ead_features["teacher_l2"],
                ead_features["teacher_l3"],
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
            "teacher_l1": torch.randn(1, 64, 56, 56),
            "teacher_l2": torch.randn(1, 128, 28, 28),
            "teacher_l3": torch.randn(1, 256, 14, 14),
            "difference": torch.randn(1, 64, 224, 224),
        }
        traced = torch.jit.trace(self, (example_img, example_features))
        traced.save(output_path)
