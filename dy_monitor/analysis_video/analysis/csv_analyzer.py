import csv
import os
from datetime import datetime
from typing import List, Optional

from analysis_video.config.settings import AppConfig
from analysis_video.utils.logger import get_logger
from analysis_video.utils.video_base64 import video_to_base64

logger = get_logger("analysis.csv_analyzer")


def _storage_videos_dir() -> str:
    """返回视频 CSV 存储目录。"""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "storage", "videos"))


def _ensure_analysis_columns(header: List[str]) -> List[str]:
    """确保 CSV 头包含分析结果字段，并维持调度器所需列顺序。"""
    required = ["analysis_text", "llm_cents", "analyzed_at"]
    out = list(header)
    for col in required:
        if col not in out:
            out.append(col)
    return out


def _safe_int(value: str) -> int:
    """将字符串安全转为整数，失败时返回 0。"""
    try:
        return int((value or "0").strip())
    except Exception:
        return 0


def _fallback_summary(row: dict) -> str:
    """在无法调用模型时，基于互动数据生成可读摘要。"""
    digg = _safe_int(row.get("digg_count", "0"))
    comment = _safe_int(row.get("comment_count", "0"))
    collect = _safe_int(row.get("collect_count", "0"))
    aweme_id = (row.get("aweme_id") or "").strip()
    create_time = row.get("create_time", "")

    trend = "热度一般"
    if digg >= 5000 or comment >= 500:
        trend = "热度较高"
    elif digg >= 1000 or comment >= 100:
        trend = "热度上升"

    return (
        f"视频 {aweme_id} 互动概览：点赞 {digg}，评论 {comment}，收藏 {collect}，"
        f"发布时间戳 {create_time}。综合判断：{trend}，建议结合原视频进一步研判。"
    )


def _analyze_with_ark(download_url: str, aweme_id: str) -> Optional[str]:
    """尝试调用 Ark 多模态模型，失败时返回 None。"""
    api_key = os.getenv("ARK_API_KEY", "").strip()
    if not api_key:
        return None

    try:
        ark_module = __import__("volcenginesdkarkruntime", fromlist=["Ark"])
        Ark = getattr(ark_module, "Ark")
    except Exception:
        logger.warning("Ark SDK not installed, fallback to rule-based summary.")
        return None

    base_url = os.getenv("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
    model = os.getenv("ARK_VISION_MODEL", "doubao-seed-1-6-vision-250815")

    try:
        base64_str = video_to_base64(
            download_url,
            include_data_uri=False,
            preferred_basename=aweme_id or None,
        )
        client = Ark(api_key=api_key, base_url=base_url)
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "请用中文输出一段不超过120字的投资信息摘要，聚焦观点、风险与结论，不要使用markdown。",
                        },
                        {
                            "type": "video_url",
                            "video_url": {
                                "url": f"data:video/mp4;base64,{base64_str}",
                            },
                        },
                    ],
                }
            ],
        )
        content = (resp.choices[0].message.content or "").strip()
        return content or None
    except Exception as exc:
        logger.warning(f"Ark analyze failed for aweme_id={aweme_id}: {exc}")
        return None


def _analyze_row(row: dict) -> tuple[str, int]:
    """分析单条视频记录，返回 (分析文本, 成本分)。"""
    aweme_id = (row.get("aweme_id") or "").strip()
    download_url = (row.get("download_url") or "").strip()

    if download_url:
        ark_text = _analyze_with_ark(download_url, aweme_id)
        if ark_text:
            return ark_text, 10

    return _fallback_summary(row), 1


def analyze_pending_videos_in_csv(config: AppConfig) -> None:
    """扫描 storage/videos 下的作者 CSV，并补齐未分析的视频结果列。"""
    _ = config  # 预留给后续按配置动态切换策略
    videos_dir = _storage_videos_dir()
    if not os.path.isdir(videos_dir):
        logger.info("videos dir does not exist, skip analysis")
        return

    files = [f for f in os.listdir(videos_dir) if f.lower().endswith(".csv")]
    if not files:
        logger.info("no video csv files found")
        return

    for filename in files:
        csv_path = os.path.join(videos_dir, filename)
        try:
            with open(csv_path, "r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                old_header = reader.fieldnames or []

            if not old_header:
                continue

            header = _ensure_analysis_columns(old_header)
            updated = False

            for row in rows:
                analyzed_at = (row.get("analyzed_at") or "").strip()
                if analyzed_at:
                    continue

                analysis_text, llm_cents = _analyze_row(row)
                row["analysis_text"] = analysis_text
                row["llm_cents"] = str(llm_cents)
                row["analyzed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                updated = True

            if updated:
                with open(csv_path, "w", encoding="utf-8", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=header)
                    writer.writeheader()
                    for row in rows:
                        writer.writerow({k: row.get(k, "") for k in header})
                logger.info(f"updated analyzed rows in {filename}")
        except Exception as exc:
            logger.error(f"analyze csv failed file={filename} err={exc}")
