import argparse
import csv
import json
import os
import re
from typing import Dict, Optional

import requests
from dotenv import dotenv_values, load_dotenv
"""
从抖音分享文本中提取博主 sec_id 和昵称的工具脚本。
"""

# Auto-load .env so running this script directly can read tokens.
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
	for value in values:
		if value is None:
			continue
		text = str(value).strip().strip("\"").strip("'")
		if text:
			return text
	return ""


def extract_share_url(share_text: str) -> str:
	"""Extract the first URL from Douyin share text."""
	match = re.search(r"https?://[^\s]+", share_text or "")
	if not match:
		raise ValueError("No URL found in input share text.")

	url = match.group(0).strip().rstrip(".,;!?)]}\"'")
	if not url:
		raise ValueError("Extracted URL is empty.")
	return url


def fetch_creator_profile_from_share_link(
	share_text: str,
	auth_token: Optional[str] = None,
	base_url: str = DEFAULT_BASE_URL,
	timeout_sec: float = DEFAULT_TIMEOUT_SEC,
) -> Dict[str, str]:
	"""Get creator nickname and sec_id from a Douyin share link."""
	token = _first_nonempty(
		auth_token,
		os.getenv("DOUYIN_AUTH_TOKEN"),
		os.getenv("TIKHUB_API_TOKEN"),
		SCRIPT_ENV_VALUES.get("DOUYIN_AUTH_TOKEN"),
		SCRIPT_ENV_VALUES.get("TIKHUB_API_TOKEN"),
		ROOT_ENV_VALUES.get("DOUYIN_AUTH_TOKEN"),
		ROOT_ENV_VALUES.get("TIKHUB_API_TOKEN"),
	)
	if not token:
		raise ValueError("Missing token. Please set DOUYIN_AUTH_TOKEN (or TIKHUB_API_TOKEN).")

	share_url = extract_share_url(share_text)
	api_url = f"{base_url.rstrip('/')}/api/v1/douyin/app/v3/fetch_one_video_by_share_url"
	headers = {"Authorization": f"Bearer {token}"}
	params = {"share_url": share_url}

	response = requests.get(api_url, headers=headers, params=params, timeout=timeout_sec)
	response.raise_for_status()

	body = response.json()
	payload = body.get("data") or body

	aweme_detail = payload.get("aweme_detail") or {}
	author = aweme_detail.get("author") or payload.get("author") or {}

	nickname = str(author.get("nickname") or "").strip()
	sec_id = str(author.get("sec_uid") or author.get("sec_id") or "").strip()
	uid = str(author.get("uid") or "").strip()

	if not sec_id:
		raise ValueError("API response does not contain sec_id/sec_uid.")

	return {
		"nickname": nickname,
		"sec_id": sec_id,
		"uid": uid,
		"share_url": share_url,
	}


def save_profile(profile: Dict[str, str], output_path: str, fmt: str) -> None:
	"""将博主信息保存到本地文件，支持 json 或 csv。"""
	fmt = (fmt or "json").lower().strip()
	if fmt not in {"json", "csv"}:
		raise ValueError("output format must be json or csv")

	output_dir = os.path.dirname(os.path.abspath(output_path))
	os.makedirs(output_dir, exist_ok=True)

	if fmt == "json":
		existing = []
		if os.path.exists(output_path):
			try:
				with open(output_path, "r", encoding="utf-8") as f:
					loaded = json.load(f)
				if isinstance(loaded, list):
					existing = loaded
				elif isinstance(loaded, dict):
					existing = [loaded]
			except Exception:
				existing = []
		existing.append(profile)
		with open(output_path, "w", encoding="utf-8") as f:
			json.dump(existing, f, ensure_ascii=False, indent=2)
		return

	file_exists = os.path.exists(output_path)
	with open(output_path, "a", encoding="utf-8", newline="") as f:
		writer = csv.DictWriter(f, fieldnames=["nickname", "sec_id", "uid", "share_url"])
		if not file_exists:
			writer.writeheader()
		writer.writerow(profile)


def main() -> int:
	parser = argparse.ArgumentParser(
		description="Get Douyin creator nickname and sec_id from share link"
	)
	parser.add_argument("share_text", nargs="?", help="Douyin share text or URL")
	parser.add_argument("--token", default=None, help="TikHub token, fallback to DOUYIN_AUTH_TOKEN")
	parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="TikHub base URL")
	parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SEC, help="HTTP timeout seconds")
	args = parser.parse_args()

	share_text = args.share_text
	if not share_text:
		share_text = input("Please paste share text/url: ").strip()

	try:
		result = fetch_creator_profile_from_share_link(
			share_text=share_text,
			auth_token=args.token,
			base_url=args.base_url,
			timeout_sec=args.timeout,
		)
		# 输出到文件
		output_format = "json"
		output_path = os.path.join(SCRIPT_DIR, "creator_profile.json")
		save_profile(result, output_path, output_format)
		print(json.dumps(result, ensure_ascii=False, indent=2))
		print(f"Saved to: {output_path}")
		return 0
	except requests.RequestException as exc:
		print(f"Request failed: {exc}")
		return 1
	except ValueError as exc:
		print(f"Invalid input or response: {exc}")
		return 1


if __name__ == "__main__":
	raise SystemExit(main())
