
import requests
import json
import os

# 从 .env 文件加载环境变量
from dotenv import load_dotenv
load_dotenv()

API_TOKEN = os.getenv("TIKHUB_API_TOKEN")



url = "https://api.tikhub.io/api/v1/douyin/app/v3/fetch_user_post_videos"

params = {
   "sec_user_id": "MS4wLjABAAAAGjKNHxjkCZkvHOlbQoak8AfOMAzx94au5szDYGhfcv4",
   "max_cursor": max_cursor,
   "count": count,
   "sort_type": filter_type,
}

headers = {
   'Authorization': f'Bearer {API_TOKEN}'
}

response = requests.get(url, headers=headers, params=params, timeout=30)

print(response.status_code)
print(response.text)


