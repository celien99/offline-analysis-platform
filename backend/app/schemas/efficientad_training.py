from __future__ import annotations

from pydantic import BaseModel, Field


class EfficientADTrainingStartRequest(BaseModel):
    """EfficientAD 训练请求参数。仅暴露 camera_id 和图片，其余配置内置于 config 文件中。"""

    camera_id: str = Field(..., description="目标相机 ID（对应 config 中的 camera_id）")
    config_json: str = Field(..., description="序列化为 JSON 的检测配置文件内容")
