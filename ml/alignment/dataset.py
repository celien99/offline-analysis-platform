from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
from torch.utils.data import Dataset


class AlignmentDataset(Dataset):
    """Paired (EAD features, DINOv2 embedding) dataset for alignment training."""

    def __init__(self, ead_feature_paths: list[str], dino_embeddings: list[list[float]]):
        self.ead_paths = ead_feature_paths
        self.dino_embs = dino_embeddings
        assert len(self.ead_paths) == len(self.dino_embs)

    def __len__(self) -> int:
        return len(self.ead_paths)

    def __getitem__(self, idx: int) -> tuple[dict[str, torch.Tensor], torch.Tensor]:
        base = Path(self.ead_paths[idx])
        ead_features = {
            "teacher": torch.from_numpy(np.load(base / "teacher.npy")).float(),
            "student": torch.from_numpy(np.load(base / "student.npy")).float(),
            "difference": torch.from_numpy(np.load(base / "difference.npy")).float(),
        }
        for k in ead_features:
            t = ead_features[k]
            if t.dim() == 3:
                ead_features[k] = t.permute(2, 0, 1)
        dino_emb = torch.tensor(self.dino_embs[idx], dtype=torch.float32)
        return ead_features, dino_emb
