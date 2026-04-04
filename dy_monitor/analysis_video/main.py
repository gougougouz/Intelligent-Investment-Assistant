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
    run_once = os.getenv("RUN_ONCE", "false").lower() == "true"
    if run_once:
        logger.info("Running one-off job.")
        cfg = load_config()
        job(cfg)
    else:
        start_scheduler()


if __name__ == "__main__":
    main()