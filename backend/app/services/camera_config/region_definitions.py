from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.schemas.camera_config import CameraRegionDefinition


class RegionDefinitionError(ValueError):
    pass


class RegionDefinitionNotFoundError(RegionDefinitionError):
    pass


class RegionDefinitionLoader:
    """从 seat_defect_core 检测配置读取相机 Region 几何定义。"""

    def __init__(self, config_path: str | None = None, repo_root: str | Path | None = None) -> None:
        self._repo_root = Path(repo_root or Path(__file__).resolve().parents[4])
        self._config_path = self._resolve_config_path(config_path or settings.default_inspection_config)

    def _resolve_config_path(self, raw_path: str) -> Path:
        path = Path(raw_path)
        if path.is_absolute():
            return path
        backend_dir = self._repo_root / "backend"
        candidate = (backend_dir / path).resolve()
        if candidate.exists():
            return candidate
        return (self._repo_root / path).resolve()

    def load_for_camera(
        self,
        *,
        seat_model_id: str,
        camera_id: str,
    ) -> list[CameraRegionDefinition]:
        payload = self._load_payload()
        inspection = payload.get("seat_defect_inspection")
        if not isinstance(inspection, dict):
            raise RegionDefinitionError("检测配置缺少 seat_defect_inspection")

        seat_models = inspection.get("seat_models")
        if not isinstance(seat_models, list):
            raise RegionDefinitionError("检测配置缺少 seat_models")

        for seat_model in seat_models:
            if not isinstance(seat_model, dict) or seat_model.get("seat_model_id") != seat_model_id:
                continue
            cameras = seat_model.get("cameras")
            if not isinstance(cameras, list):
                raise RegionDefinitionError(f"座椅型号 {seat_model_id} 缺少 cameras")
            for camera in cameras:
                if not isinstance(camera, dict) or camera.get("camera_id") != camera_id:
                    continue
                return self._parse_regions(camera.get("regions", []))
            raise RegionDefinitionNotFoundError(
                f"检测配置中座椅型号 {seat_model_id} 不存在相机 {camera_id}"
            )

        raise RegionDefinitionNotFoundError(f"检测配置中不存在座椅型号 {seat_model_id}")

    def _load_payload(self) -> dict[str, Any]:
        try:
            with self._config_path.open("r", encoding="utf-8") as f:
                payload = json.load(f)
        except FileNotFoundError as exc:
            raise RegionDefinitionError(f"检测配置文件不存在: {self._config_path}") from exc
        except json.JSONDecodeError as exc:
            raise RegionDefinitionError(f"检测配置文件 JSON 无效: {self._config_path}") from exc
        if not isinstance(payload, dict):
            raise RegionDefinitionError("检测配置根节点必须是对象")
        return payload

    def _parse_regions(self, raw_regions: object) -> list[CameraRegionDefinition]:
        if raw_regions is None:
            return []
        if not isinstance(raw_regions, list):
            raise RegionDefinitionError("camera.regions 必须是数组")

        definitions: list[CameraRegionDefinition] = []
        seen: set[str] = set()
        for index, raw_region in enumerate(raw_regions):
            if not isinstance(raw_region, dict):
                raise RegionDefinitionError("region 必须是对象")
            region_id = raw_region.get("region_id")
            if not isinstance(region_id, str) or not region_id:
                raise RegionDefinitionError("region.region_id 必须是非空字符串")
            if region_id in seen:
                raise RegionDefinitionError(f"检测配置存在重复 region_id: {region_id}")
            seen.add(region_id)
            definition = CameraRegionDefinition(
                region_id=region_id,
                box=raw_region.get("box"),
                enabled=bool(raw_region.get("enabled", True)),
                sort_order=int(raw_region.get("sort_order", index)),
                patchcore=raw_region.get("patchcore"),
            )
            definitions.append(definition)

        definitions.sort(key=lambda item: item.sort_order)
        return definitions

