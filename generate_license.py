"""ライセンスキー生成ツール（販売者用）

使い方:
    python generate_license.py
    python generate_license.py --output path/to/license.key
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.license import generate_license_file


def main():
    parser = argparse.ArgumentParser(description="Video Kantan ライセンスキー生成")
    parser.add_argument(
        "--output", "-o",
        default=os.path.join(os.path.dirname(__file__), "license", "license.key"),
        help="出力先パス (デフォルト: license/license.key)",
    )
    args = parser.parse_args()

    output_path = os.path.abspath(args.output)
    key = generate_license_file(output_path)

    print(f"ライセンスキー: {key}")
    print(f"ファイル出力先: {output_path}")
    print()
    print("購入者にこのファイルを渡してください。")
    print("配置先: VideoKantan.exe と同じフォルダの license/ 内")


if __name__ == "__main__":
    main()
