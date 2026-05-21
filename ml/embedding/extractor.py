from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn
from PIL import Image
from torchvision import models, transforms


class ResNet18EmbeddingExtractor:
    """ResNet18-based embedding extractor for anomaly images.

    Uses pretrained ResNet18 with the final classification layer removed.
    Outputs 512-dimensional feature vectors suitable for clustering and similarity search.
    """

    IMAGE_SIZE = (224, 224)
    OUTPUT_DIM = 512

    def __init__(self, device: str = "cpu") -> None:
        self._device = device
        self._model = self._build_model()
        self._model.eval()

        self._transform = transforms.Compose([
            transforms.Resize(self.IMAGE_SIZE),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ),
        ])

    def _build_model(self) -> nn.Module:
        model = models.resnet18(weights=models.ResNet18_Weights.IMAGENET1K_V1)
        model = nn.Sequential(*list(model.children())[:-1])
        model = model.to(self._device)
        return model

    @property
    def model_name(self) -> str:
        return "resnet18"

    @property
    def dimension(self) -> int:
        return self.OUTPUT_DIM

    async def extract(self, image: np.ndarray) -> np.ndarray:
        """Extract embedding vector from an image (numpy array RGB format)."""
        pil_image = Image.fromarray(image.astype(np.uint8)).convert("RGB")
        tensor = self._transform(pil_image).unsqueeze(0).to(self._device)

        with torch.no_grad():
            embedding = self._model(tensor)

        return embedding.squeeze().cpu().numpy()

    def extract_sync(self, image: np.ndarray) -> np.ndarray:
        """Synchronous version for use in Celery workers."""
        pil_image = Image.fromarray(image.astype(np.uint8)).convert("RGB")
        tensor = self._transform(pil_image).unsqueeze(0).to(self._device)

        with torch.no_grad():
            embedding = self._model(tensor)

        return embedding.squeeze().cpu().numpy()

    def batch_extract(self, images: list[np.ndarray]) -> np.ndarray:
        """Batch extract embeddings from multiple images."""
        tensors = []
        for img in images:
            pil = Image.fromarray(img.astype(np.uint8)).convert("RGB")
            tensors.append(self._transform(pil))
        batch = torch.stack(tensors).to(self._device)

        with torch.no_grad():
            embeddings = self._model(batch)

        return embeddings.squeeze().cpu().numpy()
