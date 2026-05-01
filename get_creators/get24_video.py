import argparse
import csv
import json
import os
import time
from typing import Dict, List, Optional

import requests
from dotenv import dotenv_values, load_dotenv


# 自动加载 .env，保证脚本直接运行时能读取 token
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
SCRIPT_ENV_PATH = os.path.join(SCRIPT_DIR, ".env")
ROOT_ENV_PATH = os.path.join(PROJECT_ROOT, ".env")
SCRIPT_ENV_VALUES = dotenv_values(SCRIPT_ENV_PATH)
ROOT_ENV_VALUES = dotenv_values(ROOT_ENV_PATH)
load_dotenv(SCRIPT_ENV_PATH, override=False)
load_dotenv(ROOT_ENV_PATH, override=False)


DEFAULT_BASE_URL = os.getenv("TIKHUB_BASE_URL", "https://api.tikhub.io")
DEFAULT_TIMEOUT_SEC = float(os.getenv("DOUYIN_HTTP_TIMEOUT_SEC", "20") or 20)


def _first_nonempty(*values: Optional[str]) -> str:
	"""从一组候选值中返回第一个非空字符串。"""
	for value in values:
		if value is None:
			continue
		text = str(value).strip().strip("\"").strip("'")
		if text:
			return text
	return ""


def _resolve_token(auth_token: Optional[str]) -> str:
	"""解析 Token：优先命令行，其次环境变量与 .env。"""
	return _first_nonempty(
		auth_token,
		os.getenv("DOUYIN_AUTH_TOKEN"),
		os.getenv("TIKHUB_API_TOKEN"),
		SCRIPT_ENV_VALUES.get("DOUYIN_AUTH_TOKEN"),
		SCRIPT_ENV_VALUES.get("TIKHUB_API_TOKEN"),
		ROOT_ENV_VALUES.get("DOUYIN_AUTH_TOKEN"),
		ROOT_ENV_VALUES.get("TIKHUB_API_TOKEN"),
	)


def fetch_recent_video_download_urls(
	sec_id: str,
	auth_token: Optional[str] = None,
	base_url: str = DEFAULT_BASE_URL,
	timeout_sec: float = DEFAULT_TIMEOUT_SEC,
	count: int = 20,
) -> List[Dict[str, str]]:
	"""
	根据 sec_id 获取博主近 24 小时内发布视频的下载链接。

	返回值中包含：aweme_id、create_time、download_url。
	"""
	token = _resolve_token(auth_token)
	if not token:
		raise ValueError("Missing token. Please set DOUYIN_AUTH_TOKEN (or TIKHUB_API_TOKEN).")

	api_url = f"{base_url.rstrip('/')}/api/v1/douyin/app/v3/fetch_user_post_videos"
	headers = {"Authorization": f"Bearer {token}"}

	# 24 小时边界（秒级时间戳）
	boundary = int(time.time()) - 24 * 3600
	max_cursor = 0
	results: List[Dict[str, str]] = []

	# 分页抓取，直到没有更多或遇到 24 小时外的视频
	while True:
		params = {
			"sec_user_id": sec_id,
			"max_cursor": max_cursor,
			"count": count,
			"sort_type": 0,
		}
		resp = requests.get(api_url, headers=headers, params=params, timeout=timeout_sec)
		resp.raise_for_status()
		payload = resp.json().get("data") or resp.json()

		aweme_list = payload.get("aweme_list") or []
		if not aweme_list:
			break

		reached_old = False
		for item in aweme_list:
			create_time = int(item.get("create_time") or 0)
			if create_time < boundary:
				reached_old = True
				continue

			video_obj = item.get("video") or {}
			download_addr = video_obj.get("download_addr") or {}
			download_url_list = download_addr.get("url_list") or []
			download_url = download_url_list[0] if download_url_list else ""

			results.append(
				{
					"aweme_id": str(item.get("aweme_id") or ""),
					"create_time": str(create_time),
					"download_url": download_url,
				}
			)

		if reached_old:
			break

		has_more = payload.get("has_more")
		next_cursor = payload.get("max_cursor")
		if has_more and next_cursor is not None:
			max_cursor = next_cursor
			continue
		break

	return results


def save_results(data: List[Dict[str, str]], output_path: str, fmt: str) -> None:
	"""将结果保存到本地文件，支持 json 或 csv。"""
	fmt = (fmt or "json").lower().strip()
	if fmt not in {"json", "csv"}:
		raise ValueError("output format must be json or csv")

	# 确保输出目录存在
	output_dir = os.path.dirname(os.path.abspath(output_path))
	os.makedirs(output_dir, exist_ok=True)

	if fmt == "json":
		with open(output_path, "w", encoding="utf-8") as f:
			json.dump(data, f, ensure_ascii=False, indent=2)
		return

	# csv 格式输出
	with open(output_path, "w", encoding="utf-8", newline="") as f:
		writer = csv.DictWriter(
			f, fieldnames=["aweme_id", "create_time", "download_url"]
		)
		writer.writeheader()
		for row in data:
			writer.writerow(row)


def main() -> int:
	# 在这里直接填写 sec_id（命令行参数将被忽略）
	SEC_ID = "MS4wLjABAAAAdY-kHKi6v_XePn6DxZrI12jYs7Mek_wP3YhfP5n2CXc"
	TOKEN = None
	BASE_URL = DEFAULT_BASE_URL
	TIMEOUT_SEC = DEFAULT_TIMEOUT_SEC
	COUNT = 20
	# 输出格式与路径
	OUTPUT_FORMAT = "json"
	OUTPUT_PATH = os.path.join(SCRIPT_DIR, "output_24h.json")

	try:
		if not SEC_ID:
			raise ValueError("SEC_ID 不能为空，请在代码中填写")
		data = fetch_recent_video_download_urls(
			sec_id=SEC_ID,
			auth_token=TOKEN,
			base_url=BASE_URL,
			timeout_sec=TIMEOUT_SEC,
			count=COUNT,
		)
		save_results(data, OUTPUT_PATH, OUTPUT_FORMAT)
		print(f"Saved {len(data)} items to: {OUTPUT_PATH}")
		return 0
	except requests.RequestException as exc:
		print(f"Request failed: {exc}")
		return 1
	except ValueError as exc:
		print(f"Invalid input or response: {exc}")
		return 1


if __name__ == "__main__":
	raise SystemExit(main())
