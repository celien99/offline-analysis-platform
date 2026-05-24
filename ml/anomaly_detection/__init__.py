"""Anomaly detection models — end-to-end student models distilled from PatchCore teacher."""

from .fastflow import FastFlowConfig, FastFlowModel
from .trainer import FastFlowTrainer
from .inference import FastFlowInference

__all__ = [
    "FastFlowConfig",
    "FastFlowModel",
    "FastFlowTrainer",
    "FastFlowInference",
]
