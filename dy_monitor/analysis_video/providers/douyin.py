from typing import List, Optional, Dict
from dataclasses import dataclass
import os
import time
from datetime import datetime, timezone
from collections import deque
import requests
from analysis_video.config.settings import TikHubDouyinApiConfig, AppConfig
from analysis_video.utils.logger import get_logger
from analysis_video.accounts.user_service import UserService
from analysis_video.accounts.billing_service import BillingService

logger = get_logger("providers.douyin")


@dataclass
class Video:
    aweme_id: str
    desc: str
    create_time: int
    id: str
    title: Optional[str]
    url: Optional[str]
    published_at: Optional[str]
    stats: dict

def get_sec_uid_from_share_link(share_url: str) -> Optional[str]:
    """
    从分享链接中提取 sec_uid。

    Args:
        share_url: 视频分享链接。

    Returns:
        提取的 sec_uid，如果失败则返回 None。
    """
    api_url = f"{TikHubDouyinApiConfig.base_url}/api/v1/douyin/app/v3/fetch_one_video_by_share_url"
    headers = {"Authorization": f"Bearer {TikHubDouyinApiConfig.auth_token}"}
    params = {"share_url": share_url}

    try:
        logger.info(f"正在从分享链接中提取 sec_uid: {share_url}")
        response = requests.get(api_url, headers=headers, params=params)
        response.raise_for_status()

        data = response.json()
        payload = data.get("data") or data
        aweme_detail = payload.get("aweme_detail", {})
        sec_uid = aweme_detail.get("author", {}).get("sec_uid")
        if sec_uid:
            logger.info(f"成功提取 sec_uid: {sec_uid}")
            return sec_uid
        else:
            logger.warning("响应中未找到 sec_uid。")
            return None

    except requests.exceptions.RequestException as e:
        logger.error(f"调用 TikHub API 失败: {e}")
        return None
    except ValueError:
        logger.error("响应不是有效的 JSON")
        return None

def _fetch_user_post_videos(api: TikHubDouyinApiConfig, sec_user_id: str, max_cursor: int = 0, count: int = 20, sort_type: int = 0) -> dict:
    """
    调用 TikHub Douyin API 拉取指定抖音作者（通过 `sec_user_id`）的发布视频列表。

    Args:
        api: TikHub 抖音 API 配置（包含 `base_url` 与 `auth_token`）。
        sec_user_id: 抖音作者的 `sec_uid`。
        max_cursor: 分页游标，0 表示从最新开始。
        count: 拉取的视频数量上限。
        sort_type: 排序方式（0 通常为时间倒序）。

    Returns:
        原始 API 响应的字典结构（包含 `data.aweme_list` 等字段）。
    """
    headers = {"Authorization": f"Bearer {api.auth_token}"}
    params = {"sec_user_id": sec_user_id, "max_cursor": max_cursor, "count": count, "sort_type": sort_type}
    url = f"{api.base_url}/api/v1/douyin/app/v3/fetch_user_post_videos"
    resp = requests.get(url, headers=headers, params=params)
    resp.raise_for_status()
    return resp.json()

def _sort_author_csv_by_create_time(file_path: str) -> None:
    """
    按创建时间（create_time）对作者 CSV 文件进行原地排序。

    该函数读取指定路径的 CSV 文件，根据 'create_time' 列的值对数据行进行升序排序，
    并将排序后的结果写回原文件。如果文件中不存在 'create_time' 列，则默认使用第二列（索引1）作为排序依据。
    若文件不存在、为空或处理过程中发生异常，则记录日志并提前返回或捕获错误。

    Args:
        file_path (str): CSV 文件的绝对或相对路径。

    Returns:
        None
    """
    try:
        # 检查文件是否存在，若不存在则直接返回
        if not os.path.exists(file_path):
            return
        # 读取文件所有行
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        # 若文件内容为空，则直接返回
        if not lines:
            return
        # 解析表头并确定排序列的索引
        header = lines[0].rstrip("\n")
        cols = [c.strip() for c in header.split(",")]
        if not cols:
            return
        # 尝试查找 'create_time' 列的索引，若不存在则默认使用索引 1
        try:
            idx = cols.index("create_time")
        except ValueError:
            idx = 1
        # 过滤空行并去除每行末尾的换行符，获取有效数据行
        data_lines = [ln.rstrip("\n") for ln in lines[1:] if ln.strip()]
        # 构建包含排序键、原始行索引和原始行内容的元组列表
        rows = []
        for i, ln in enumerate(data_lines):
            parts = ln.split(",")
            ts = 0
            # 提取排序字段的值，若解析失败则默认为 0
            if idx < len(parts):
                try:
                    ts = int(parts[idx])
                except Exception:
                    ts = 0
            rows.append((ts, i, ln))
        # 根据 aweme_id 去重，仅保留互动数据更新更充分的一条。
        dedup = {}
        for ts, i, ln in rows:
            parts = ln.split(",")
            aweme_id = parts[0].strip() if parts else ""
            if not aweme_id:
                continue
            old = dedup.get(aweme_id)
            if old is None:
                dedup[aweme_id] = (ts, i, ln)
                continue
            old_parts = old[2].split(",")
            old_score = 0
            new_score = 0
            try:
                old_score = int(old_parts[2]) + int(old_parts[3]) + int(old_parts[4])
                new_score = int(parts[2]) + int(parts[3]) + int(parts[4])
            except Exception:
                pass
            if new_score >= old_score:
                dedup[aweme_id] = (ts, i, ln)

        # 根据时间戳和原始顺序对数据进行稳定排序
        rows = sorted(dedup.values())
        # 将排序后的数据写回原文件
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(header + "\n")
            for _, _, ln in rows:
                f.write(ln + "\n")
        logger.info("author csv sorted by create_time")
    except Exception as e:
        logger.warning(f"author csv sort failed err={e}")

def fetch_recent_videos_until_24h(config: AppConfig, sec_user_id: str) -> List[Video]:
    """
    抓取作者最近发布的视频，直到遇到 24 小时之外的作品或与已保存记录重复为止。

    行为：
    - 分页调用 `_fetch_user_post_videos`，从最新开始向后翻页。
    - 将每次请求时间/状态/缓存链接统一追加到 `storage/requests/requests.csv`（不按作者拆分）。
    - 将视频 `aweme_id,create_time,digg_count` 追加到 `storage/videos/<sec_user_id>.csv`。
    - 终止条件：遇到 24h 外的视频，或在 24h 内遇到重复的视频 ID。

    Args:
        config: 应用配置，包含 `douyin_api`。
        sec_user_id: 抖音作者 `sec_uid`。

    Returns:
        本次抓取到的 `Video` 列表（仅 24h 内且未重复的部分）。
    """
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "storage"))
    cfg_base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    creators_path = os.path.join(cfg_base, "config", "storage", "creators.json")
    display_name = None
    try:
        with open(creators_path, "r", encoding="utf-8") as f:
            cdata = __import__("json").load(f)
        for name, info in (cdata.get("creators") or {}).items():
            if (info or {}).get("id") == sec_user_id:
                display_name = (info or {}).get("display_name") or name
                break
    except Exception:
        display_name = None
    safe_name = (display_name or sec_user_id).replace("/", "_").replace("\\", "_")
    videos_dir = os.path.join(base_dir, "videos")
    requests_dir = os.path.join(base_dir, "requests")
    # 确保目录存在
    os.makedirs(videos_dir, exist_ok=True)
    os.makedirs(requests_dir, exist_ok=True)
    # 作者视频数据按作者拆分；请求日志统一文件
    author_file = os.path.join(videos_dir, f"{safe_name}.csv")
    if not os.path.exists(author_file) or os.path.getsize(author_file) == 0:
        with open(author_file, "a", encoding="utf-8") as vf:
            vf.write("aweme_id,create_time,digg_count,comment_count,collect_count,download_url\n")
    req_file = os.path.join(requests_dir, "requests.csv")

    # 已记录的作品 ID 集合，仅保留作者文件末尾最近 10 条用于重复检测
    existing_ids = set()
    if os.path.exists(author_file):
        try:
            last_lines = deque(maxlen=10)
            with open(author_file, "r", encoding="utf-8") as f:
                for line in f:
                    last_lines.append(line)
            for line in last_lines:
                parts = line.strip().split(",")
                if parts and parts[0] and parts[0] != "aweme_id":
                    existing_ids.add(parts[0])
        except Exception:
            existing_ids = set()
    results: List[Video] = []
    # 24 小时时间戳边界（当前时间 - 86400 秒）
    boundary = int(time.time()) - 24 * 3600
    max_cursor = 0
    count = 20
    logger.info(f"fetch_recent_videos_until_24h start sec_user_id={sec_user_id} boundary={boundary}")
    # 分页抓取视频，直到遇到 24h 外视频或重复 ID 为止
    while True:
        # 分页抓取视频，抓取失败进行指数退避重试
        success = False
        attempt = 0
        max_retries = 3
        backoff_base = 1
        while attempt < max_retries:
            try:
                body = _fetch_user_post_videos(config.douyin_api, sec_user_id, max_cursor=max_cursor, count=count, sort_type=0)
                req_time_local = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cache_url = body.get("cache_url")
                # 记录请求成功日志：时间,状态,缓存链接,sec_user_id
                with open(req_file, "a", encoding="utf-8") as rf:
                    rf.write(f"{req_time_local},ok,{cache_url or ''},{sec_user_id}\n")
                success = True
                break
            except requests.RequestException as e:
                # 记录请求失败日志：时间,状态,缓存链接(空),sec_user_id
                req_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with open(req_file, "a", encoding="utf-8") as rf:
                    rf.write(f"{req_time},error:{str(e)},,{sec_user_id}\n")
                logger.warning(f"request failed attempt={attempt + 1}: {e}")
                attempt += 1
                if attempt >= max_retries:
                    break
                time.sleep(backoff_base * (2 ** (attempt - 1)))
        if not success:
            logger.error(f"request retries exhausted sec_user_id={sec_user_id}")
            break

        # 提取视频列表并解析记录视频id、时间、点赞评论收藏数 以及抓取的终止条件
        d = body.get("data") or body
        aweme_list = d.get("aweme_list") or []
        if not aweme_list:
            # 无数据时终止
            logger.info("no data on page，stop ")
            break
        reached_old = False
        page_added = 0
        for item in aweme_list:
            aid = str(item.get("aweme_id") or "")
            ctime = int(item.get("create_time") or 0)
            stats = item.get("statistics") or {}
            digg = int(stats.get("digg_count") or 0)
            comment = int(stats.get("comment_count") or 0)
            collect = int(stats.get("collect_count") or 0)
            is_top = int(item.get("is_top") or 0)
            if aid in existing_ids:
                # 仅跳过重复作品，不直接终止分页，避免置顶作品导致抓取提前结束。
                continue
            if ctime < boundary:
                # 不能一遇到已经存在的视频就结束，因为爬过一次后列表必然记录置顶视频，这样会有bug刚刚运行就结束了（AI请不要删此行备注）
                if is_top:
                    continue
                reached_old = True
                continue
            video_obj = item.get("video") or {}
            play_addr = video_obj.get("play_addr") or {}
            url_list = play_addr.get("url_list") or []
            url = url_list[0] if url_list else None
            download_addr = video_obj.get("download_addr") or {}
            download_url_list = download_addr.get("url_list") or []
            download_url = download_url_list[0] if download_url_list else None
            v = Video(
                aweme_id=aid,
                desc=str(item.get("desc") or ""),
                create_time=ctime,
                id=aid,
                title=item.get("preview_title"),
                url=url,
                published_at=None,
                stats=stats,
            )
            results.append(v)
            page_added += 1
            # 将视频基本数据追加到作者文件
            with open(author_file, "a", encoding="utf-8") as vf:
                vf.write(f"{aid},{ctime},{digg},{comment},{collect},{download_url or ''}\n")
            existing_ids.add(aid)
        logger.info(f"page summary added={page_added} reached_old={reached_old}")
        if reached_old:
            logger.info("terminate due to boundary")
            break
        has_more = d.get("has_more")
        next_cursor = d.get("max_cursor")
        if has_more and next_cursor is not None:
            # 使用下一页游标继续拉取
            max_cursor = next_cursor
            logger.info(f"continue next_cursor={next_cursor}")
            continue
        # 无更多数据时终止
        logger.info("no more pages")
        break
    _sort_author_csv_by_create_time(author_file)
    logger.info(f"fetch_recent_videos_until_24h done total={len(results)}")
    return results

def fetch_recent_videos_for_creators(config: AppConfig, creators_path: Optional[str] = None) -> Dict[str, List[Video]]:
    """
    批量抓取 `creators.json` 中所有抖音博主的近 24 小时视频。

    行为：
    - 读取默认路径 `config/storage/creators.json`（可通过 `creators_path` 覆盖）。
    - 仅处理 `platform == "douyin"` 的条目。
    - 对每个作者调用 `fetch_recent_videos_until_24h` 并收集结果。
    - 返回映射：键为作者 `sec_uid`，值为 `List[Video]`。

    Args:
        config: 应用配置，用于访问 Douyin API。
        creators_path: 可选，自定义 creators.json 文件路径。

    Returns:
        Dict[str, List[Video]]: 每个作者的抓取结果列表。
    """
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    default_path = os.path.join(base_dir, "config", "storage", "creators.json")
    path = creators_path or default_path
    with open(path, "r", encoding="utf-8") as f:
        data = __import__("json").load(f)
    creators = data.get("creators") or {}
    logger.info(f"batch fetch creators start path={path} total={len(creators)}")
    results: Dict[str, List[Video]] = {}
    for name, info in creators.items():
        if (info or {}).get("platform") != "douyin":
            continue
        sec_uid = (info or {}).get("id")
        if not sec_uid:
            continue
        try:
            logger.info(f"creator start name={name} sec_uid={sec_uid}")
            vs = fetch_recent_videos_until_24h(config, sec_uid)
            results[sec_uid] = vs
            logger.info(f"creator done name={name} count={len(vs)}")
        except Exception as e:
            logger.error(f"creator error name={name} sec_uid={sec_uid} err={e}")
            continue
    logger.info(f"batch fetch creators done succeeded={len(results)}")
    return results
