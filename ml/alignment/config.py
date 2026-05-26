from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AlignmentConfig:
    l1_channels: int = 64
    l2_channels: int = 128
    l3_channels: int = 256
    diff_channels: int = 64
    per_layer_proj_dim: int = 128
    transformer_dim: int = 512
    transformer_heads: int = 4
    transformer_layers: int = 2
    transformer_ffn_dim: int = 1024
    output_dim: int = 384
    learning_rate: float = 1e-4
    temperature: float = 0.07
    batch_size: int = 64
    epochs: int = 30
    early_stopping_patience: int = 5
    output_dir: str = "./models"
