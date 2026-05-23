from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path

import httpx
import numpy as np
from PIL import Image

from app.domain.multimodal import VLMRequest, VLMResult

ANALYSIS_PROMPT = """你是一名工业视觉缺陷分析专家。请仔细观察以下裁剪图片，这些图片是从汽车座椅生产线上检测到的异常区域。

请分析并返回 JSON 格式的结果：
{
  "type": "缺陷类型 (wrinkle/scratch/reflection/stain/seam_shift/other)",
  "is_false_alarm": true或false,
  "reason": "判定原因的简要说明（中文）",
  "confidence": 0.0到1.0之间的置信度,
  "suggestion": "manual_review 或 add_to_false_alarm_library"
}
"""


class QwenVLMAnalyzer:
    """基于 OpenAI 兼容 API 的视觉分析器，用于工业缺陷分析。"""

    def __init__(
        self,
        endpoint: str = "http://localhost:8001/v1",
        model_name: str = "qwen2.5-vl",
        api_key: str = "",
        timeout: float = 120.0,
    ) -> None:
        self._endpoint = endpoint
        self._model_name = model_name
        self._api_key = api_key
        self._timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout)

    @property
    def model_name(self) -> str:
        return self._model_name

    @staticmethod
    def _image_to_base64(image_path: str | Path) -> str:
        img = Image.open(image_path).convert("RGB")
        buffer = BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    @staticmethod
    def _ndarray_to_base64(image_array: np.ndarray) -> str:
        img = Image.fromarray(image_array.astype(np.uint8)).convert("RGB")
        buffer = BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    async def analyze(self, request: VLMRequest) -> VLMResult:
        """Analyze anomaly images using the VLM.

        发送图片优先级：
        1. crop_image: 缺陷区域裁剪（最重要）
        2. original_image: 原图全局上下文
        不发送 heatmap_image（热力图叠加热图会遮挡原图内容，干扰 VLM 判断）。
        """
        content_parts: list[dict[str, object]] = [
            {"type": "text", "text": ANALYSIS_PROMPT}
        ]

        # 主图：缺陷区域裁剪
        if request.crop_image is not None:
            b64 = self._ndarray_to_base64(request.crop_image)
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
            })

        # 辅图：原图全局上下文（放后面，模型可据此判断缺陷位置）
        if request.original_image is not None:
            b64 = self._ndarray_to_base64(request.original_image)
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
            })

        # 不发送 heatmap_image：热力图叠加会遮挡原图纹理，影响模型判断

        payload = {
            "model": self._model_name,
            "messages": [
                {"role": "user", "content": content_parts}
            ],
            "temperature": 0.3,
            "max_tokens": 512,
        }

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        try:
            response = await self._client.post(
                f"{self._endpoint}/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            raw_text = data["choices"][0]["message"]["content"]

            import json
            try:
                parsed = json.loads(raw_text)
                return VLMResult(
                    anomaly_type=parsed.get("type", "unknown"),
                    is_false_alarm=parsed.get("is_false_alarm", False),
                    reason=parsed.get("reason", ""),
                    confidence=float(parsed.get("confidence", 0.5)),
                    suggestion=parsed.get("suggestion", "manual_review"),
                    raw_response=raw_text,
                )
            except (json.JSONDecodeError, KeyError):
                return VLMResult(
                    anomaly_type="unknown",
                    is_false_alarm=False,
                    reason="Failed to parse VLM response",
                    confidence=0.0,
                    suggestion="manual_review",
                    raw_response=raw_text,
                )

        except httpx.HTTPError as e:
            return VLMResult(
                anomaly_type="error",
                is_false_alarm=False,
                reason=f"VLM API error: {e}",
                confidence=0.0,
                suggestion="retry",
            )

    async def batch_analyze(
        self, requests: list[VLMRequest]
    ) -> list[VLMResult]:
        results: list[VLMResult] = []
        for req in requests:
            results.append(await self.analyze(req))
        return results

    async def close(self) -> None:
        await self._client.aclose()
