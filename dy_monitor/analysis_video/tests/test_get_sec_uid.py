import os
import sys

# 将项目根目录添加到 sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from dotenv import load_dotenv
from analysis_video.providers.douyin import get_sec_uid_from_share_link

if __name__ == "__main__":
    # 加载 .env
    load_dotenv()

    # 示例分享链接
    share_url = "https://v.douyin.com/hoNVcbAUnOU/"
#3.58 复制打开抖音，看看【今日财经速递🔥的作品】# 黄金 # 热点 # 最新消息 # 国际 # 上... https://v.douyin.com/hoNVcbAUnOU/ M@j.CH usR:/ 04/18 
    # 获取 sec_uid
    sec_uid = get_sec_uid_from_share_link(share_url)

    if sec_uid:
        print(f"成功从分享链接中提取 sec_uid: {sec_uid}")
    else:
        print("未能提取 sec_uid。请检查您的 DOUYIN_AUTH_TOKEN 是否已在 .env 文件中正确设置。")