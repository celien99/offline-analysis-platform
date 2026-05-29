"""EfficientAD 模型训练。

基于 anomalib 的 EfficientAD 实现，从正常参考图像训练异常检测模型。
训练完成后自动计算最优阈值并记录 MLflow 实验。
"""

from __future__ import annotations

import json
import inspect
import time
from pathlib import Path
from typing import Optional, Sequence, Type

import cv2
import numpy as np
import torch


class _EfficientADExportWrapper(torch.nn.Module):
    """把 anomalib InferenceBatch 规范化为推理服务期望的 TorchScript 输出。"""

    def __init__(self, model: torch.nn.Module) -> None:
        super().__init__()
        self.model = model
        self.register_buffer("mean", torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1))
        self.register_buffer("std", torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1))

    def forward(self, batch: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        # 线上 EfficientADService 已做 ImageNet normalize；anomalib 内部模型会自行 normalize。
        batch = (batch * self.std + self.mean).clamp(0.0, 1.0)
        output = self.model(batch)
        return output.anomaly_map, output.pred_score


def train_efficientad(
    config: object,
    camera_id: str,
    good_image_paths: Sequence[str | Path],
    output_path: str,
    *,
    mlflow_tracking_uri: Optional[str] = None,
    mlflow_experiment: str = "efficientad",
) -> dict:
    """训练 EfficientAD 模型并导出 TorchScript。

    Args:
        config: InspectionConfig 或 JSON 配置文件路径。
        camera_id: 目标相机 ID。
        good_image_paths: 正常参考图像路径列表。
        output_path: 输出 .pt 文件路径。
        mlflow_tracking_uri: MLflow tracking URI，为 None 则不记录。
        mlflow_experiment: MLflow 实验名称。

    Returns:
        dict: {status, artifact_path, image_threshold, pixel_threshold, train_image_count, mlflow_run_id}
    """
    from ..config import InspectionConfig
    from ..api import resolve_config

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

    # 只收集文件路径，不在内存中累积高分辨率 numpy 数组，避免 cv::OutOfMemoryError
    image_paths: list[Path] = [Path(p) for p in good_image_paths if Path(p).exists()]
    if len(image_paths) < 2:
        raise RuntimeError(f"正常参考图像不足 ({len(image_paths)} 张)，至少需要 2 张")

    device = _resolve_train_device(efficientad_cfg.device)

    # GPU 性能优化：针对 RTX 4060 (Ada Lovelace) 及以上架构
    if device.type == "cuda":
        _configure_gpu()

    # 只使用正常图训练时，Folder 数据模块可以直接从 train/good 中拆分验证集。
    try:
        from anomalib.data import Folder as FolderDataModule
        from anomalib.models import EfficientAd
        from anomalib.engine import Engine
    except ImportError as exc:
        try:
            from anomalib.data.image.folder import Folder as FolderDataModule
            from anomalib.models import EfficientAd
            from anomalib.engine import Engine
        except ImportError as fallback_exc:
            detail = f"{fallback_exc.__class__.__name__}: {fallback_exc}"
            if str(exc) != str(fallback_exc):
                detail = f"{exc.__class__.__name__}: {exc}; fallback {detail}"
            raise RuntimeError(
                "EfficientAD training requires anomalib and its runtime dependencies. "
                "Install them in the active Python environment with: pip install anomalib. "
                f"Underlying import error: {detail}"
            ) from fallback_exc
    datamodule_cls: Type = FolderDataModule

    import tempfile
    import shutil

    # MLflow 初始化
    mlflow_run_id: Optional[str] = None
    mlflow = _init_mlflow(mlflow_tracking_uri, mlflow_experiment)

    tmp_dir = Path(tempfile.mkdtemp(prefix="efficientad_train_"))
    t_start = time.monotonic()
    try:
        # anomalib MVTec 格式: {category}/train/good/ + {category}/test/good/ (用于阈值计算)
        category = camera_id.replace(" ", "_")
        good_dir = tmp_dir / category / "train" / "good"
        good_dir.mkdir(parents=True, exist_ok=True)

        # 划分训练集和阈值计算集 (90/10)
        split_idx = max(1, int(len(image_paths) * (1.0 - efficientad_cfg.validation_split)))
        train_paths = image_paths[:split_idx]
        threshold_paths = image_paths[split_idx:] if split_idx < len(image_paths) else image_paths[:1]

        # 直接复制原图到 anomalib 目录（保留原始格式，不做 decode→re-encode）
        for i, src in enumerate(train_paths):
            shutil.copy2(str(src), str(good_dir / f"{i:04d}{src.suffix}"))

        test_good_dir = tmp_dir / category / "test" / "good"
        test_good_dir.mkdir(parents=True, exist_ok=True)
        for i, src in enumerate(threshold_paths):
            shutil.copy2(str(src), str(test_good_dir / f"{i:04d}{src.suffix}"))

        # 配置 anomalib 模型
        model = EfficientAd(
            teacher_out_channels=384,
            model_size="medium",
        )

        # 训练
        # EfficientAD 架构要求 train_batch_size=1，这是模型设计的硬约束
        # （teacher-student 知识蒸馏 + 特征统计依赖 per-image 处理）
        # 通过 gradient_accumulation 增大有效 batch size，减少 optimizer step 开销
        train_batch_size = 1
        engine_kwargs: dict = {
            "max_epochs": efficientad_cfg.epochs,
            "devices": 1 if device.type != "cpu" else 0,
            "accelerator": "gpu" if device.type == "cuda" else "cpu",
            "default_root_dir": str(tmp_dir / "results"),
        }
        if device.type == "cuda":
            engine_kwargs["precision"] = "16-mixed"
            # 每 4 步更新一次权重，等效 batch_size=4，减少 optimizer CPU-GPU 同步开销
            engine_kwargs["accumulate_grad_batches"] = 4
        engine = Engine(**engine_kwargs)

        eval_batch_size = max(16, efficientad_cfg.batch_size)
        num_workers = 8
        datamodule_kwargs: dict = {
            "normal_dir": str(good_dir),
            "normal_test_dir": str(test_good_dir),
            "train_batch_size": train_batch_size,
            "eval_batch_size": eval_batch_size,
            "num_workers": num_workers,
        }
        datamodule_signature = inspect.signature(datamodule_cls)
        datamodule_parameters = datamodule_signature.parameters
        if "name" in datamodule_parameters:
            datamodule_kwargs["name"] = category
        if "root" in datamodule_parameters:
            datamodule_kwargs["root"] = None
        if "val_split_ratio" in datamodule_parameters:
            datamodule_kwargs["val_split_ratio"] = 0.5
        if "image_size" in datamodule_parameters:
            datamodule_kwargs["image_size"] = (
                efficientad_cfg.input_size,
                efficientad_cfg.input_size,
            )
        # GPU 训练时优化 DataLoader：pin_memory 加速 CPU→GPU 传输，persistent_workers 复用 worker 进程
        if "pin_memory" in datamodule_parameters:
            datamodule_kwargs["pin_memory"] = (device.type == "cuda")
        if "persistent_workers" in datamodule_parameters:
            datamodule_kwargs["persistent_workers"] = True
        datamodule = datamodule_cls(**datamodule_kwargs)

        engine.fit(model=model, datamodule=datamodule)
        model.to(device)
        torch_model = model.model.to(device).eval()

        # 计算最优阈值：在正常图像上推理，取分数的指定分位数作为阈值
        image_threshold = _compute_threshold(
            model=torch_model,
            image_paths=threshold_paths,
            device=device,
            input_size=efficientad_cfg.input_size,
            percentile=99.7,
        )

        # 导出 TorchScript（推理用）
        # 必须在 CPU 上 trace，否则图中会硬编码 cuda:0 导致 CPU-only 环境无法运行
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        model.eval()
        export_model = _EfficientADExportWrapper(torch_model).cpu().eval()
        example_input = torch.randn(
            1,
            3,
            efficientad_cfg.input_size,
            efficientad_cfg.input_size,
        )
        traced = torch.jit.trace(export_model, example_input)
        traced.save(str(output))

        # 保存原始 state_dict 供推理时多尺度特征提取
        state_dict_path = output.with_suffix(".state_dict.pt")
        torch.save(torch_model.state_dict(), str(state_dict_path))

        # 像素级阈值（取图像级阈值的 0.8 倍作为参考）
        pixel_threshold = round(image_threshold * 0.8, 6)

        train_time_s = round(time.monotonic() - t_start, 1)

        # 保存元数据
        meta = {
            "image_threshold": image_threshold,
            "pixel_threshold": pixel_threshold,
            "input_size": efficientad_cfg.input_size,
            "teacher_backbone": efficientad_cfg.teacher_backbone,
            "student_backbone": efficientad_cfg.student_backbone,
            "train_image_count": len(train_paths),
            "threshold_image_count": len(threshold_paths),
            "epochs": efficientad_cfg.epochs,
            "train_batch_size": train_batch_size,
            "eval_batch_size": eval_batch_size,
            "num_workers": num_workers,
            "train_time_s": train_time_s,
            "camera_id": camera_id,
        }
        meta_path = output.with_suffix(".meta.json")
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2))

        # 记录 MLflow
        if mlflow is not None:
            try:
                mlflow.log_params({
                    "camera_id": camera_id,
                    "teacher_backbone": efficientad_cfg.teacher_backbone,
                    "student_backbone": efficientad_cfg.student_backbone,
                    "input_size": efficientad_cfg.input_size,
                    "epochs": efficientad_cfg.epochs,
                    "configured_batch_size": efficientad_cfg.batch_size,
                    "train_batch_size": train_batch_size,
                    "eval_batch_size": eval_batch_size,
                    "num_workers": num_workers,
                    "learning_rate": efficientad_cfg.learning_rate,
                    "train_image_count": len(train_paths),
                    "threshold_image_count": len(threshold_paths),
                })
                mlflow.log_metrics({
                    "image_threshold": image_threshold,
                    "pixel_threshold": pixel_threshold,
                    "train_time_s": train_time_s,
                })
                mlflow.log_artifact(str(output))
                mlflow.log_artifact(str(meta_path))
                mlflow.log_artifact(str(state_dict_path))
                mlflow_run_id = mlflow.active_run().info.run_id
                mlflow.end_run()
            except Exception:
                pass  # MLflow 记录失败不阻塞训练流程

        return {
            "status": "completed",
            "artifact_path": str(output),
            "state_dict_path": str(state_dict_path),
            "image_threshold": image_threshold,
            "pixel_threshold": pixel_threshold,
            "train_image_count": len(train_paths),
            "train_time_s": train_time_s,
            "mlflow_run_id": mlflow_run_id,
        }
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _compute_threshold(
    model: object,
    image_paths: list[Path],
    device: torch.device,
    input_size: int,
    percentile: float = 99.7,
    batch_size: int = 32,
) -> float:
    """在正常图像上计算异常分数阈值（GPU 批量推理）。

    分批加载图像文件并送 GPU 并行推理，避免在内存中同时持有所有高分辨率原图。
    每批加载后立即 resize 并转为 tensor，释放原始 numpy 数组。

    Args:
        batch_size: GPU 推理 batch size，RTX 4060 8GB 推荐 32-64。
    """
    model.eval()
    all_scores: list[float] = []

    with torch.no_grad():
        for start in range(0, len(image_paths), batch_size):
            batch_paths = image_paths[start : start + batch_size]
            batch_tensors: list[torch.Tensor] = []
            for p in batch_paths:
                img = cv2.imread(str(p))
                if img is None:
                    batch_tensors.append(torch.zeros(3, input_size, input_size))
                    continue
                img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                del img  # 立即释放高分辨率原图，只保留 RGB
                img_resized = cv2.resize(img_rgb, (input_size, input_size))
                t = torch.from_numpy(img_resized).float().permute(2, 0, 1) / 255.0
                batch_tensors.append(t)

            batch = torch.stack(batch_tensors).to(device)
            output = model(batch)
            scores = _extract_pred_score(output)

            if isinstance(scores, torch.Tensor):
                all_scores.extend(scores.detach().cpu().tolist())
            elif isinstance(scores, (list, tuple)):
                all_scores.extend(float(s) for s in scores)
            else:
                all_scores.append(float(scores))

    if not all_scores:
        return 0.5

    threshold = float(np.percentile(all_scores, percentile))
    threshold = max(threshold, 1e-6)
    return round(threshold, 6)


def _extract_pred_score(output: object) -> torch.Tensor | float:
    """从 anomalib 1.x/2.x 输出中提取图像级异常分数。"""
    if hasattr(output, "pred_score"):
        return getattr(output, "pred_score")
    if isinstance(output, dict) and "pred_score" in output:
        return output["pred_score"]
    if isinstance(output, (tuple, list)):
        if len(output) >= 3 and torch.is_tensor(output[2]):
            return output[0]
        if len(output) >= 2:
            return output[1]
    if torch.is_tensor(output):
        return output.mean()
    raise RuntimeError(f"EfficientAD 输出格式不支持: {type(output)}")


def _init_mlflow(tracking_uri: Optional[str], experiment: str):
    """初始化 MLflow tracking。"""
    if tracking_uri is None:
        return None
    try:
        import mlflow

        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment(experiment)
        mlflow.start_run()
        return mlflow
    except Exception:
        return None


def train_efficientad_cli() -> None:
    """CLI 入口：由 seat_defect_core.__main__ 调用。"""
    import argparse

    parser = argparse.ArgumentParser(description="训练 EfficientAD 模型")
    parser.add_argument("--config", required=True, help="检测配置文件路径 (JSON/INI)")
    parser.add_argument("--camera-id", required=True, help="目标相机 ID")
    parser.add_argument("--good-images", required=True, help="正常参考图像目录")
    parser.add_argument("--output", required=True, help="输出 .pt 文件路径")
    parser.add_argument("--mlflow-uri", default=None, help="MLflow tracking URI")
    parser.add_argument("--mlflow-experiment", default="efficientad", help="MLflow 实验名称")

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
        mlflow_tracking_uri=args.mlflow_uri,
        mlflow_experiment=args.mlflow_experiment,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


def _find_camera(inspection_cfg, camera_id: str):
    """在配置中查找指定相机。"""
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


def _configure_gpu() -> None:
    """配置 GPU 性能选项：TF32 + cuDNN benchmark。

    TF32 (TensorFloat-32)：在 RTX 4060 (Ada Lovelace) 及 Ampere 以上架构上，
    将矩阵运算吞吐量提升约 2×，精度损失远低于 FP16。
    cuDNN benchmark：自动搜索最优卷积算法，减少 kernel launch 开销。
    """
    torch.backends.cudnn.benchmark = True
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True


def re_export_cpu(state_dict_path: str, output_path: str, *, input_size: int = 256) -> str:
    """将 CUDA traced 的 EfficientAD 模型重新导出为 CPU 兼容版本。

    从训练时保存的 state_dict 加载权重，在 CPU 上 trace 并保存。
    解决模型在 Windows+CUDA 上训练后无法在 Mac/Linux CPU 环境运行的问题。

    Args:
        state_dict_path: 训练时保存的 .state_dict.pt 文件路径
        output_path: 输出 TorchScript .pt 文件路径
        input_size: 模型输入尺寸（需与训练时一致）

    Returns:
        str: 输出文件路径
    """
    import torch as _torch

    from anomalib.models import EfficientAd as _EfficientAd

    state_dict = _torch.load(state_dict_path, map_location="cpu", weights_only=True)
    model = _EfficientAd(teacher_out_channels=384, model_size="medium")
    model.model.load_state_dict(state_dict)
    model.model.eval()

    export_model = _EfficientADExportWrapper(model.model).cpu().eval()
    example_input = _torch.randn(1, 3, input_size, input_size)
    traced = _torch.jit.trace(export_model, example_input)

    # 验证导出结果能在 CPU 上正常推理
    _ = traced(example_input)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    traced.save(str(out))
    return str(out)
