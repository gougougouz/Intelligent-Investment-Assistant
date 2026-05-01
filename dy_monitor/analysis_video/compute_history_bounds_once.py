from __future__ import annotations

import argparse
import json
import os
import sys

if __package__ is None or __package__ == "":
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from analysis_video.analysis.history_bounds import HISTORY_BOUNDS_PATH, bootstrap_history_bounds


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute 7-day daily-extrema history bounds once and print values for config.py."
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=7,
        help="How many previous days to use. Default is 7.",
    )
    args = parser.parse_args()

    bounds = bootstrap_history_bounds(lookback_days=max(1, int(args.lookback_days)))
    hist_min = float(bounds.get("hist_min", 0.0))
    hist_max = float(bounds.get("hist_max", 0.0))

    print("=" * 80)
    print("历史极值计算完成（前N天逐日初始分取极值）")
    print("=" * 80)
    print(json.dumps(bounds, ensure_ascii=False, indent=2))
    print("\n请将以下值填写到 analysis_video/analysis/config.py：")
    print(f"HIST_MIN = {hist_min}")
    print(f"HIST_MAX = {hist_max}")
    print("\n边界详情文件：")
    print(HISTORY_BOUNDS_PATH)


if __name__ == "__main__":
    main()
