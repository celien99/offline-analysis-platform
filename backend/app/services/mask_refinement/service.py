"""Mask Refinement 服务 — 背景消除、标准化处理

在 embedding 提取之前对 anomaly crop 进行预处理：
1. GrabCut 前景/背景分离
2. 直方图均衡化（光照标准化）
3. 形态学操作（去噪、孔洞填充）
4. 输出标准化大小的 cleaned crop
"""
from __future__ import annotations

from io import BytesIO

import numpy as np
from PIL import Image

from app.common.logging import get_logger
from app.infrastructure.storage.minio_client import minio_client

logger = get_logger(__name__)


class MaskRefinementService:
    """图像掩码精化服务 — 支持本地处理和 SAM2 预留接口"""

    def __init__(self) -> None:
        self._target_size = (224, 224)

    async def refine_from_minio(
        self,
        crop_path: str,
        *,
        use_grabcut: bool = True,
        equalize_hist: bool = True,
    ) -> bytes | None:
        """从 MinIO 下载 crop 图片，执行 mask 精化，返回处理后的 PNG 字节"""
        try:
            raw = await minio_client.download(crop_path)
        except Exception as exc:
            logger.warning("mask_refine_download_failed", path=crop_path, error=str(exc))
            return None

        img = np.array(Image.open(BytesIO(raw)).convert("RGB"))
        refined = self.refine(img, use_grabcut=use_grabcut, equalize_hist=equalize_hist)

        buf = BytesIO()
        Image.fromarray(refined).save(buf, format="PNG")
        return buf.getvalue()

    def refine(
        self,
        image: np.ndarray,
        *,
        use_grabcut: bool = True,
        equalize_hist: bool = True,
    ) -> np.ndarray:
        """对单张 numpy (H, W, 3) 图像执行 mask 精化"""
        h, w = image.shape[:2]

        if use_grabcut and min(h, w) > 30:
            mask = self._grabcut_foreground(image)
            image = self._apply_mask(image, mask)

        if equalize_hist:
            image = self._equalize_lighting(image)

        image = self._resize_standard(image)

        return image

    # ── GrabCut 前景分离 ───────────────────────────────

    def _grabcut_foreground(self, image: np.ndarray) -> np.ndarray:
        """使用 GrabCut 提取前景 mask"""
        try:
            import cv2
        except ImportError:
            logger.warning("cv2_not_available_skipping_grabcut")
            return np.ones(image.shape[:2], dtype=np.uint8)

        h, w = image.shape[:2]
        # 中心矩形作为初始前景区域
        margin_x = max(w // 6, 10)
        margin_y = max(h // 6, 10)
        rect = (margin_x, margin_y, w - 2 * margin_x, h - 2 * margin_y)

        mask = np.zeros((h, w), dtype=np.uint8)
        bgd_model = np.zeros((1, 65), dtype=np.float64)
        fgd_model = np.zeros((1, 65), dtype=np.float64)

        try:
            cv2.grabCut(image, mask, rect, bgd_model, fgd_model, 3, cv2.GC_INIT_WITH_RECT)
        except cv2.error:
            return np.ones((h, w), dtype=np.uint8)

        # 前景和可能前景设为 1
        fg_mask = np.where((mask == 1) | (mask == 3), 1, 0).astype(np.uint8)

        # 形态学闭运算：填充孔洞
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        # 开运算：去噪
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel, iterations=1)

        return fg_mask

    # ── 光照标准化 ────────────────────────────────────

    def _equalize_lighting(self, image: np.ndarray) -> np.ndarray:
        """CLAHE 自适应直方图均衡化"""
        try:
            import cv2
        except ImportError:
            return image

        lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l_eq = clahe.apply(l_channel)
        lab_eq = cv2.merge([l_eq, a_channel, b_channel])
        return cv2.cvtColor(lab_eq, cv2.COLOR_LAB2RGB)

    # ── 标准化 ────────────────────────────────────────

    def _resize_standard(self, image: np.ndarray) -> np.ndarray:
        """调整到标准尺寸，保持宽高比，填充黑边"""
        try:
            import cv2
        except ImportError:
            pil_img = Image.fromarray(image)
            pil_img = pil_img.resize(self._target_size, Image.LANCZOS)
            return np.array(pil_img)

        h, w = image.shape[:2]
        target_w, target_h = self._target_size
        scale = min(target_w / w, target_h / h)
        new_w, new_h = int(w * scale), int(h * scale)
        resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)

        canvas = np.zeros((target_h, target_w, 3), dtype=np.uint8)
        x_offset = (target_w - new_w) // 2
        y_offset = (target_h - new_h) // 2
        canvas[y_offset:y_offset + new_h, x_offset:x_offset + new_w] = resized

        return canvas

    # ── 辅助 ──────────────────────────────────────────

    def _apply_mask(
        self, image: np.ndarray, mask: np.ndarray
    ) -> np.ndarray:
        """将 mask 应用到图像，背景置为黑色"""
        mask_3ch = np.stack([mask] * 3, axis=-1)
        return (image * mask_3ch).astype(np.uint8)
