import json
import os
import time
from typing import Any, Dict

from analysis_video.utils.logger import get_logger

logger = get_logger("storage.json")


class JsonStore:
    def __init__(self, path: str):
        """初始化 JSON 存储对象并加载已有数据。"""
        self.path = path
        self._ensure_dir()
        self.data: Dict[str, Any] = {}
        self._load()

    def _ensure_dir(self) -> None:
        """确保存储文件所在目录存在。"""
        d = os.path.dirname(self.path)
        if d:
            os.makedirs(d, exist_ok=True)

    def _load(self) -> None:
        """从磁盘读取 JSON 数据；读取失败时回退为空字典。"""
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception:
                self.data = {}

    def save(self) -> None:
        """以临时文件替换方式原子化保存 JSON 数据。"""
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    def now(self) -> int:
        """返回当前 Unix 时间戳（秒）。"""
        return int(time.time())