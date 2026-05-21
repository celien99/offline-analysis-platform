from __future__ import annotations

import torch
import numpy as np
from PIL import Image
from torchvision import models, transforms as T


class EfficientNetEmbeddingExtractor:
    """EfficientNet-B0 embedding extractor for lightweight feature extraction.

    Offers a good speed/quality trade-off for resource-constrained deployments.
    """

    def __init__(self, device: str = "cpu") -> None:
        self._device = device
        base = models.efficientnet_b0(weights=models.EfficientNet_B0_Weights.IMAGENET1K_V1)
        self._model = torch.nn.Sequential(
            base.features,
            base.avgpool,
            torch.nn.Flatten(),
        ).to(device)
        self._model.eval()

    @property
    def model_name(self) -> str:
        return "efficientnet_b0"

    @property
    def dimension(self) -> int:
        return 1280

    def extract_sync(self, image: np.ndarray) -> np.ndarray:
        pil = Image.fromarray(image.astype(np.uint8)).convert("RGB")
        img_tensor = self._preprocess(pil).unsqueeze(0).to(self._device)
        with torch.no_grad():
            embedding = self._model(img_tensor)
        return embedding.squeeze(0).cpu().numpy()

    def extract_batch_sync(self, images: list[np.ndarray]) -> np.ndarray:
        tensors = []
        for img in images:
            pil = Image.fromarray(img.astype(np.uint8)).convert("RGB")
            tensors.append(self._preprocess(pil))
        batch = torch.stack(tensors).to(self._device)
        with torch.no_grad():
            embeddings = self._model(batch)
        return embeddings.cpu().numpy()

    @staticmethod
    def _preprocess(pil_image: Image.Image) -> torch.Tensor:
        transform = T.Compose([
            T.Resize((224, 224)),
            T.ToTensor(),
            T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])
        return transform(pil_image)
