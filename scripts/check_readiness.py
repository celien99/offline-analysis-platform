#!/usr/bin/env python3
"""检测环境就绪检查：验证配置、模型文件和依赖的完整度。

用法：
  ./seat_defect_core/.venv/bin/python scripts/check_readiness.py
  ./seat_defect_core/.venv/bin/python scripts/check_readiness.py --config seat_defect_core/config.example.json
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

STATUS_OK = "  OK  "
STATUS_MISS = " MISS "
STATUS_WARN = " WARN "


def check_python() -> bool:
    import sys
    major, minor = sys.version_info[:2]
    ok = (major, minor) >= (3, 11)
    tag = STATUS_OK if ok else STATUS_WARN
    print(f" [{tag}] Python {major}.{minor} (需要 >=3.11)")
    return ok


def check_imports() -> dict[str, bool]:
    modules = {
        "cv2": "opencv-python",
        "numpy": "numpy",
        "torch": "torch",
        "torchvision": "torchvision",
        "ultralytics": "ultralytics",
        "requests": "requests",
    }
    results: dict[str, bool] = {}
    for mod, pkg in modules.items():
        try:
            __import__(mod)
            print(f" [{STATUS_OK}] {mod} ({pkg})")
            results[mod] = True
        except ImportError:
            print(f" [{STATUS_MISS}] {mod} ({pkg}) — 未安装")
            results[mod] = False
    return results


def check_torch_device() -> None:
    import torch
    cpu = True  # torch imported → CPU always available
    mps = torch.backends.mps.is_available() if hasattr(torch.backends, "mps") else False
    cuda = torch.cuda.is_available()
    print(f" [{STATUS_OK}] torch {torch.__version__} — CPU={cpu}, MPS={mps}, CUDA={cuda}")
    if mps:
        print(f"         MPS 可用 → config 中 device 设为 'mps' 可获得 GPU 加速")


def check_config(config_path: Path) -> dict[str, list[tuple[str, Path, bool]]] | None:
    try:
        from seat_defect_core.runtime_config import load_config
        cfg = load_config(str(config_path))
    except Exception as exc:
        print(f" [ FAIL ] 配置加载失败: {exc}")
        return None

    print(f" [{STATUS_OK}] 配置加载成功: {config_path}")
    print(f"         part_id={cfg.part_id}")
    print(f"         seat_models={len(cfg.seat_models)} 个, cameras={len(cfg.cameras)} 个")
    print(f"         fusion.ng_strategy={cfg.fusion.ng_strategy}")
    print(f"         upload_base_url={cfg.upload_base_url or '(未设置)'}")
    print(f"         debug_artifacts_enabled={cfg.debug_artifacts_enabled}")

    # 收集所有模型路径
    model_files: dict[str, list[tuple[str, Path, bool]]] = {"yolo": [], "patchcore": [], "filter_clf": []}

    all_cameras = list(cfg.cameras)
    for sm in cfg.seat_models:
        all_cameras.extend(sm.cameras)

    for cam in all_cameras:
        cam_label = f"{cam.camera_id}"
        # YOLO
        if cam.detection.model_path:
            p = Path(cam.detection.model_path)
            model_files["yolo"].append((cam_label, p, p.exists()))

        # PatchCore (whole ROI)
        p = Path(cam.patchcore_model_path)
        model_files["patchcore"].append((f"{cam_label} (整ROI)", p, p.exists()))

        # Region PatchCore
        for region in cam.regions:
            rp = Path(region.patchcore_model_path)
            model_files["patchcore"].append((f"{cam_label}/{region.region_id}", rp, rp.exists()))

        # Filter Classifier
        if cam.filter_classifier.enabled and cam.filter_classifier.model_path:
            cp = Path(cam.filter_classifier.model_path)
            if cp.is_dir():
                cp = cp / "model.pt"
            model_files["filter_clf"].append((cam_label, cp, cp.exists()))

    return model_files


def print_model_status(model_files: dict[str, list[tuple[str, Path, bool]]]) -> int:
    missing = 0
    for category, items in model_files.items():
        if not items:
            continue
        print(f"\n [{category.upper()} 模型]")
        for label, path, exists in items:
            tag = STATUS_OK if exists else STATUS_MISS
            print(f" [{tag}] {label}: {path}")
            if not exists:
                missing += 1
    return missing


def print_next_steps(missing_count: int) -> None:
    print("\n" + "=" * 60)
    if missing_count == 0:
        print("  所有模型文件已就绪，可以直接运行检测!")
        print()
        print("  运行命令:")
        print("    ./seat_defect_core/.venv/bin/python -m seat_defect_core \\")
        print("      --config seat_defect_core/config.example.json \\")
        print("      --images cam_front=sample.jpg cam_side=sample.jpg")
        return

    print(f"  缺少 {missing_count} 个模型文件，请按以下步骤补齐:")
    print()
    print("  1. YOLO 模型 (.pt)")
    print("     用 ultralytics 训练座椅分割模型，导出 best.pt")
    print("     放置: models/yolo/seat_model_a_best.pt")
    print()
    print("  2. PatchCore 模型 (.npz)")
    print("     运行 seat_defect_core 的 PatchCore 训练脚本")
    print("     或者从已部署产线拷贝 *.npz 文件")
    print("     放置: models/seat_model_a/cam_*_patchcore.npz")
    print()
    print("  3. Filter Classifier 模型 (.pt) [可选]")
    print("     将 filter_classifier.enabled 设为 false 可跳过")
    print("     或等待后端训练完成自动部署到 deployed_models/")
    print()
    print("  补充完成后再次运行本脚本验证。")


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="seat_defect_core 环境就绪检查")
    parser.add_argument("--config", type=str,
                        default=str(REPO_ROOT / "seat_defect_core" / "config.example.json"),
                        help="配置文件路径")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"配置文件不存在: {config_path}")
        return 1

    print("=" * 60)
    print("  seat_defect_core 环境就绪检查")
    print("=" * 60)

    # 1. Python 版本
    print("\n[1] Python 版本")
    check_python()

    # 2. 依赖
    print("\n[2] Python 依赖")
    import_results = check_imports()
    if not all(import_results.values()):
        print("\n  请运行: cd seat_defect_core && uv sync")

    # 3. 加速设备
    print("\n[3] 加速设备")
    if import_results.get("torch"):
        check_torch_device()

    # 4. 配置
    print("\n[4] 检测配置")
    model_files = check_config(config_path)
    if model_files is None:
        return 1

    # 5. 模型文件
    print("\n[5] 模型文件检查")
    missing = print_model_status(model_files)

    # 6. 下一步
    print_next_steps(missing)

    return 0 if missing == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
