from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import torch
from PIL import Image
from torch.utils.data import Dataset
from torchvision import transforms


IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


def _build_transform(image_size: int, augment: bool = False) -> transforms.Compose:
    ops = [transforms.Resize((image_size, image_size))]
    if augment:
        ops.extend([
            transforms.RandomHorizontalFlip(),
            transforms.ColorJitter(brightness=0.1, contrast=0.1, saturation=0.1, hue=0.02),
            transforms.RandomRotation(degrees=15),
        ])
    ops.extend([
        transforms.ToTensor(),
        transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
    ])
    return transforms.Compose(ops)


class DualModalDataset(Dataset):
    """Dataset loading patch images + EfficientAD features + labels."""

    def __init__(self, images: list[np.ndarray], labels: list[int],
                 features_dir: Optional[str] = None,
                 proposal_ids: Optional[list[str]] = None,
                 image_size: int = 448, augment: bool = False):
        self.images = images
        self.labels = labels
        self.features_dir = Path(features_dir) if features_dir else None
        self.proposal_ids = proposal_ids or []
        self.transform = _build_transform(image_size, augment)

    def __len__(self) -> int:
        return len(self.images)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, Optional[dict[str, torch.Tensor]], int]:
        img_array = self.images[idx]
        if img_array.ndim == 3 and img_array.shape[2] == 3:
            img = Image.fromarray(img_array.astype(np.uint8))
        else:
            img = Image.fromarray(img_array.astype(np.uint8), mode="RGB")
        img_tensor = self.transform(img)
        label = self.labels[idx]

        ead_features = None
        if self.features_dir is not None and self.proposal_ids:
            pid = self.proposal_ids[idx]
            feat_dir = self.features_dir / pid
            try:
                ead_features = {
                    "teacher_l1": torch.from_numpy(np.load(feat_dir / "teacher_l1.npy")),
                    "teacher_l2": torch.from_numpy(np.load(feat_dir / "teacher_l2.npy")),
                    "teacher_l3": torch.from_numpy(np.load(feat_dir / "teacher_l3.npy")),
                    "difference": torch.from_numpy(np.load(feat_dir / "difference.npy")),
                }
            except (FileNotFoundError, OSError):
                ead_features = None

        return img_tensor, ead_features, label
