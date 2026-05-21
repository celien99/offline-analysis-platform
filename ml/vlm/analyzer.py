from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path

import httpx
from PIL import Image

from app.domain.multimodal import VLMRequest, VLMResult

ANALYSIS_PROMPT = """You are an industrial vision defect analysis expert.

Please analyze the following anomaly region.

Input information:
- Original image
- ROI image
- Heatmap
- Anomaly crop
- Current cluster representative images

Please output in JSON format:
1. suspected anomaly type
2. whether it looks more like a false alarm
3. possible reasons
4. suggested handling method
5. whether to suggest adding to false alarm library
"""


class QwenVLMAnalyzer:
    """Qwen2.5-VL based VLM analyzer for industrial defect explanation.

    Communicates with a VLM endpoint (vLLM/Ollama) to analyze anomaly images.
    """

    def __init__(
        self,
        endpoint: str = "http://localhost:8001/v1",
        model_name: str = "qwen2.5-vl",
        timeout: float = 120.0,
    ) -> None:
        self._endpoint = endpoint
        self._model_name = model_name
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
    def _ndarray_to_base64(image_array) -> str:
        import numpy as np
        img = Image.fromarray(image_array.astype(np.uint8)).convert("RGB")
        buffer = BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    async def analyze(self, request: VLMRequest) -> VLMResult:
        """Analyze anomaly images using the VLM."""
        content_parts: list[dict[str, object]] = [
            {"type": "text", "text": ANALYSIS_PROMPT}
        ]

        if request.crop_image is not None:
            b64 = self._ndarray_to_base64(request.crop_image)
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
            })

        if request.heatmap_image is not None:
            b64 = self._ndarray_to_base64(request.heatmap_image)
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
            })

        payload = {
            "model": self._model_name,
            "messages": [
                {"role": "user", "content": content_parts}
            ],
            "temperature": 0.3,
            "max_tokens": 512,
        }

        try:
            response = await self._client.post(
                f"{self._endpoint}/chat/completions",
                json=payload,
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
