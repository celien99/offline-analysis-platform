"""CLI entry point for seat_defect_core: python -m seat_defect_core [options].

Usage examples:
  python -m seat_defect_core --config inspection_config.json
  python -m seat_defect_core --config config.json --images cam1=img1.jpg cam2=img2.jpg
  python -m seat_defect_core --config config.json --upload http://localhost:8000
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="seat_defect_core",
        description="Online real-time seat defect inspection core",
    )
    parser.add_argument(
        "--config",
        type=str,
        required=True,
        help="JSON or INI inspection config file path",
    )
    parser.add_argument(
        "--images",
        type=str,
        nargs="*",
        default=[],
        help="Camera image paths as CAMERA_ID=PATH pairs",
    )
    parser.add_argument(
        "--part-id",
        type=str,
        default=None,
        help="Part identifier for this inspection",
    )
    parser.add_argument(
        "--seat-model-id",
        type=str,
        default=None,
        help="Seat model identifier override",
    )
    parser.add_argument(
        "--upload",
        type=str,
        default=None,
        help="Override upload_base_url in config",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Write inspection response JSON to file",
    )
    parser.add_argument(
        "--warmup",
        action="store_true",
        default=False,
        help="Preload models before inspection",
    )

    args = parser.parse_args(argv)

    # 解析图片映射
    image_paths: Dict[str, str] = {}
    for pair in args.images:
        if "=" not in pair:
            print(f"错误：--images 格式应为 CAMERA_ID=PATH，收到：{pair}", file=sys.stderr)
            return 1
        camera_id, path = pair.split("=", 1)
        image_paths[camera_id.strip()] = path.strip()

    try:
        from seat_defect_core.api import SeatDefectInspector

        inspector = SeatDefectInspector(args.config)

        if args.upload:
            inspector.config.upload_base_url = args.upload

        if args.warmup:
            print("预热模型中...")
            inspector.warmup(seat_model_id=args.seat_model_id)
            print("预热完成")

        if image_paths:
            response, camera_images = inspector.inspect_paths(
                image_paths,
                part_id=args.part_id,
                seat_model_id=args.seat_model_id,
            )
        else:
            print("错误：请通过 --images 指定至少一个机位图片", file=sys.stderr)
            return 1

        # 输出结果
        payload = response.to_dict()
        print(json.dumps({"status": response.status, "decision_reason": response.decision_reason}, ensure_ascii=False))
        for cam_result in response.result.camera_results:
            print(f"  [{cam_result.camera_id}] status={cam_result.status} reason={cam_result.reason}")

        # --upload 时同步上传，确保上传完成后再退出
        if args.upload and response.status == "NG":
            from seat_defect_core.anomaly_uploader import upload_inspection_response
            print(f"上传 NG 结果到 {args.upload}...")
            results = upload_inspection_response(response, args.upload)
            for r in results:
                print(f"  上传成功: anomaly_id={r.get('anomaly_id', '?')}")
            if not results:
                print("  上传失败（网络不通或后端未运行）")

        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"结果已写入：{output_path}")

        return 0

    except Exception as exc:
        print(f"检测失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
