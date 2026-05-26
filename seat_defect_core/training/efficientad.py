"""EfficientAD 模型训练。

基于 anomalib 的 EfficientAD 实现，从正常参考图像训练异常检测模型。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

import cv2
import numpy as np
import torch


def train_efficientad(
    config: object,
    camera_id: str,
    good_image_paths: Sequence[str | Path],
    output_path: str,
) -> dict:
    """训练 EfficientAD 模型并导出 TorchScript。

    Args:
        config: InspectionConfig 或 JSON 配置文件路径。
        camera_id: 目标相机 ID。
        good_image_paths: 正常参考图像路径列表。
        output_path: 输出 .pt 文件路径。

    Returns:
        dict: {status, artifact_path, image_threshold, train_image_count}
    """
    from ..config import InspectionConfig
    from ..config_file import resolve_config
    from ..efficientad.config import EfficientADConfig

    # 解析配置
    if isinstance(config, (str, Path)):
        inspection_cfg = resolve_config(str(config))
    elif isinstance(config, InspectionConfig):
        inspection_cfg = config
    else:
        raise TypeError(f"config 类型不支持: {type(config)}")

    camera_config = _find_camera(inspection_cfg, camera_id)
    if camera_config is None:
        available = _list_camera_ids(inspection_cfg)
        raise ValueError(f"未找到相机 '{camera_id}'，可用相机: {available}")

    efficientad_cfg = camera_config.efficientad
    if efficientad_cfg is None:
        raise ValueError(f"相机 '{camera_id}' 未配置 efficientad 参数")

    # 加载正常图像
    images: list[np.ndarray] = []
    for img_path in good_image_paths:
        img_path = Path(img_path)
        if not img_path.exists():
            continue
        img = cv2.imread(str(img_path))
        if img is not None:
            images.append(img)

    if len(images) < 2:
        raise RuntimeError(f"正常参考图像不足 ({len(images)} 张)，至少需要 2 张")

    device = _resolve_train_device(efficientad_cfg.device)

    # 使用 anomalib 训练
    try:
        from anomalib.data import MVTec
        from anomalib.models import EfficientAd
        from anomalib.engine import Engine
    except ImportError:
        raise RuntimeError(
            "EfficientAD 训练依赖 anomalib 库，请安装: pip install anomalib"
        )

    # 创建临时数据集目录结构
    import tempfile
    import shutil

    tmp_dir = Path(tempfile.mkdtemp(prefix="efficientad_train_"))
    try:
        # anomalib MVTec 格式: {category}/train/good/
        category = camera_id.replace(" ", "_")
        good_dir = tmp_dir / category / "train" / "good"
        good_dir.mkdir(parents=True, exist_ok=True)

        for i, img in enumerate(images):
            cv2.imwrite(str(good_dir / f"{i:04d}.png"), img)

        # 配置 anomalib 模型
        model = EfficientAd(
            teacher_out_channels=384,
            model_size="medium",
        )

        # 训练
        engine = Engine(
            max_epochs=efficientad_cfg.epochs,
            devices=1 if device.type != "cpu" else 0,
            accelerator="gpu" if device.type == "cuda" else "cpu",
            default_root_dir=str(tmp_dir / "results"),
        )

        datamodule = MVTec(
            root=str(tmp_dir),
            category=category,
            image_size=(efficientad_cfg.input_size, efficientad_cfg.input_size),
            train_batch_size=efficientad_cfg.batch_size,
            eval_batch_size=efficientad_cfg.batch_size,
            num_workers=0,
        )

        engine.fit(model=model, datamodule=datamodule)

        # 导出 TorchScript
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        model.eval()
        example_input = torch.randn(1, 3, efficientad_cfg.input_size, efficientad_cfg.input_size)
        traced = torch.jit.trace(model, example_input.to(device))
        traced.save(str(output))

        # 保存阈值元数据
        image_threshold = 0.5  # anomalib 默认
        meta = {
            "image_threshold": image_threshold,
            "input_size": efficientad_cfg.input_size,
            "teacher_backbone": efficientad_cfg.teacher_backbone,
            "student_backbone": efficientad_cfg.student_backbone,
            "train_image_count": len(images),
            "epochs": efficientad_cfg.epochs,
        }
        meta_path = output.with_suffix(".meta.json")
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2))

        return {
            "status": "completed",
            "artifact_path": str(output),
            "image_threshold": image_threshold,
            "train_image_count": len(images),
        }
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def train_efficientad_cli() -> None:
    """CLI 入口：由 seat_defect_core.__main__ 调用。"""
    import argparse

    parser = argparse.ArgumentParser(description="训练 EfficientAD 模型")
    parser.add_argument("--config", required=True, help="检测配置文件路径 (JSON/INI)")
    parser.add_argument("--camera-id", required=True, help="目标相机 ID")
    parser.add_argument("--good-images", required=True, help="正常参考图像目录")
    parser.add_argument("--output", required=True, help="输出 .pt 文件路径")

    args = parser.parse_args()

    img_dir = Path(args.good_images)
    if not img_dir.is_dir():
        raise FileNotFoundError(f"图像目录不存在: {args.good_images}")

    image_paths: list[str] = []
    for ext in ("*.jpg", "*.jpeg", "*.png", "*.bmp"):
        image_paths.extend(str(p) for p in img_dir.glob(ext))
    if not image_paths:
        raise FileNotFoundError(f"目录中未找到图像文件: {args.good_images}")

    result = train_efficientad(
        config=args.config,
        camera_id=args.camera_id,
        good_image_paths=image_paths,
        output_path=args.output,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


def _find_camera(inspection_cfg, camera_id: str):
    """在配置中查找指定相机。"""
    from ..config import SeatModelConfig

    for cam in getattr(inspection_cfg, "cameras", []) or []:
        if cam.camera_id == camera_id:
            return cam
    seat_models: list = getattr(inspection_cfg, "seat_models", []) or []
    for sm in seat_models:
        for cam in getattr(sm, "cameras", []) or []:
            if cam.camera_id == camera_id:
                return cam
    return None


def _list_camera_ids(inspection_cfg) -> list[str]:
    """列出配置中所有相机 ID。"""
    ids: list[str] = []
    for cam in getattr(inspection_cfg, "cameras", []) or []:
        ids.append(cam.camera_id)
    for sm in getattr(inspection_cfg, "seat_models", []) or []:
        for cam in getattr(sm, "cameras", []) or []:
            ids.append(cam.camera_id)
    return ids


def _resolve_train_device(requested: str) -> torch.device:
    """解析训练设备。"""
    normalized = requested.strip().lower()
    if normalized.startswith("cuda") and torch.cuda.is_available():
        return torch.device("cuda")
    if normalized == "mps" and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")
