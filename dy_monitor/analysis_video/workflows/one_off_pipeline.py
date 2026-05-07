from __future__ import annotations

from datetime import datetime
import os
import shutil
from typing import Any, Dict, Optional

from analysis_video.analysis.csv_analyzer import (
    analyze_pending_videos_in_csv,
    format_investment_report_text,
)
from analysis_video.analysis.history_bounds import bootstrap_history_bounds
from analysis_video.config import AppConfig, load_config
from analysis_video.providers.douyin import fetch_recent_videos_for_creators
from analysis_video.utils.logger import get_logger

logger = get_logger("workflow.one_off")


def _reset_run_artifacts() -> None:
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    videos_dir = os.path.join(base_dir, "storage", "videos")
    download_dir = os.path.join(base_dir, "video_downloads")

    removed_csv = 0
    if os.path.isdir(videos_dir):
        for name in os.listdir(videos_dir):
            if not name.lower().endswith(".csv"):
                continue
            path = os.path.join(videos_dir, name)
            try:
                os.remove(path)
                removed_csv += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"reset: failed to remove csv {path}: {exc}")

    if os.path.isdir(download_dir):
        try:
            shutil.rmtree(download_dir)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"reset: failed to remove video_downloads {download_dir}: {exc}")

    logger.info(
        "reset: cleared creator csv files and downloaded videos "
        f"csv_removed={removed_csv}"
    )


def run_24h_creator_pipeline(
    config: Optional[AppConfig] = None,
    refresh_history_bounds: bool = False,
    fetch_new_videos: bool = True,
) -> Dict[str, Any]:
    """单次执行抓取+分析，输出近24小时的情绪分与投资建议。"""
    cfg = config or load_config()
    run_start = datetime.now()

    _reset_run_artifacts()

    if refresh_history_bounds:
        bounds = bootstrap_history_bounds(lookback_days=7, reference_now=run_start)
        logger.info(
            "History bounds refreshed "
            f"min={bounds.get('hist_min')} max={bounds.get('hist_max')} source={bounds.get('source')}"
        )

    fetch_result: Dict[str, Any] = {}
    if fetch_new_videos:
        fetch_result = fetch_recent_videos_for_creators(cfg)

    report = analyze_pending_videos_in_csv(cfg, only_after=run_start)
    report["fetched_creator_count"] = len(fetch_result)
    report["fetched_video_count"] = sum(len(vs) for vs in fetch_result.values())
    report["report_text"] = format_investment_report_text(report)

    logger.info(
        "One-off pipeline completed "
        f"score={report.get('final_score')} advice={report.get('investment_advice')} "
        f"videos={report.get('video_count')}"
    )
    return report
