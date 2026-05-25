from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path

import httpx
import numpy as np
from PIL import Image

from app.domain.multimodal import VLMRequest, VLMResult

ANALYSIS_PROMPT = """你是一名汽车座椅质检专家。你将看到一张从汽车座椅图像中自动裁剪出的**可疑区域**。

请判断：**正常座椅上是否应该存在这个东西？**

返回 JSON：
{
  "type": "若判定为异常，异常类型 (scratch/stain/wrinkle/hole/seam_shift/foreign_object/reflection/other/none)",
  "is_false_alarm": true 或 false,
  "reason": "判定原因（中文）",
  "confidence": 0.0到1.0之间的置信度,
  "suggestion": "manual_review 或 add_to_false_alarm_library"
}

判断标准：
1. 这是正常座椅面料、缝线、logo、褶皱、光影或已知结构的一部分 → is_false_alarm=true
2. 这是正常座椅上**不应该出现**的东西（破损、污渍、异物、异常变形等）→ is_false_alarm=false
3. 不确定或处于边界情况 → is_false_alarm=false, suggestion="manual_review"
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

        # 主图：缺陷区域裁剪（支持多张 crop，cluster 分析时传递更多样本给 VLM）
        crop_imgs = request.crop_images.copy() if request.crop_images else []
        if request.crop_image is not None:
            crop_imgs.insert(0, request.crop_image)
        for crop_arr in crop_imgs:
            b64 = self._ndarray_to_base64(crop_arr)
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
            raw_text: str = data["choices"][0]["message"]["content"]

            return self._parse_response(raw_text)

        except httpx.HTTPError as e:
            return VLMResult(
                anomaly_type="error",
                is_false_alarm=False,
                reason=f"VLM API error: {e}",
                confidence=0.0,
                suggestion="retry",
            )

    @staticmethod
    def _parse_response(raw_text: str) -> VLMResult:
        """Robustly parse VLM response, handling various JSON formats."""
        import json
        import re

        cleaned = raw_text.strip()

        # 1. Strip markdown code fences
        cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```\s*$", "", cleaned)

        parsed: dict[str, object] = {}
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            # 2. Try to extract JSON object from text
            m = re.search(r"\{[^{}]*\}", cleaned, re.DOTALL)
            if m:
                try:
                    parsed = json.loads(m.group())
                except json.JSONDecodeError:
                    pass

        if not parsed:
            return VLMResult(
                anomaly_type="unknown",
                is_false_alarm=False,
                reason=f"Failed to parse VLM response: {raw_text[:200]}",
                confidence=0.0,
                suggestion="manual_review",
                raw_response=raw_text,
            )

        # 3. Extract fields with multiple possible key names
        anomaly_type = str(
            parsed.get("type")
            or parsed.get("anomaly_type")
            or parsed.get("suspected_anomaly_type")
            or "unknown"
        )
        raw_fa = parsed.get("is_false_alarm")
        if raw_fa is None:
            raw_fa = parsed.get("whether_it_looks_more_like_a_false_alarm")
        is_false_alarm = bool(raw_fa) if raw_fa is not None else False
        reason = str(
            parsed.get("reason")
            or parsed.get("possible_reasons")
            or parsed.get("failure_reason")
            or ""
        )
        # reason 可能是 list → join 成 string
        if isinstance(parsed.get("possible_reasons"), list):
            reason = "; ".join(str(r) for r in parsed["possible_reasons"])

        confidence = float(parsed.get("confidence", 0.5))
        suggestion = str(
            parsed.get("suggestion")
            or parsed.get("suggested_handling_method")
            or "manual_review"
        )

        return VLMResult(
            anomaly_type=anomaly_type,
            is_false_alarm=is_false_alarm,
            reason=reason,
            confidence=confidence,
            suggestion=suggestion,
            raw_response=raw_text,
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
