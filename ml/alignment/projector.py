from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


class AlignmentProjector(nn.Module):
    """将 EfficientAD (teacher, student, difference) 特征投影到 EmbeddingSpaceContract 384d L2 空间。

    接收 _extract_features() 产出的三组特征图，通过 AdaptiveAvgPool + Linear 投影后，
    经 Transformer Encoder 聚合为统一 embedding。
    """

    def __init__(self, config=None):
        super().__init__()
        from .config import AlignmentConfig
        cfg = config or AlignmentConfig()

        self.teacher_proj = nn.Sequential(
            nn.AdaptiveAvgPool2d(1), nn.Flatten(1),
            nn.Linear(cfg.teacher_channels, cfg.per_layer_proj_dim), nn.ReLU(inplace=True))
        self.student_proj = nn.Sequential(
            nn.AdaptiveAvgPool2d(1), nn.Flatten(1),
            nn.Linear(cfg.student_channels, cfg.per_layer_proj_dim), nn.ReLU(inplace=True))
        self.diff_proj = nn.Sequential(
            nn.AdaptiveAvgPool2d(1), nn.Flatten(1),
            nn.Linear(cfg.diff_channels, cfg.per_layer_proj_dim), nn.ReLU(inplace=True))

        self.pos_embed = nn.Parameter(torch.randn(1, 3, cfg.transformer_dim) * 0.02)

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=cfg.transformer_dim, nhead=cfg.transformer_heads,
            dim_feedforward=cfg.transformer_ffn_dim, batch_first=True, activation="gelu")
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=cfg.transformer_layers)

        self.input_proj = nn.Linear(cfg.per_layer_proj_dim, cfg.transformer_dim)
        self.cls_token = nn.Parameter(torch.randn(1, 1, cfg.transformer_dim) * 0.02)
        self.output_proj = nn.Linear(cfg.transformer_dim, cfg.output_dim)
        self._cfg = cfg

    def forward(self, teacher: torch.Tensor, student: torch.Tensor,
                difference: torch.Tensor) -> torch.Tensor:
        ft = self.teacher_proj(teacher)
        fs = self.student_proj(student)
        fd = self.diff_proj(difference)
        tokens = torch.stack([ft, fs, fd], dim=1)
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
            torch.randn(B, self._cfg.teacher_channels, 64, 64),
            torch.randn(B, self._cfg.student_channels, 64, 64),
            torch.randn(B, self._cfg.diff_channels, 64, 64),
        )
        traced = torch.jit.trace(self, example)
        traced.save(output_path)
