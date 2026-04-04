import os
import sys
import requests
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from analysis_video.accounts.user_service import UserService


def main():
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config', 'storage'))
    svc = UserService(base)

    share_url = '5.69 复制打开抖音，看看【源头信息哥的作品】【20251114】彭博社最新消息： 📉 2025... https://v.douyin.com/M8lvh4GfJ8U/ 07/12 KWm:/ Y@Z.mq '
    base_url = "https://api.tikhub.io"
    token = os.getenv("DOUYIN_AUTH_TOKEN", "")
    api_url = f"{base_url}/api/v1/douyin/app/v3/fetch_one_video_by_share_url"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"share_url": share_url}

    try:
        resp = requests.get(api_url, headers=headers, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        payload = data.get('data') or data
        aweme_detail = payload.get('aweme_detail', {})
        author = aweme_detail.get('author', {})
        sec_uid = author.get('sec_uid')
        nickname = author.get('nickname') or ''
        if not sec_uid:
            print('parse_failed: no sec_uid')
            return
        svc.add_creator(sec_uid, 'douyin', nickname)
        c = svc.get_creator(sec_uid)
        print('creator_added', c.id, c.platform, c.display_name)
    except Exception as e:
        print('request_failed', str(e))


if __name__ == '__main__':
    main()