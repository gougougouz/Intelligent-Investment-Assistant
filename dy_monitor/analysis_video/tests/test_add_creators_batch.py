import os
import sys
import requests
import time
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from analysis_video.accounts.user_service import UserService


def fetch_author_by_share_url(share_url: str, base_url: str, token: str):
    api_url = f"{base_url}/api/v1/douyin/app/v3/fetch_one_video_by_share_url"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"share_url": share_url}
    for _ in range(3):
        resp = requests.get(api_url, headers=headers, params=params, timeout=20)
        if resp.status_code == 502:
            time.sleep(1.5)
            continue
        resp.raise_for_status()
        data = resp.json()
        payload = data.get('data') or data
        aweme_detail = payload.get('aweme_detail', {})
        author = aweme_detail.get('author', {})
        return author.get('sec_uid'), author.get('nickname')
    raise RuntimeError(f"bad_gateway: {share_url}")


def main():
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
    base_url = "https://api.tikhub.io"
    token = os.getenv("DOUYIN_AUTH_TOKEN", "")
    if not token:
        print('missing_token')
        return

    base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config', 'storage'))
    svc = UserService(base)

    share_urls = [
        "https://v.douyin.com/M8lvh4GfJ8U/",
        "https://v.douyin.com/lmmQRHKcOiA/",
        "https://v.douyin.com/rF6iihAya28/",
        "https://v.douyin.com/CJ_YOePppeU/",
        "https://v.douyin.com/zJNFyEu6mP8/",
        "https://v.douyin.com/LswbJyp9BfA/",
        "https://v.douyin.com/ZrhFM_fpJ_U/",
        "https://v.douyin.com/bti3aGcajxo/",
        "https://v.douyin.com/DvjdtVWDiaU/",
        "https://v.douyin.com/Kzf5AQXq-NI/",
        "https://v.douyin.com/J6Ggx22NzEk/",
        "https://v.douyin.com/gFcGLHtBshE/",
        "https://v.douyin.com/hoNVcbAUnOU/",
        "https://v.douyin.com/pgoGxG7GxIs/",
    ]

    added = []
    failed = []
    for url in share_urls:
        try:
            sec_uid, nickname = fetch_author_by_share_url(url, base_url, token)
            if not sec_uid:
                failed.append((url, 'no_sec_uid'))
                continue
            svc.add_creator(sec_uid, 'douyin', nickname or '')
            added.append((sec_uid, nickname or ''))
        except Exception as e:
            failed.append((url, str(e)))

    print('added_count', len(added))
    for sec_uid, nick in added:
        print('added', sec_uid, nick)
    if failed:
        print('failed_count', len(failed))
        for u, reason in failed:
            print('failed', u, reason)


if __name__ == '__main__':
    main()