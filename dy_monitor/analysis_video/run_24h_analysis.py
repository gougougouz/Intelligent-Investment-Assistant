from __future__ import annotations

import argparse
import json
import os
import sys

if __package__ is None or __package__ == "":
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from analysis_video.workflows.one_off_pipeline import run_24h_creator_pipeline
from analysis_video.utils.logger import get_logger

logger = get_logger("entry.run_24h")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one-off 24h creator analysis and output investment advice.")
    parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help="Skip network fetching and only analyze data already stored in CSV.",
    )
    parser.add_argument(
        "--refresh-bounds",
        action="store_true",
        help="Refresh history bounds from recent 7-day data before analysis.",
    )
    args = parser.parse_args()

    report = run_24h_creator_pipeline(
        refresh_history_bounds=args.refresh_bounds,
        fetch_new_videos=not args.skip_fetch,
    )

    summary = {
        "generated_at": report.get("generated_at"),
        "scope_name": report.get("scope_name"),
        "video_count": report.get("video_count"),
        "final_score": report.get("final_score"),
        "sentiment_level": report.get("sentiment_level"),
        "investment_advice": report.get("investment_advice"),
        "report_path": report.get("report_path"),
        "fetched_creator_count": report.get("fetched_creator_count"),
        "fetched_video_count": report.get("fetched_video_count"),
    }

    logger.info(
        "Run finished "
        f"score={summary.get('final_score')} advice={summary.get('investment_advice')} "
        f"path={summary.get('report_path')}"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
