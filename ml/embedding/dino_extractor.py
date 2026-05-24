from __future__ import annotations

import torch
import numpy as np
from PIL import Image


class DINOv2EmbeddingExtractor:
    """DINOv2-small embedding extractor for high-quality visual features.

    DINOv2 produces richer embeddings than ResNet18, better capturing fine-grained
    visual differences relevant to industrial defect detection.
    """

    def __init__(self, model_name: str = "dinov2_vits14", device: str = "cpu") -> None:
        self._model_name = model_name
        self._device = device
        self._model = torch.hub.load(
            "facebookresearch/dinov2", model_name
        ).to(device)
        self._model.eval()

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return 384

    async def extract(self, image: np.ndarray) -> np.ndarray:
        """Async extract for FastAPI services (runs sync in thread)."""
        import asyncio
        return await asyncio.to_thread(self.extract_sync, image)

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
        from torchvision import transforms as T

        transform = T.Compose([
            T.Resize((224, 224)),
            T.ToTensor(),
            T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])
        return transform(pil_image)
