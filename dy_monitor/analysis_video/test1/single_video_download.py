import requests
import os
import json

# 从 .env 文件加载环境变量
from dotenv import load_dotenv
load_dotenv()

# 从环境变量中获取 API Token
API_TOKEN = os.getenv("TIKHUB_API_TOKEN")

# API 的基础 URL
BASE_URL = "https://api.tikhub.io"


def fetch_single_video(share_url: str):
    """根据分享链接获取单个作品数据"""
    if not API_TOKEN:
        print("错误：请在 .env 文件中设置 TIKHUB_API_TOKEN")
        return

    headers = {
        "Authorization": f"Bearer {API_TOKEN}"
    }

    params = {
        "share_url": share_url
    }

    try:
        response = requests.get(f"{BASE_URL}/api/v1/douyin/app/v3/fetch_one_video_by_share_url", 
                                headers=headers, params=params)
        response.raise_for_status()  # 如果请求失败则引发异常
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"请求出错: {e}")
        return None

if __name__ == "__main__":
    # 示例用法
    share_url = "https://v.douyin.com/xcUF8_0ewd8"
    data = fetch_single_video(share_url)

    if data:
        print("成功获取数据，已写入 single_video_output.json 文件。")
        
        # 将数据写入 JSON 文件
        output_path = os.path.join(os.path.dirname(__file__), "single_video_output.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        # 为了更好地显示，我们仍然在终端打印数据
        try:
            from rich import print as rprint
            rprint(data)
        except ImportError:
            import json
            print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print("未能获取数据。")