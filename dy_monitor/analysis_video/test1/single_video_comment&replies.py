import requests
import json
import os

# 从 .env 文件加载环境变量
from dotenv import load_dotenv
load_dotenv()

API_TOKEN = os.getenv("TIKHUB_API_TOKEN")





payload={}
headers = {
   'Authorization': f'Bearer {API_TOKEN}'
}
cursor = 0
count = 20
url = f"https://api.tikhub.io/api/v1/douyin/web/fetch_video_comment_replies?item_id=7256431404848860476&comment_id=7256432985954714404&cursor={cursor}&count={count}"



response = requests.request("GET", url, headers=headers, data=payload)
response.raise_for_status()
data = response.json()

output_path = os.path.join(os.path.dirname(__file__), "single_video_comments&replies_output.json")
with open(output_path, "w", encoding="utf-8") as f:
   json.dump(data, f, ensure_ascii=False, indent=2)

print(f"成功获取评论数据，已写入: {output_path}")

