import logging
import os
from logging.handlers import TimedRotatingFileHandler
from typing import Optional

LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"


def get_logger(
    name: str,
    log_dir: str = "logs",
    log_level: int = logging.INFO,
    base_dir: Optional[str] = None,
) -> logging.Logger:
    """获取或创建一个带时间和日期轮换的日志记录器。"""
    # 如果未提供 base_dir，则使用 `analysis_video` 目录
    if base_dir is None:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    # 创建日志目录
    log_path = os.path.join(base_dir, log_dir)
    os.makedirs(log_path, exist_ok=True)

    # 创建或获取记录器
    logger = logging.getLogger(name)
    logger.setLevel(log_level)

    # 如果记录器已经有处理器，则直接返回，避免重复添加
    if logger.hasHandlers():
        return logger

    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(console_handler)

    # 创建文件处理器，按天轮换
    file_handler = TimedRotatingFileHandler(
        os.path.join(log_path, f"{name}.log"),
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(file_handler)

    return logger