"""EfficientAD 模型训练。

基于 anomalib 的 EfficientAD 实现，从正常参考图像训练异常检测模型。
训练完成后自动计算最优阈值并记录 MLflow 实验。
"""

from __future__ import annotations

import json
import inspect
import logging
import shutil
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Optional, Sequence, Type

import cv2
import numpy as np
import torch


_logger = logging.getLogger(__name__)


class _EfficientADExportWrapper(torch.nn.Module):
    """把 anomalib 模型包装为推理服务期望的输出格式。

    scoring 策略：
    - 默认使用 ST + STAE 混合（各 50%）。ST 擅长局部纹理异常，
      STAE 擅长全局外观异常。可通过 use_ae=False 降级为 ST-only，
      用于兼容旧版（随机 teacher）训练的模型。
    - 禁用 quantile normalization。
    - 使用 top-0.5% 均值评分。
    """

    def __init__(self, model: torch.nn.Module, use_ae: bool = True) -> None:
        super().__init__()
        self.model = model
        self.use_ae = use_ae
        self.register_buffer("mean", torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1))
        self.register_buffer("std", torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1))

    def forward(self, batch: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """返回 (anomaly_map, pred_score)。"""
        # 线上 EfficientADService 已做 ImageNet normalize，还原到 [0,1] 像素值
        batch = (batch * self.std + self.mean).clamp(0.0, 1.0)

        student_output, distance_st = self.model.compute_student_teacher_distance(batch)

        if self.use_ae:
            # ST + STAE 混合：同时覆盖纹理和外观异常
            map_st, map_stae = self.model.compute_maps(
                batch, student_output, distance_st, normalize=False,
            )
            anomaly_map = 0.5 * map_st + 0.5 * map_stae
        else:
            # ST-only：仅用 teacher-student distance（兼容旧模型）
            map_st = torch.mean(distance_st, dim=1, keepdim=True)
            image_size = batch.shape[-2:]
            if getattr(self.model, 'pad_maps', False):
                map_st = torch.nn.functional.pad(map_st, (4, 4, 4, 4))
            anomaly_map = torch.nn.functional.interpolate(
                map_st, size=image_size, mode="bilinear",
            )

        # top-0.5% 均值评分
        flat = anomaly_map.flatten(1)
        k = max(1, int(0.005 * flat.shape[1]))
        pred_score = flat.topk(k, dim=1).values.mean(dim=1)

        return anomaly_map, pred_score


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

    # MLflow 初始化
    mlflow_run_id: Optional[str] = None
    mlflow = _init_mlflow(mlflow_tracking_uri, mlflow_experiment)

    # 只收集文件路径，不在内存中累积高分辨率 numpy 数组，避免 cv::OutOfMemoryError
    source_image_paths: list[Path] = [Path(p) for p in good_image_paths if Path(p).exists()]
    if len(source_image_paths) < 2:
        raise RuntimeError(f"正常参考图像不足 ({len(source_image_paths)} 张)，至少需要 2 张")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    prepared_root = output.parent / f"{output.stem}_prepared_roi"
    tmp_dir = Path(tempfile.mkdtemp(prefix="efficientad_train_"))
    t_start = time.monotonic()
    try:
        prepared = _prepare_training_images(
            camera_config,
            source_image_paths,
            prepared_root,
            reset_output=True,
        )
        image_paths = prepared["image_paths"]
        target_mask_paths = prepared["target_mask_paths"]
        ignore_mask_paths = prepared["ignore_mask_paths"]
        if len(image_paths) < 2:
            reason_summary = ", ".join(
                f"{reason}={count}" for reason, count in sorted(prepared["rejections"].items())
            ) or "none"
            raise RuntimeError(
                f"YOLO+ROI 制备后的正常参考图像不足 ({len(image_paths)} 张)，"
                f"至少需要 2 张；跳过原因: {reason_summary}"
            )

        # anomalib MVTec 格式: {category}/train/good/ + {category}/test/good/ (用于阈值计算)
        category = camera_id.replace(" ", "_")
        good_dir = tmp_dir / category / "train" / "good"
        good_dir.mkdir(parents=True, exist_ok=True)

        # 固定 seed 打乱后划分，避免按时间/批次排序导致阈值集偏置。
        order = np.random.default_rng(42).permutation(len(image_paths)).tolist()
        image_paths = [image_paths[i] for i in order]
        target_mask_paths = [target_mask_paths[i] for i in order]
        ignore_mask_paths = [ignore_mask_paths[i] for i in order]

        split_idx = max(1, int(len(image_paths) * (1.0 - efficientad_cfg.validation_split)))
        train_paths = image_paths[:split_idx]
        threshold_paths = image_paths[split_idx:] if split_idx < len(image_paths) else image_paths[:1]
        threshold_target_mask_paths = (
            target_mask_paths[split_idx:] if split_idx < len(target_mask_paths) else target_mask_paths[:1]
        )
        threshold_ignore_mask_paths = (
            ignore_mask_paths[split_idx:] if split_idx < len(ignore_mask_paths) else ignore_mask_paths[:1]
        )

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

        # 加载预训练 teacher 权重（anomalib 的 prepare_pretrained_model
        # 会在 on_train_start 中由 Lightning 自动调用，但显式调用可确保
        # 在训练前完成下载/加载，并在失败时给出明确错误信息而非静默跳过）
        try:
            model.prepare_pretrained_model()
        except Exception as exc:
            _logger.error(
                "efficientad_pretrained_teacher_download_failed",
                exc_info=True,
                hint="检查网络连接或手动下载 anomalib 预训练权重到缓存目录",
            )
            raise RuntimeError(
                "EfficientAD 预训练 teacher 权重下载失败。"
                "请确保网络可访问 GitHub，或手动下载权重后放置到 anomalib 缓存目录。"
            ) from exc

        # 校验 teacher 权重已加载（未加载时 Conv2d 权重 std 约 0.02-0.09，
        # 预训练权重 std 差异显著更小或更大，通过极端值判断）
        teacher_std = float(
            model.model.teacher.conv1.weight.std().item()
        )
        if teacher_std < 0.01:
            raise RuntimeError(
                f"EfficientAD teacher 权重 std={teacher_std:.6f}，"
                f"预训练权重可能未正确加载。请检查 anomalib 缓存目录。"
            )
        _logger.info(
            "efficientad_teacher_verified",
            teacher_std=round(teacher_std, 6),
        )

        # 训练
        # EfficientAD 架构要求 train_batch_size=1，这是模型设计的硬约束
        # （teacher-student 知识蒸馏 + 特征统计依赖 per-image 处理）
        # 通过 gradient_accumulation 增大有效 batch size，减少 optimizer step 开销
        train_batch_size = 1
        accelerator = "gpu" if device.type == "cuda" else ("mps" if device.type == "mps" else "cpu")
        engine_kwargs: dict = {
            "max_epochs": efficientad_cfg.epochs,
            "devices": 1,
            "accelerator": accelerator,
            "default_root_dir": str(tmp_dir / "results"),
        }
        if device.type == "cuda":
            engine_kwargs["precision"] = "16-mixed"
            # 每 4 步更新一次权重，等效 batch_size=4，减少 optimizer CPU-GPU 同步开销
            engine_kwargs["accumulate_grad_batches"] = 4
        try:
            engine = Engine(**engine_kwargs)
        except (ValueError, RuntimeError) as exc:
            if accelerator == "mps":
                _logger.warning(
                    "mps_accelerator_unsupported falling back to CPU: %s", exc
                )
                engine_kwargs["accelerator"] = "cpu"
                engine = Engine(**engine_kwargs)
            else:
                raise

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

        # 保存 state_dict（在任何设备迁移之前保存训练后的权重）
        state_dict_path = output.with_suffix(".state_dict.pt")
        torch.save(torch_model.state_dict(), str(state_dict_path))

        # 创建推理 wrapper 并移到 CPU（确保阈值计算和 trace 都在 CPU 上，
        # 避免 CUDA 设备常量泄漏到 TorchScript 图，同时保证跨平台阈值一致性）
        model.eval()
        export_model = _EfficientADExportWrapper(torch_model, use_ae=True).cpu().eval()

        # 计算最优阈值：使用与线上推理完全一致的 wrapper + scoring 方法，
        # 在 CPU 上计算，确保训练环境 (CUDA) 和部署环境 (CPU/Mac) 阈值一致
        thresholds = _compute_thresholds(
            model=export_model,
            image_paths=threshold_paths,
            device=torch.device("cpu"),
            input_size=efficientad_cfg.input_size,
            image_percentile=efficientad_cfg.image_threshold_percentile,
            pixel_percentile=efficientad_cfg.pixel_threshold_percentile,
            score_topk_ratio=efficientad_cfg.score_topk_ratio,
            target_mask_paths=threshold_target_mask_paths,
            ignore_mask_paths=threshold_ignore_mask_paths,
        )
        image_threshold = thresholds["image_threshold"]
        pixel_threshold = thresholds["pixel_threshold"]

        # 导出 TorchScript（CPU trace，确保跨平台兼容）
        example_input = torch.randn(
            1,
            3,
            efficientad_cfg.input_size,
            efficientad_cfg.input_size,
        )
        traced = torch.jit.trace(export_model, example_input)
        traced.save(str(output))

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
            "source_image_count": len(source_image_paths),
            "prepared_image_count": len(image_paths),
            "prepared_image_dir": str(prepared_root),
            "prepare_rejections": dict(prepared["rejections"]),
            "epochs": efficientad_cfg.epochs,
            "train_batch_size": train_batch_size,
            "eval_batch_size": eval_batch_size,
            "num_workers": num_workers,
            "train_time_s": train_time_s,
            "camera_id": camera_id,
            "image_threshold_percentile": efficientad_cfg.image_threshold_percentile,
            "pixel_threshold_percentile": efficientad_cfg.pixel_threshold_percentile,
            "score_topk_ratio": efficientad_cfg.score_topk_ratio,
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
            "prepared_image_dir": str(prepared_root),
            "source_image_count": len(source_image_paths),
            "prepared_image_count": len(image_paths),
            "prepare_rejections": dict(prepared["rejections"]),
            "mlflow_run_id": mlflow_run_id,
        }
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _prepare_training_images(
    camera_config,
    source_image_paths: Sequence[Path],
    output_dir: Path,
    *,
    reset_output: bool = False,
    pipeline_cls=None,
) -> dict:
    """Run the online YOLO+ROI prepare path and persist EfficientAD training inputs.

    The saved image is exactly the online texture input (`aligned_roi_image`) that
    `select_texture_input(prepared.roi)` returns during inspection. Masks are kept
    beside it so threshold calibration can use the same target/ignore semantics as
    online scoring.
    """
    from ..util import select_texture_input, write_image

    if pipeline_cls is None:
        from ..service.core import CameraPipeline

        pipeline_cls = CameraPipeline

    if reset_output and output_dir.exists():
        import shutil as _shutil

        _shutil.rmtree(output_dir)
    image_dir = output_dir / "images"
    target_dir = output_dir / "target_masks"
    ignore_dir = output_dir / "ignore_masks"
    image_dir.mkdir(parents=True, exist_ok=True)
    target_dir.mkdir(parents=True, exist_ok=True)
    ignore_dir.mkdir(parents=True, exist_ok=True)

    pipeline = pipeline_cls(camera_config)
    prepared_image_paths: list[Path] = []
    target_mask_paths: list[Path] = []
    ignore_mask_paths: list[Path] = []
    rejections: Counter[str] = Counter()

    for index, source_path in enumerate(source_image_paths):
        try:
            image = cv2.imread(str(source_path))
            if image is None:
                rejections["image_decode_failed"] += 1
                continue
            prepared = pipeline.prepare_image(image)
            if prepared.roi is None:
                rejections[prepared.rejection_reason or "roi_missing"] += 1
                continue
            texture_input = select_texture_input(prepared.roi)
            stem = f"{index:06d}_{source_path.stem}"
            image_path = image_dir / f"{stem}.png"
            target_path = target_dir / f"{stem}.png"
            ignore_path = ignore_dir / f"{stem}.png"

            write_image(image_path, texture_input)
            write_image(target_path, (prepared.roi.target_mask > 0).astype(np.uint8) * 255)
            write_image(ignore_path, (prepared.roi.ignore_mask > 0).astype(np.uint8) * 255)
            prepared_image_paths.append(image_path)
            target_mask_paths.append(target_path)
            ignore_mask_paths.append(ignore_path)
            if prepared.rejection_reason is not None:
                rejections[prepared.rejection_reason] += 1
        except Exception:
            rejections["prepare_exception"] += 1
            _logger.warning(
                "prepare_training_image_failed index=%d path=%s",
                index, str(source_path), exc_info=True,
            )

    manifest = {
        "camera_id": camera_config.camera_id,
        "source_image_count": len(source_image_paths),
        "prepared_image_count": len(prepared_image_paths),
        "rejections": dict(rejections),
        "images": [str(path) for path in prepared_image_paths],
        "target_masks": [str(path) for path in target_mask_paths],
        "ignore_masks": [str(path) for path in ignore_mask_paths],
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "image_paths": prepared_image_paths,
        "target_mask_paths": target_mask_paths,
        "ignore_mask_paths": ignore_mask_paths,
        "rejections": rejections,
    }


def _compute_threshold(
    model: object,
    image_paths: list[Path],
    device: torch.device,
    input_size: int,
    percentile: float = 99.0,
    batch_size: int = 32,
) -> float:
    """Backward-compatible image-threshold helper."""
    thresholds = _compute_thresholds(
        model=model,
        image_paths=image_paths,
        device=device,
        input_size=input_size,
        image_percentile=percentile,
        batch_size=batch_size,
    )
    return thresholds["image_threshold"]


def _compute_thresholds(
    model: object,
    image_paths: list[Path],
    device: torch.device,
    input_size: int,
    *,
    image_percentile: float = 99.0,
    pixel_percentile: float = 99.9,
    score_topk_ratio: float = 0.005,
    batch_size: int = 32,
    target_mask_paths: Optional[list[Path]] = None,
    ignore_mask_paths: Optional[list[Path]] = None,
) -> dict[str, float]:
    """在正常图像上同时计算图像级和像素级阈值。

    图像级分数与线上高召回判定一致：取 wrapper pred_score 与 anomaly_map
    top-k 均值的较大值。像素级阈值来自正常验证集 anomaly_map 像素分布，
    用于线上强热点兜底。
    """
    from ..efficientad.engine import _prepare_input, _resize_anomaly_map, _to_binary_mask, _topk_mean_flat

    model.eval()
    image_scores: list[float] = []
    pixel_scores: list[np.ndarray] = []

    with torch.no_grad():
        for start in range(0, len(image_paths), batch_size):
            batch_paths = image_paths[start : start + batch_size]
            batch_target_masks = (
                target_mask_paths[start : start + batch_size]
                if target_mask_paths is not None
                else [None] * len(batch_paths)
            )
            batch_ignore_masks = (
                ignore_mask_paths[start : start + batch_size]
                if ignore_mask_paths is not None
                else [None] * len(batch_paths)
            )
            batch_tensors: list[torch.Tensor] = []
            batch_masks: list[np.ndarray | None] = []
            for p, target_path, ignore_path in zip(batch_paths, batch_target_masks, batch_ignore_masks):
                img = cv2.imread(str(p))
                if img is None:
                    continue
                t = _prepare_input(img, input_size).squeeze(0)
                batch_tensors.append(t)
                if target_path is None:
                    batch_masks.append(None)
                    continue
                target = cv2.imread(str(target_path), cv2.IMREAD_GRAYSCALE)
                if target is None:
                    batch_masks.append(None)
                    continue
                ignore = (
                    cv2.imread(str(ignore_path), cv2.IMREAD_GRAYSCALE)
                    if ignore_path is not None
                    else None
                )
                target_binary = _to_binary_mask(target, (input_size, input_size))
                if ignore is not None:
                    ignore_binary = _to_binary_mask(ignore, (input_size, input_size))
                    target_binary[ignore_binary > 0] = 0
                batch_masks.append(target_binary)

            if not batch_tensors:
                continue

            batch = torch.stack(batch_tensors).to(device)
            output = model(batch)
            if not isinstance(output, (tuple, list)) or len(output) < 2:
                pred_score = _extract_pred_score(output)
                if isinstance(pred_score, torch.Tensor):
                    image_scores.extend(pred_score.detach().cpu().flatten().tolist())
                else:
                    image_scores.append(float(pred_score))
                continue

            anomaly_map, pred_score = output[0], output[1]
            maps_np = anomaly_map.detach().cpu().float().numpy()
            if maps_np.ndim == 4:
                maps_np = maps_np[:, 0]
            pred_scores = pred_score.detach().cpu().flatten().tolist()
            for i, amap in enumerate(maps_np):
                if amap.shape != (input_size, input_size):
                    amap = _resize_anomaly_map(
                        torch.from_numpy(amap).unsqueeze(0).unsqueeze(0),
                        input_size,
                        input_size,
                    )
                mask = batch_masks[i] if i < len(batch_masks) else None
                if mask is not None and int(mask.sum()) > 0:
                    flat = amap[mask > 0].reshape(-1).astype(np.float32)
                else:
                    flat = amap.reshape(-1).astype(np.float32)
                if flat.size == 0:
                    continue
                topk = _topk_mean_flat(flat, score_topk_ratio)
                base_score = pred_scores[i] if i < len(pred_scores) else float(flat.mean())
                image_scores.append(max(float(base_score), topk))
                pixel_scores.append(flat)

    if not image_scores:
        return {
            "image_threshold": 0.5,
            "pixel_threshold": 0.4,
        }

    image_threshold = float(np.percentile(image_scores, image_percentile))
    if pixel_scores:
        all_pixels = np.concatenate(pixel_scores)
        pixel_threshold = float(np.percentile(all_pixels, pixel_percentile))
    else:
        pixel_threshold = image_threshold * 0.8

    return {
        "image_threshold": round(max(image_threshold, 1e-6), 6),
        "pixel_threshold": round(max(pixel_threshold, 1e-6), 6),
    }



def _extract_pred_score(output: object) -> torch.Tensor | float:
    """从模型输出中提取图像级异常分数。

    兼容两种格式：
    - _EfficientADExportWrapper：tuple (anomaly_map, pred_score)
    - anomalib EfficientAdModel：InferenceBatch 含 .pred_score 属性
    """
    if isinstance(output, (tuple, list)) and len(output) >= 2:
        # wrapper 输出 (anomaly_map, pred_score)
        return output[1]
    if hasattr(output, "pred_score"):
        return getattr(output, "pred_score")
    if isinstance(output, dict) and "pred_score" in output:
        return output["pred_score"]
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
    parser.add_argument("--good-images", required=True, help="正常原图目录（训练前自动执行 YOLO+ROI 制备）")
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


def re_export_cpu(
    state_dict_path: str,
    output_path: str,
    *,
    input_size: int = 256,
    image_threshold: float | None = None,
    use_ae: bool = True,
) -> str:
    """将 CUDA traced 的 EfficientAD 模型重新导出为 CPU 兼容版本。

    从训练时保存的 state_dict 加载权重，在 CPU 上 trace 并保存。
    如果提供 image_threshold，会同时更新 meta.json。

    Args:
        state_dict_path: 训练时保存的 .state_dict.pt 文件路径
        output_path: 输出 TorchScript .pt 文件路径
        input_size: 模型输入尺寸（需与训练时一致）
        image_threshold: 异常分数阈值。为 None 则保留 meta.json 中的旧值。
            注意：新 scoring 管线的阈值与旧管线不兼容，建议重新计算。
        use_ae: 启用 ST+STAE 混合评分。旧训练模型（无 AE）应设为 False。

    Returns:
        str: 输出文件路径
    """
    import torch as _torch

    from anomalib.models import EfficientAd as _EfficientAd

    state_dict = _torch.load(state_dict_path, map_location="cpu", weights_only=True)
    model = _EfficientAd(teacher_out_channels=384, model_size="medium")
    model.model.load_state_dict(state_dict)
    model.model.eval()

    export_model = _EfficientADExportWrapper(model.model, use_ae=use_ae).cpu().eval()
    example_input = _torch.randn(1, 3, input_size, input_size)
    traced = _torch.jit.trace(export_model, example_input)

    # 验证导出结果能在 CPU 上正常推理
    _ = traced(example_input)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    traced.save(str(out))

    # 更新 meta.json 中的阈值
    if image_threshold is not None:
        meta_path = out.with_suffix(".meta.json")
        if meta_path.exists():
            meta = json.loads(meta_path.read_text("utf-8"))
        else:
            meta = {}
        meta["image_threshold"] = round(image_threshold, 6)
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2))

    return str(out)


def recompute_threshold(
    state_dict_path: str,
    image_dir: str,
    *,
    input_size: int = 256,
    percentile: float = 99.0,
    pixel_percentile: float = 99.9,
    score_topk_ratio: float = 0.005,
    batch_size: int = 32,
    device: str = "cpu",
    use_ae: bool = True,
) -> dict:
    """从 state_dict 重建模型，在给定正常图像上重新计算异常分数阈值。

    用于以下场景：
    - 训练时 _prepare_input 使用了旧版 gray canvas letterbox，
      需要在新版 reflection padding 上重算阈值。
    - 阈值与推理环境不一致时需要重新校准。

    Args:
        state_dict_path: 训练时保存的 .state_dict.pt 文件路径。
        image_dir: 正常参考图像目录（支持 jpg/png/bmp）。
        input_size: 模型输入尺寸，需与训练时一致。
        percentile: 阈值百分位数，默认 99.0。
        pixel_percentile: 像素级阈值百分位数，默认 99.9。
        score_topk_ratio: top-k 兜底评分比例，默认 0.005。
        batch_size: 批量推理大小。
        device: 推理设备 (cpu/cuda/mps)。
        use_ae: 启用 ST+STAE 混合评分。旧训练模型（无 AE）应设为 False。

    Returns:
        dict: {image_threshold, pixel_threshold, image_count, scores_percentiles}
    """
    import torch as _torch
    from pathlib import Path as _Path

    _device = _torch.device(device)
    if _device.type == "cuda" and not _torch.cuda.is_available():
        _device = _torch.device("cpu")
    if _device.type == "mps" and not _torch.backends.mps.is_available():
        _device = _torch.device("cpu")

    from anomalib.models import EfficientAd as _EfficientAd

    state_dict = _torch.load(state_dict_path, map_location="cpu", weights_only=True)
    model = _EfficientAd(teacher_out_channels=384, model_size="medium")
    model.model.load_state_dict(state_dict)
    model.model.eval()

    export_model = _EfficientADExportWrapper(model.model, use_ae=use_ae).to(_device).eval()

    image_dir_path = _Path(image_dir)
    image_paths: list[_Path] = []
    for ext in ("*.jpg", "*.jpeg", "*.png", "*.bmp"):
        image_paths.extend(sorted(image_dir_path.glob(ext)))
    if not image_paths:
        raise FileNotFoundError(f"{image_dir} 中未找到图像文件")

    thresholds = _compute_thresholds(
        model=export_model,
        image_paths=image_paths,
        device=_device,
        input_size=input_size,
        image_percentile=percentile,
        pixel_percentile=pixel_percentile,
        score_topk_ratio=score_topk_ratio,
        batch_size=batch_size,
    )

    return {
        "image_threshold": thresholds["image_threshold"],
        "pixel_threshold": thresholds["pixel_threshold"],
        "image_count": len(image_paths),
    }
