"""Pydantic schemas — API 请求/响应模型。

在线（seat_defect_core）与离线（backend）交互的 schema 版本化约定：
- CURRENT_SCHEMA_VERSION 在每次 breaking change 时递增
- 在线端上传异常时从响应中校验 schema_version
- 部署 manifest 中携带 schema_version，确保在线端能正确解析模型配置
"""

CURRENT_SCHEMA_VERSION = "1.0"
