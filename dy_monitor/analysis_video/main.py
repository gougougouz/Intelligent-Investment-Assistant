import os
import sys

if __package__ is None or __package__ == "":
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from analysis_video.run_24h_analysis import main as run_24h_main
from analysis_video.utils.logger import get_logger

logger = get_logger("main")


def main():
    """程序入口：执行一次 24 小时视频抓取与投资建议分析。"""
    logger.info("Running one-off 24h creator analysis pipeline.")
    run_24h_main()


if __name__ == "__main__":
    main()