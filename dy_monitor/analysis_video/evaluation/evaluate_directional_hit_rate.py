from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from typing import Dict, List

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from analysis_video.evaluation.metrics import (
    compute_directional_hit_rate,
    predict_direction_from_text,
)


def _storage_videos_dir() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "storage", "videos"))


def _load_labels(path: str) -> List[Dict[str, str]]:
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return [row for row in reader if row.get("aweme_id") and row.get("realized_direction")]


def _load_video_rows() -> Dict[str, Dict[str, str]]:
    videos_dir = _storage_videos_dir()
    latest_rows: Dict[str, Dict[str, str]] = {}
    if not os.path.isdir(videos_dir):
        return latest_rows

    for filename in os.listdir(videos_dir):
        if not filename.lower().endswith(".csv"):
            continue
        csv_path = os.path.join(videos_dir, filename)
        try:
            with open(csv_path, "r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    aweme_id = (row.get("aweme_id") or "").strip()
                    if not aweme_id:
                        continue
                    latest_rows[aweme_id] = row
        except Exception:
            continue
    return latest_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate directional hit rate for video analysis.")
    parser.add_argument(
        "--labels",
        type=str,
        default=os.path.join(os.path.dirname(__file__), "data", "directional_labels_template.csv"),
        help="Label CSV path, with columns aweme_id and realized_direction.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=os.path.join(os.path.dirname(__file__), "reports", "directional_hit_rate_report.json"),
        help="Output JSON report path.",
    )
    args = parser.parse_args()

    labels = _load_labels(args.labels)
    video_rows = _load_video_rows()

    pairs: List[Dict[str, str]] = []
    for label in labels:
        aweme_id = (label.get("aweme_id") or "").strip()
        row = video_rows.get(aweme_id)
        if not row:
            continue
        pairs.append(
            {
                "predicted_direction": predict_direction_from_text(row.get("analysis_text", "")),
                "actual_direction": label.get("realized_direction", ""),
                "aweme_id": aweme_id,
            }
        )

    result = compute_directional_hit_rate(pairs)
    report = {
        "labels_file": os.path.abspath(args.labels),
        "sample_count": result["samples"],
        "correct_count": result["correct"],
        "skipped_count": result["skipped"],
        "directional_hit_rate": result["directional_hit_rate"],
        "up_precision_proxy": result["up_precision_proxy"],
        "down_precision_proxy": result["down_precision_proxy"],
        "neutral_precision_proxy": result["neutral_precision_proxy"],
    }

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"report saved to: {os.path.abspath(args.output)}")


if __name__ == "__main__":
    main()
