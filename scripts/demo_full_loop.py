#!/usr/bin/env python3
"""端到端 Demo：验证 seat_defect_core → 离线平台 完整数据闭环。

前提条件：
  1. 后端 Docker 服务已启动：cd backend && docker compose up -d
  2. seat_defect_core 已安装：cd seat_defect_core && uv sync

用法：
  python scripts/demo_full_loop.py
  python scripts/demo_full_loop.py --backend http://localhost:8000 --images ./sample_images
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from time import sleep

REPO_ROOT = Path(__file__).resolve().parent.parent


def check_backend_health(base_url: str, timeout: float = 5.0) -> bool:
    """检查后端服务是否可达。"""
    try:
        import urllib.request
        url = f"{base_url.rstrip('/')}/health"
        req = urllib.request.Request(url)
        resp = urllib.request.urlopen(req, timeout=timeout)
        data = json.loads(resp.read())
        return data.get("status") == "healthy"
    except Exception:
        return False


def check_deploy_targets(base_url: str) -> list[dict]:
    """查询离线平台配置的部署目标。"""
    import requests
    try:
        resp = requests.get(f"{base_url.rstrip('/')}/api/model/deploy-targets", timeout=5)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        print(f"  [警告] 无法查询部署目标：{exc}")
        return []


def discover_images(image_dir: Path) -> dict[str, Path]:
    """从目录中发现测试图片，按文件名映射 camera_id。

    文件名格式: {camera_id}.jpg 或 {camera_id}.png
    例如: cam_front.jpg → camera_id="cam_front"
    """
    image_paths: dict[str, Path] = {}
    for ext in ("*.jpg", "*.jpeg", "*.png"):
        for f in image_dir.glob(ext):
            camera_id = f.stem  # 文件名（不含扩展名）作为 camera_id
            image_paths[camera_id] = f
    return image_paths


def run_inspection(
    config_path: Path,
    image_paths: dict[str, Path],
    part_id: str | None = None,
    seat_model_id: str | None = None,
) -> tuple[object, dict]:
    """运行 seat_defect_core 检测。"""
    sys.path.insert(0, str(REPO_ROOT))
    from seat_defect_core.api import SeatDefectInspector

    inspector = SeatDefectInspector(str(config_path))
    print("  [检测] 预热模型...")
    inspector.warmup(seat_model_id=seat_model_id)
    print("  [检测] 执行检测...")
    response, camera_images = inspector.inspect_paths(
        {cid: str(p) for cid, p in image_paths.items()},
        part_id=part_id,
        seat_model_id=seat_model_id,
    )
    return response, camera_images


def upload_results(response, base_url: str) -> list[dict]:
    """将 NG 检测结果上传到离线平台。"""
    sys.path.insert(0, str(REPO_ROOT))
    from seat_defect_core.anomaly_uploader import upload_inspection_response

    print(f"  [上传] 目标: {base_url}")
    results = upload_inspection_response(response, base_url)
    if results:
        print(f"  [上传] 成功上传 {len(results)} 条异常记录")
        for r in results:
            print(f"    anomaly_id={r.get('anomaly_id', '?')}  status={r.get('status', '?')}")
    else:
        if response.status == "NG":
            print("  [上传] 警告：检测为 NG 但上传失败（后端可能未运行或网络不通）")
        else:
            print(f"  [上传] 检测状态为 {response.status}，无需上传")
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="seat_defect_core ↔ 离线平台 端到端 Demo")
    parser.add_argument("--backend", type=str, default="http://localhost:8000",
                        help="离线平台后端地址")
    parser.add_argument("--images", type=str, default=None,
                        help="测试图片目录（必填，包含 {camera_id}.jpg 格式图片）")
    parser.add_argument("--config", type=str, default=None,
                        help="seat_defect_core 配置 JSON 路径（不存在则使用内置最小配置）")
    parser.add_argument("--no-upload", action="store_true",
                        help="不上传到后端，仅执行检测")
    args = parser.parse_args()

    print("=" * 60)
    print("  seat_defect_core ↔ 离线分析平台 端到端 Demo")
    print("=" * 60)

    # Step 1: 检查后端
    print("\n[1/5] 检查后端服务...")
    if check_backend_health(args.backend):
        print(f"  后端健康检查通过: {args.backend}")
        targets = check_deploy_targets(args.backend)
        if targets:
            print(f"  部署目标: {json.dumps(targets, ensure_ascii=False)}")
    else:
        print(f"  [警告] 后端不可达: {args.backend}")
        print("  请先启动后端: cd backend && docker compose up -d")
        if not args.no_upload:
            print("  使用 --no-upload 可以在无后端时仅执行检测")
            return 1

    # Step 2: 准备图片
    print("\n[2/5] 准备测试图片...")
    image_dir = Path(args.images) if args.images else REPO_ROOT / "sample_images"
    if not image_dir.exists() or not any(image_dir.iterdir()):
        print(f"  [错误] 图片目录不存在或为空: {image_dir}")
        print(f"  请将测试图片放入该目录，文件名格式: {{camera_id}}.jpg")
        print(f"  例如: cam_front.jpg, cam_side.jpg")
        return 1
    image_paths = discover_images(image_dir)
    if not image_paths:
        print(f"  [错误] 未在 {image_dir} 中找到图片（.jpg/.png）")
        return 1
    print(f"  从 {image_dir} 读取 {len(image_paths)} 张图片")
    for cam_id, path in image_paths.items():
        print(f"    {cam_id} ← {path.name}")

    # Step 3: 准备配置
    print("\n[3/5] 准备检测配置...")
    if args.config:
        config_path = Path(args.config)
    else:
        config_path = REPO_ROOT / "seat_defect_core" / "config.example.json"
    if not config_path.exists():
        print(f"  [错误] 配置文件不存在: {config_path}")
        return 1
    print(f"  配置: {config_path}")

    # Step 4: 运行检测
    print("\n[4/5] 运行检测...")
    try:
        response, camera_images = run_inspection(
            config_path,
            image_paths,
            part_id="demo_part_001",
        )
        print(f"  结果: status={response.status}  reason={response.decision_reason}")
        for cam_result in response.result.camera_results:
            print(f"    [{cam_result.camera_id}] status={cam_result.status}  reason={cam_result.reason}")
            if cam_result.filter_result:
                print(f"       filter: is_real_defect={cam_result.filter_result.is_real_defect}  "
                      f"confidence={cam_result.filter_result.confidence:.3f}")
    except Exception as exc:
        print(f"  [错误] 检测失败: {exc}")
        print("  [提示] 可能需要先训练 PatchCore 模型放到 models/ 目录下")
        print("  当前 demo 假设 models/ 中已有训练的 PatchCore/YOLO 模型")
        return 1

    # Step 5: 上传
    if not args.no_upload and response.status == "NG":
        print("\n[5/5] 上传异常到离线平台...")
        upload_results(response, args.backend)
    else:
        print(f"\n[5/5] 跳过上传 (status={response.status}, no_upload={args.no_upload})")

    print("\n" + "=" * 60)
    print("  Demo 完成")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
