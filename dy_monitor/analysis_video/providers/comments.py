"""视频评论抓取器：按 aweme_id 获取评论文本与点赞数。"""

from typing import Any, Dict, List

import requests

from analysis_video.config.settings import TikHubDouyinApiConfig
from analysis_video.utils.logger import get_logger

logger = get_logger("providers.comments")


def _extract_comments(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
	"""从不同响应结构中提取 comments 列表。"""
	data = payload.get("data") if isinstance(payload, dict) else None
	if isinstance(data, dict):
		comments = data.get("comments")
		if isinstance(comments, list):
			return comments

	comments = payload.get("comments") if isinstance(payload, dict) else None
	if isinstance(comments, list):
		return comments

	return []


def fetch_video_comments(
	api: TikHubDouyinApiConfig,
	aweme_id: str,
	*,
	count: int = 50,
	max_pages: int = 2,
	timeout: int = 15,
) -> List[Dict[str, Any]]:
	"""抓取视频评论并标准化为 analysis_llm 所需字段。"""
	aid = str(aweme_id or "").strip()
	if not aid:
		return []

	headers = {"Authorization": f"Bearer {api.auth_token}"}
	base_url = api.base_url.rstrip("/")
	cursor = 0
	collected: List[Dict[str, Any]] = []

	for _ in range(max_pages):
		url = f"{base_url}/api/v1/douyin/web/fetch_video_comments"
		params = {
			"aweme_id": aid,
			"cursor": cursor,
			"count": count,
		}
		try:
			resp = requests.get(url, headers=headers, params=params, timeout=timeout)
			resp.raise_for_status()
			payload = resp.json()
		except Exception as exc:  # noqa: BLE001
			logger.warning(f"fetch comments failed aweme_id={aid} cursor={cursor} err={exc}")
			break

		page_comments = _extract_comments(payload)
		if not page_comments:
			break

		for item in page_comments:
			if not isinstance(item, dict):
				continue
			comment_id = str(item.get("cid") or item.get("comment_id") or "").strip()
			content = str(item.get("text") or item.get("content") or "").strip()
			like_count = item.get("digg_count") or item.get("like_count") or 0
			if not comment_id or not content:
				continue
			try:
				normalized_like = float(like_count)
			except Exception:
				normalized_like = 0.0
			collected.append(
				{
					"comment_id": comment_id,
					"content": content,
					"like_count": normalized_like,
				}
			)

		data = payload.get("data") if isinstance(payload, dict) else {}
		has_more = bool((data or {}).get("has_more"))
		next_cursor = (data or {}).get("cursor")
		if not has_more or next_cursor is None:
			break
		try:
			cursor = int(next_cursor)
		except Exception:
			break

	return collected


def fetch_top_comments_by_digg(
	api: TikHubDouyinApiConfig,
	aweme_id: str,
	*,
	top_n: int = 20,
	count: int = 50,
	max_pages: int = 2,
) -> List[Dict[str, Any]]:
	"""抓取评论并按点赞倒序截取前 N 条。"""
	comments = fetch_video_comments(api, aweme_id, count=count, max_pages=max_pages)
	sorted_comments = sorted(
		comments,
		key=lambda x: float(x.get("like_count") or 0),
		reverse=True,
	)
	return sorted_comments[: max(0, int(top_n))]





