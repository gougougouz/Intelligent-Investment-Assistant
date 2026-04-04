import requests
import os
import json

# 从 analysis_video 目录加载 .env，确保能取到 token
from dotenv import load_dotenv
env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv(env_path)

# 从环境变量中获取 API Token（兼容两种变量名）
API_TOKEN = os.getenv("DOUYIN_AUTH_TOKEN") 

# API 的基础 URL
BASE_URL = "https://api.tikhub.io"


def fetch_user_post_videos(sec_user_id: str, max_cursor: int = 0, count: int = 20, sort_type: int = 0):
    """获取用户主页作品数据"""
    if not API_TOKEN:
        print("错误：请在 .env 设置 DOUYIN_AUTH_TOKEN 或 TIKHUB_API_TOKEN")
        return

    headers = {
        "Authorization": f"Bearer {API_TOKEN}"
    }

    params = {
        "sec_user_id": sec_user_id,
        "max_cursor": max_cursor,
        "count": count,
        "sort_type": sort_type
    }

    try:
        response = requests.get(f"{BASE_URL}/api/v1/douyin/app/v3/fetch_user_post_videos", headers=headers, params=params)
        response.raise_for_status()  # 如果请求失败则引发异常
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"请求出错: {e}")
        return None

if __name__ == "__main__":
    # 示例用法
    sec_user_id = "MS4wLjABAAAAxDVMuuWfu2GOErVVpgBH0aE4a7gYLyi0NzPLRUHak70"
    data = fetch_user_post_videos(sec_user_id)

    if data:
        output_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "home_page.json"))
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"成功获取数据，已写入 {output_path}")
        try:
            from rich import print as rprint
            rprint(data)
        except ImportError:
            print(json.dumps(data, indent=2, ensure_ascii=False))