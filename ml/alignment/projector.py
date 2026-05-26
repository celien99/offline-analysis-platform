from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


class AlignmentProjector(nn.Module):
    """Projects EfficientAD features into EmbeddingSpaceContract-compatible 384d L2 space."""

    def __init__(self, config=None):
        super().__init__()
        from .config import AlignmentConfig
        cfg = config or AlignmentConfig()

        self.l1_proj = nn.Sequential(
            nn.AdaptiveAvgPool2d(1), nn.Flatten(1),
            nn.Linear(cfg.l1_channels, cfg.per_layer_proj_dim), nn.ReLU(inplace=True))
        self.l2_proj = nn.Sequential(
            nn.AdaptiveAvgPool2d(1), nn.Flatten(1),
            nn.Linear(cfg.l2_channels, cfg.per_layer_proj_dim), nn.ReLU(inplace=True))
        self.l3_proj = nn.Sequential(
            nn.AdaptiveAvgPool2d(1), nn.Flatten(1),
            nn.Linear(cfg.l3_channels, cfg.per_layer_proj_dim), nn.ReLU(inplace=True))
        self.diff_proj = nn.Sequential(
            nn.AdaptiveAvgPool2d(1), nn.Flatten(1),
            nn.Linear(cfg.diff_channels, cfg.per_layer_proj_dim), nn.ReLU(inplace=True))

        self.pos_embed = nn.Parameter(torch.randn(1, 4, cfg.transformer_dim) * 0.02)

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=cfg.transformer_dim, nhead=cfg.transformer_heads,
            dim_feedforward=cfg.transformer_ffn_dim, batch_first=True, activation="gelu")
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=cfg.transformer_layers)

        self.input_proj = nn.Linear(cfg.per_layer_proj_dim, cfg.transformer_dim)
        self.cls_token = nn.Parameter(torch.randn(1, 1, cfg.transformer_dim) * 0.02)
        self.output_proj = nn.Linear(cfg.transformer_dim, cfg.output_dim)
        self._cfg = cfg

    def forward(self, teacher_l1: torch.Tensor, teacher_l2: torch.Tensor,
                teacher_l3: torch.Tensor, difference: torch.Tensor) -> torch.Tensor:
        f1 = self.l1_proj(teacher_l1)
        f2 = self.l2_proj(teacher_l2)
        f3 = self.l3_proj(teacher_l3)
        fd = self.diff_proj(difference)
        tokens = torch.stack([f1, f2, f3, fd], dim=1)
        tokens = self.input_proj(tokens) + self.pos_embed
        B = tokens.size(0)
        cls_tokens = self.cls_token.expand(B, -1, -1)
        tokens = torch.cat([cls_tokens, tokens], dim=1)
        tokens = self.transformer(tokens)
        cls_out = tokens[:, 0, :]
        emb = self.output_proj(cls_out)
        return F.normalize(emb, p=2, dim=1)

    def to_torchscript(self, output_path: str) -> None:
        self.eval()
        B = 1
        example = (
            torch.randn(B, self._cfg.l1_channels, 56, 56),
            torch.randn(B, self._cfg.l2_channels, 28, 28),
            torch.randn(B, self._cfg.l3_channels, 14, 14),
            torch.randn(B, self._cfg.diff_channels, 224, 224),
        )
        traced = torch.jit.trace(self, example)
        traced.save(output_path)
