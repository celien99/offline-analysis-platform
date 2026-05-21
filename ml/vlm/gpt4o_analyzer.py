from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path

import httpx
from PIL import Image

from app.domain.multimodal import VLMRequest, VLMResult
from ml.vlm.analyzer import ANALYSIS_PROMPT


class GPT4oAnalyzer:
    """GPT-4o based VLM analyzer for cloud-based analysis.

    Uses the OpenAI API (or Azure OpenAI) to analyze industrial defect images.
    """

    def __init__(
        self,
        api_key: str = "",
        endpoint: str = "https://api.openai.com/v1",
        model_name: str = "gpt-4o",
        timeout: float = 120.0,
    ) -> None:
        self._endpoint = endpoint
        self._model_name = model_name
        self._timeout = timeout
        self._client = httpx.AsyncClient(
            timeout=timeout,
            headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
        )

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
        content_parts: list[dict[str, object]] = [
            {"type": "text", "text": ANALYSIS_PROMPT}
        ]

        import numpy as np
        for img_field in [
            request.crop_image,
            request.heatmap_image,
            request.original_image,
            request.roi_image,
        ]:
            if img_field is not None:
                b64 = self._ndarray_to_base64(img_field)
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                })

        payload = {
            "model": self._model_name,
            "messages": [{"role": "user", "content": content_parts}],
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
                    reason="Failed to parse GPT-4o response",
                    confidence=0.0,
                    suggestion="manual_review",
                    raw_response=raw_text,
                )
        except httpx.HTTPError as e:
            return VLMResult(
                anomaly_type="error",
                is_false_alarm=False,
                reason=f"GPT-4o API error: {e}",
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
