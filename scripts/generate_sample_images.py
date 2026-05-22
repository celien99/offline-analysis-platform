#!/usr/bin/env python3
"""生成合成测试图片，用于 seat_defect_core 端到端 Demo。

生成图片包含：
  - 灰色背景模拟座椅表面
  - 随机纹理噪声
  - 随机暗色斑点（模拟缺陷）
  - 随机划痕线条

用法：
  python scripts/generate_sample_images.py
  python scripts/generate_sample_images.py --output ./sample_images --count 4
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np


def generate_normal_image(size: tuple[int, int] = (480, 640), rng: np.random.Generator | None = None) -> np.ndarray:
    """生成正常座椅表面图像（灰色背景 + 纹理噪声）。"""
    if rng is None:
        rng = np.random.default_rng()
    img = np.ones((*size, 3), dtype=np.uint8) * 128
    noise = rng.integers(0, 30, img.shape, dtype=np.uint8)
    img = np.clip(img.astype(int) + noise.astype(int) - 15, 0, 255).astype(np.uint8)
    return img


def add_defect(img: np.ndarray, rng: np.random.Generator | None = None) -> np.ndarray:
    """在图像上添加随机缺陷（斑点或划痕）。"""
    if rng is None:
        rng = np.random.default_rng()
    height, width = img.shape[:2]

    # 随机斑点
    for _ in range(rng.integers(1, 5)):
        x = int(rng.integers(100, width - 100))
        y = int(rng.integers(80, height - 80))
        radius = int(rng.integers(15, 50))
        color = int(rng.integers(20, 100))
        cv2.circle(img, (x, y), radius, (color, color, color), -1)

    # 随机划痕
    if rng.random() > 0.3:
        x1 = int(rng.integers(50, width // 2))
        y1 = int(rng.integers(50, height - 50))
        x2 = int(rng.integers(width // 2, width - 50))
        y2 = int(rng.integers(50, height - 50))
        cv2.line(img, (x1, y1), (x2, y2), (50, 50, 50), int(rng.integers(1, 4)))

    return img


def main() -> int:
    parser = argparse.ArgumentParser(description="生成合成测试图片")
    parser.add_argument("--output", type=str, default="./sample_images",
                        help="输出目录")
    parser.add_argument("--count", type=int, default=4,
                        help="生成图片数量")
    parser.add_argument("--defect-ratio", type=float, default=0.5,
                        help="包含缺陷的图片比例 (0.0-1.0)")
    parser.add_argument("--seed", type=int, default=42,
                        help="随机种子")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(args.seed)

    defect_count = max(0, min(args.count, int(args.count * args.defect_ratio)))
    normal_count = args.count - defect_count

    print(f"生成 {args.count} 张测试图片 → {output_dir}")
    print(f"  正常图片: {normal_count} 张")
    print(f"  缺陷图片: {defect_count} 张")

    for i in range(normal_count):
        img = generate_normal_image(rng=rng)
        path = output_dir / f"normal_{i + 1:02d}.jpg"
        cv2.imwrite(str(path), img)
        print(f"  [正常] {path}")

    for i in range(defect_count):
        img = generate_normal_image(rng=rng)
        img = add_defect(img, rng=rng)
        path = output_dir / f"defect_{i + 1:02d}.jpg"
        cv2.imwrite(str(path), img)
        print(f"  [缺陷] {path}")

    print(f"\n完成！共生成 {args.count} 张图片")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
