import requests
import json
import os

# 从 .env 文件加载环境变量
from dotenv import load_dotenv
load_dotenv()

API_TOKEN = os.getenv("TIKHUB_API_TOKEN")



cursor = 0
count = 20

payload={}
headers = {
   'Authorization': f'Bearer {API_TOKEN}'
}

share_url = "https://v.douyin.com/gAO9AUNlSag"
# 先根据分享链接获取视频数据，拿到 aweme_id 后再获取评论数据
url = f"https://api.tikhub.io/api/v1/douyin/web/fetch_one_video_by_share_url?share_url={share_url}"

response = requests.request("GET", url, headers=headers, data=payload)
response.raise_for_status()
video_data = response.json()
# 拿到视频数据，用json保存
output_path = os.path.join(os.path.dirname(__file__), "single_video_output.json")
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(video_data, f, ensure_ascii=False, indent=2)

aweme_id = video_data["data"]["aweme_detail"]["aweme_id"]

url = f"https://api.tikhub.io/api/v1/douyin/web/fetch_video_comments?aweme_id={aweme_id}&cursor={cursor}&count={count}"


response = requests.request("GET", url, headers=headers, data=payload)
response.raise_for_status()

data = response.json()



output_path = os.path.join(os.path.dirname(__file__), "single_video_comments_output.json")
with open(output_path, "w", encoding="utf-8") as f:
   json.dump(data, f, ensure_ascii=False, indent=2)

print(f"成功获取评论数据，已写入: {output_path}")