from __future__ import annotations

from io import BytesIO

import numpy as np
import torch
from PIL import Image
from torchvision import models, transforms

from app.common.logging import get_logger
from app.infrastructure.queue.celery_app import celery_app
from app.infrastructure.storage.minio_client import minio_client
from app.workers import run_async

logger = get_logger(__name__)

_model: object = None
_transform: object = None


def _get_gradcam_model():
    global _model, _transform
    if _model is None:
        base = models.resnet18(weights=models.ResNet18_Weights.IMAGENET1K_V1)
        base.eval()
        _model = base
        _transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])
    return _model, _transform


def _generate_gradcam(image: np.ndarray) -> np.ndarray:
    """Generate a Grad-CAM heatmap from the last conv layer of ResNet18."""
    model, transform = _get_gradcam_model()

    pil = Image.fromarray(image.astype(np.uint8)).convert("RGB")
    input_tensor = transform(pil).unsqueeze(0)

    target_layer = model.layer4[-1]
    activations: dict[str, torch.Tensor] = {}
    gradients: dict[str, torch.Tensor] = {}

    def _forward_hook(module, inp, out):
        activations["value"] = out

    def _backward_hook(module, grad_in, grad_out):
        gradients["value"] = grad_out[0]

    fh = target_layer.register_forward_hook(_forward_hook)
    bh = target_layer.register_full_backward_hook(_backward_hook)

    output = model(input_tensor)
    target = output[:, output.argmax(dim=1).item()]

    model.zero_grad()
    target.backward()

    fh.remove()
    bh.remove()

    pooled_gradients = torch.mean(gradients["value"], dim=[0, 2, 3])
    for i in range(pooled_gradients.shape[0]):
        activations["value"][:, i, :, :] *= pooled_gradients[i]

    heatmap = torch.mean(activations["value"], dim=1).squeeze().detach().numpy()
    heatmap = np.maximum(heatmap, 0)
    heatmap /= heatmap.max() + 1e-8

    heatmap = np.uint8(255 * heatmap)
    heatmap_resized = np.array(Image.fromarray(heatmap).resize(
        (image.shape[1], image.shape[0]), Image.BILINEAR,
    ))
    return heatmap_resized


@celery_app.task(name="heatmap.generate")
def generate_heatmap(
    anomaly_id: str,
    original_path: str,
    roi_path: str | None = None,
) -> dict[str, object]:
    logger.info("heatmap_task_started", anomaly_id=anomaly_id)

    try:
        async def _run() -> dict[str, object]:
            raw = await minio_client.download(original_path)
            image = np.array(Image.open(BytesIO(raw)).convert("RGB"))

            heatmap = _generate_gradcam(image)

            heatmap_img = Image.fromarray(heatmap).convert("RGB")
            buf = BytesIO()
            heatmap_img.save(buf, format="JPEG", quality=85)
            heatmap_bytes = buf.getvalue()

            date_str = original_path.split("/")[1] if "/" in original_path else "unknown"
            cam_str = original_path.split("/")[2] if len(original_path.split("/")) > 2 else "unknown"
            heatmap_path = f"anomaly_data/{date_str}/{cam_str}/{anomaly_id}_heatmap.jpg"
            await minio_client.upload(heatmap_path, heatmap_bytes, "image/jpeg")

            from app.infrastructure.database.session import async_session_factory
            from app.repositories.anomaly.repository import AnomalyRepository

            async with async_session_factory() as session:
                anomaly_repo = AnomalyRepository(session)
                anomaly = await anomaly_repo.get_by_id(anomaly_id)
                if anomaly is not None:
                    anomaly.heatmap_path = heatmap_path
                    await session.commit()

            logger.info("heatmap_task_complete", anomaly_id=anomaly_id, path=heatmap_path)
            return {"status": "completed", "anomaly_id": anomaly_id, "heatmap_path": heatmap_path}

        return run_async(_run())
    except Exception as e:
        logger.error("heatmap_task_failed", anomaly_id=anomaly_id, error=str(e))
        return {"status": "failed", "anomaly_id": anomaly_id, "error": str(e)}
