import os
from typing import Dict

from .json_store import JsonStore


class ProgressStore:
    def __init__(self, path: str):
        """初始化分析进度存储。"""
        self.store = JsonStore(path)
        self.store.data.setdefault("analyzed", {})

    def mark_analyzed(self, user_id: str, aweme_id: str) -> None:
        """仅标记视频已分析（不写入分析文本）。"""
        m = self.store.data["analyzed"].setdefault(user_id, {})
        m[str(aweme_id)] = {"status": "analyzed", "ts": self.store.now()}
        self.store.save()

    def is_analyzed(self, user_id: str, aweme_id: str) -> bool:
        """判断某用户下某视频是否已分析。"""
        m: Dict[str, Dict] = self.store.data.get("analyzed", {}).get(user_id, {})
        v = m.get(str(aweme_id))
        return bool(v and v.get("status") == "analyzed")

    def save_result(self, user_id: str, aweme_id: str, text: str, llm_cents: int) -> None:
        """保存视频分析结果文本与计费信息。"""
        m = self.store.data["analyzed"].setdefault(user_id, {})
        rec = m.setdefault(str(aweme_id), {})
        rec["status"] = "analyzed"
        rec["ts"] = self.store.now()
        rec["text"] = text
        rec["llm_cents"] = int(llm_cents or 0)
        self.store.save()