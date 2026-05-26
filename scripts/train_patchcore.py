#!/usr/bin/env python3
"""PatchCore 模型独立训练脚本。

可在任意 Python 3.11+ 环境中运行，不依赖后端/前端服务。
只需将 seat_defect_core/ 目录复制到与本脚本同级即可使用。

用法:
  python train_patchcore.py \
    --config config.json \
    --camera-id cam_front \
    --good-images ./good_samples/ \
    --output ./models/cam_front_patchcore.npz

多机位批量训练:
  python train_patchcore.py \
    --config config.json \
    --camera-ids cam_front,cam_back \
    --good-images-root ./data/ \
    --output-dir ./models/
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 将本脚本所在目录作为项目根，确保能 import seat_defect_core
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))


def validate_args(args: argparse.Namespace) -> None:
    """校验命令行参数的正确性。"""
    # 单机位模式
    if args.camera_id:
        if not args.good_images:
            print("错误：--camera-id 模式必须指定 --good-images", file=sys.stderr)
            sys.exit(1)
        good_dir = Path(args.good_images)
        if not good_dir.is_dir():
            print(f"错误：正常样本目录不存在: {args.good_images}", file=sys.stderr)
            sys.exit(1)
        if not args.output:
            print("错误：--camera-id 模式必须指定 --output", file=sys.stderr)
            sys.exit(1)

    # 多机位批量模式
    if args.camera_ids:
        if not args.good_images_root:
            print("错误：--camera-ids 模式必须指定 --good-images-root", file=sys.stderr)
            sys.exit(1)
        root_dir = Path(args.good_images_root)
        if not root_dir.is_dir():
            print(f"错误：样本根目录不存在: {args.good_images_root}", file=sys.stderr)
            sys.exit(1)
        if not args.output_dir:
            print("错误：--camera-ids 模式必须指定 --output-dir", file=sys.stderr)
            sys.exit(1)


def scan_images(image_dir: Path) -> list[str]:
    """扫描目录中所有支持的图像文件。"""
    image_paths: list[str] = []
    for ext in ("*.jpg", "*.jpeg", "*.png", "*.bmp"):
        image_paths.extend(str(p) for p in image_dir.glob(ext))
    return sorted(image_paths)


def train_single(
    config_path: str,
    camera_id: str,
    good_image_dir: str,
    output_path: str,
) -> dict:
    """训练单个机位的 PatchCore 模型。"""
    from seat_defect_core.training.patchcore import train_patchcore

    img_dir = Path(good_image_dir)
    image_paths = scan_images(img_dir)
    if not image_paths:
        raise FileNotFoundError(f"目录中未找到图像文件 (.jpg/.jpeg/.png/.bmp): {good_image_dir}")

    print(f"\n{'='*60}")
    print(f"开始训练: camera_id={camera_id}")
    print(f"正常样本: {len(image_paths)} 张")
    print(f"样本目录: {good_image_dir}")
    print(f"输出路径: {output_path}")
    print(f"{'='*60}\n")

    result = train_patchcore(
        config=config_path,
        camera_id=camera_id,
        good_image_paths=image_paths,
        output_path=output_path,
    )
    return result


def train_batch(
    config_path: str,
    camera_ids: list[str],
    good_images_root: str,
    output_dir: str,
) -> list[dict]:
    """批量训练多个机位的 PatchCore 模型。

    样本目录结构要求:
      <good-images-root>/
        cam_front/   ← 机位 ID 对应的正常样本子目录
        cam_back/
        ...
    """
    root_dir = Path(good_images_root)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    failed: list[str] = []

    for cam_id in camera_ids:
        cam_sample_dir = root_dir / cam_id
        if not cam_sample_dir.is_dir():
            print(f"警告：跳过 {cam_id}，样本目录不存在: {cam_sample_dir}")
            failed.append(cam_id)
            continue

        output_path = str(out_dir / f"{cam_id}_patchcore.npz")
        try:
            result = train_single(config_path, cam_id, str(cam_sample_dir), output_path)
            results.append(result)
        except Exception as exc:
            print(f"错误：{cam_id} 训练失败: {exc}", file=sys.stderr)
            failed.append(cam_id)

    print(f"\n{'='*60}")
    print(f"批量训练完成")
    print(f"成功: {len(results)} 个模型")
    if failed:
        print(f"失败: {', '.join(failed)}")
    for r in results:
        print(f"  {r.get('artifact_path', '?')}  bank_size={r.get('memory_bank_size', '?')}  "
              f"threshold={r.get('threshold', 0):.4f}")
    print(f"{'='*60}\n")

    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="PatchCore 模型训练脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 单机位训练
  python train_patchcore.py \\
    --config config.json --camera-id cam_front \\
    --good-images ./data/cam_front/good/ --output ./models/cam_front.npz

  # 批量训练（样本按 cam_id 分目录）
  python train_patchcore.py \\
    --config config.json --camera-ids cam_front,cam_back \\
    --good-images-root ./data/ --output-dir ./models/
        """,
    )
    # 通用参数
    parser.add_argument("--config", type=str, required=True, help="检测配置文件路径 (JSON)")

    # 单机位模式
    parser.add_argument("--camera-id", type=str, default=None, help="目标相机 ID（单机位模式）")
    parser.add_argument("--good-images", type=str, default=None, help="正常参考图像目录（单机位模式）")
    parser.add_argument("--output", type=str, default=None, help="输出 .npz 文件路径（单机位模式）")

    # 多机位批量模式
    parser.add_argument(
        "--camera-ids",
        type=str,
        default=None,
        help="逗号分隔的相机 ID 列表（批量模式）",
    )
    parser.add_argument(
        "--good-images-root",
        type=str,
        default=None,
        help="样本根目录，每个机位一个子目录（批量模式）",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="模型输出目录（批量模式）",
    )

    args = parser.parse_args()

    # 确定运行模式
    is_single = bool(args.camera_id)
    is_batch = bool(args.camera_ids)

    if not is_single and not is_batch:
        parser.error("必须指定 --camera-id（单机位）或 --camera-ids（批量）")

    if is_single and is_batch:
        parser.error("--camera-id 和 --camera-ids 不能同时使用")

    validate_args(args)

    if is_single:
        result = train_single(args.config, args.camera_id, args.good_images, args.output)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        cam_ids = [cid.strip() for cid in args.camera_ids.split(",") if cid.strip()]
        train_batch(args.config, cam_ids, args.good_images_root, args.output_dir)


if __name__ == "__main__":
    main()
