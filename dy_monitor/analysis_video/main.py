import os
import sys

if __package__ is None or __package__ == "":
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from analysis_video.scheduler import start_scheduler, job
from analysis_video.utils.logger import get_logger
from analysis_video.config import load_config

logger = get_logger("main")


def main():
    """程序入口：根据 RUN_ONCE 决定单次执行或启动循环调度。"""
    raw = os.getenv("RUN_ONCE")
    # 默认单次执行，便于本地直接运行 main.py 验证全链路。
    run_once = True if raw is None else raw.lower() == "true"
    if run_once:
        logger.info("Running one-off job.")
        cfg = load_config()
        report = job(cfg)
        if isinstance(report, dict):
            logger.info(
                "One-off completed "
                f"score={report.get('final_score')} "
                f"advice={report.get('investment_advice')} "
                f"report={report.get('report_path', '')}"
            )
    else:
        start_scheduler()


if __name__ == "__main__":
    main()