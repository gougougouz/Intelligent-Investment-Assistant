import csv
import json
import os
import statistics
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from analysis_video.config.settings import AppConfig
from analysis_video.providers.comments import fetch_top_comments_by_digg
from analysis_video.utils.logger import get_logger
from analysis_video.utils.video_base64 import video_to_base64

logger = get_logger("analysis.csv_analyzer")

POSITIVE_HINTS = [
    "看多",
    "上涨",
    "反弹",
    "利好",
    "突破",
    "增持",
    "机会",
    "修复",
    "买入",
    "超预期",
    "景气",
    "改善",
]

NEGATIVE_HINTS = [
    "看空",
    "下跌",
    "利空",
    "风险",
    "回撤",
    "减仓",
    "卖出",
    "高估",
    "泡沫",
    "承压",
    "亏损",
    "观望",
]


def _storage_videos_dir() -> str:
    """返回视频 CSV 存储目录。"""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "storage", "videos"))


def _storage_analysis_dir() -> str:
    """返回分析报告存储目录。"""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "storage", "analysis"))


def _ensure_analysis_columns(header: List[str]) -> List[str]:
    """确保 CSV 头包含分析结果字段，并维持调度器所需列顺序。"""
    required = ["analysis_text", "llm_cents", "analyzed_at"]
    out = list(header)
    for col in required:
        if col not in out:
            out.append(col)
    return out


def _safe_int(value: Any) -> int:
    """将字符串安全转为整数，失败时返回 0。"""
    try:
        return int((value or "0").strip())
    except Exception:
        return 0


def _safe_float(value: Any) -> float:
    """将输入安全转为浮点数，失败时返回 0.0。"""
    try:
        return float(str(value or "0").strip())
    except Exception:
        return 0.0


def _clamp(value: float, low: float, high: float) -> float:
    """将数值限制在闭区间 [low, high]。"""
    if value < low:
        return low
    if value > high:
        return high
    return value


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


def _analyze_with_analysis_llm(row: dict, config: AppConfig) -> Optional[tuple[str, int]]:
    """优先使用 analysis_llm 的单视频算法（多模态+逻辑评分+评论修正）。"""
    download_url = (row.get("download_url") or "").strip()
    aweme_id = (row.get("aweme_id") or "").strip()
    if not download_url or not aweme_id:
        return None

    try:
        from analysis_video.analysis.analysis_llm import ArkService, analyze_single_video
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"analysis_llm import failed, fallback. aweme_id={aweme_id} err={exc}")
        return None

    try:
        top_comments = fetch_top_comments_by_digg(config.douyin_api, aweme_id, top_n=6, count=50, max_pages=2)
        base64_str = video_to_base64(
            download_url,
            include_data_uri=False,
            preferred_basename=aweme_id or None,
        )
        ark_service = ArkService()
        result = analyze_single_video(
            ark_service=ark_service,
            base64_str=base64_str,
            top_comments=top_comments,
            fan_count=_safe_float(row.get("fan_count") or 0),
            like_count=_safe_float(row.get("digg_count") or 0),
            auth_type=str(row.get("auth_type") or "普通用户"),
            hist_acc=_safe_float(row.get("hist_acc") or 1.0),
        )
        text = str(result.get("analysis_text") or "").strip()
        llm_cents = int(result.get("llm_cents") or 12)
        if not text:
            return None
        return text, max(1, llm_cents)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"analysis_llm analyze failed, fallback. aweme_id={aweme_id} err={exc}")
        return None


def _analyze_row(row: dict, config: AppConfig) -> tuple[str, int]:
    """分析单条视频记录，返回 (分析文本, 成本分)。"""
    aweme_id = (row.get("aweme_id") or "").strip()
    download_url = (row.get("download_url") or "").strip()

    llm_result = _analyze_with_analysis_llm(row, config)
    if llm_result:
        return llm_result

    if download_url:
        ark_text = _analyze_with_ark(download_url, aweme_id)
        if ark_text:
            return ark_text, 10

    return _fallback_summary(row), 1


def _parse_dt(value: str) -> Optional[datetime]:
    """解析标准时间字符串，失败返回 None。"""
    text = (value or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def _interaction_heat(row: Dict[str, Any]) -> float:
    """基于点赞/评论/收藏计算互动热度（0~1）。"""
    digg_norm = _clamp(_safe_int(row.get("digg_count")) / 5000.0, 0.0, 1.0)
    comment_norm = _clamp(_safe_int(row.get("comment_count")) / 500.0, 0.0, 1.0)
    collect_norm = _clamp(_safe_int(row.get("collect_count")) / 300.0, 0.0, 1.0)
    return round(digg_norm * 0.55 + comment_norm * 0.30 + collect_norm * 0.15, 4)


def _estimate_sentiment_from_text(text: str) -> float:
    """从分析文本中估计情绪倾向（-1~1）。"""
    normalized = (text or "").strip().lower()
    if not normalized:
        return 0.0

    score = 0.0
    for kw in POSITIVE_HINTS:
        if kw in normalized:
            score += 0.18

    for kw in NEGATIVE_HINTS:
        if kw in normalized:
            score -= 0.18

    return round(_clamp(score, -1.0, 1.0), 3)


def _map_score_to_level_and_advice(final_score: float) -> tuple[str, str]:
    """将百分制得分映射为情绪等级和投资建议。"""
    score_int = int(round(final_score))
    if score_int <= 20:
        return "极端看空", "卖出/规避"
    if score_int <= 40:
        return "看空", "减仓/观望"
    if score_int <= 60:
        return "中性", "持有/观望"
    if score_int <= 80:
        return "看多", "加仓/持有"
    return "极端看多", "重点关注/择机买入"


def _build_risk_note(avg_sentiment: float, dispersion: float, avg_heat: float) -> str:
    """生成简洁风险提示。"""
    if dispersion >= 0.35:
        return "观点分歧较大，建议控制仓位并分批执行。"
    if avg_heat >= 0.7 and avg_sentiment < 0:
        return "热度较高但情绪偏空，需警惕追涨杀跌风险。"
    if avg_sentiment <= -0.25:
        return "整体情绪偏弱，优先关注风险暴露与仓位管理。"
    if avg_heat < 0.2:
        return "样本热度较低，信号稳定性一般，建议继续观察。"
    return "建议结合基本面与量价数据进行二次确认。"


def _dedupe_video_rows(video_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """按 creator+aweme_id 去重，保留互动数据更新更充分的一条。"""
    unique: Dict[str, Dict[str, Any]] = {}
    for row in video_rows:
        creator = (row.get("creator") or "").strip()
        aweme_id = (row.get("aweme_id") or "").strip()
        if not aweme_id:
            continue

        key = f"{creator}::{aweme_id}"
        old = unique.get(key)
        if old is None:
            unique[key] = row
            continue

        old_score = (
            _safe_int(old.get("digg_count"))
            + _safe_int(old.get("comment_count"))
            + _safe_int(old.get("collect_count"))
        )
        new_score = (
            _safe_int(row.get("digg_count"))
            + _safe_int(row.get("comment_count"))
            + _safe_int(row.get("collect_count"))
        )
        if new_score >= old_score:
            unique[key] = row

    return list(unique.values())


def build_investment_report(video_rows: List[Dict[str, Any]], scope_name: str = "本次新增视频") -> Dict[str, Any]:
    """根据视频必要数据构建聚合投资建议报告。"""
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    deduped_rows = _dedupe_video_rows(video_rows)
    if not deduped_rows:
        sentiment_level, investment_advice = _map_score_to_level_and_advice(50.0)
        return {
            "generated_at": generated_at,
            "scope_name": scope_name,
            "video_count": 0,
            "avg_heat": 0.0,
            "avg_sentiment": 0.0,
            "sentiment_dispersion": 0.0,
            "final_score": 50.0,
            "sentiment_level": sentiment_level,
            "investment_advice": investment_advice,
            "advice_reason": "暂无可用视频样本，先维持中性判断。",
            "risk_note": "样本不足，建议等待新增视频后再判断。",
            "key_videos": [],
        }

    scored_rows: List[Dict[str, Any]] = []
    for row in deduped_rows:
        heat_score = _interaction_heat(row)
        sentiment_score = _estimate_sentiment_from_text(str(row.get("analysis_text") or ""))
        influence = 0.4 + 0.6 * heat_score
        weighted_sentiment = sentiment_score * influence
        scored_rows.append(
            {
                "aweme_id": (row.get("aweme_id") or "").strip(),
                "creator": (row.get("creator") or "").strip(),
                "create_time": str(row.get("create_time") or ""),
                "digg_count": _safe_int(row.get("digg_count")),
                "comment_count": _safe_int(row.get("comment_count")),
                "collect_count": _safe_int(row.get("collect_count")),
                "analysis_text": str(row.get("analysis_text") or "").strip(),
                "heat_score": round(heat_score, 4),
                "sentiment_score": round(sentiment_score, 4),
                "weighted_sentiment": round(weighted_sentiment, 4),
            }
        )

    heat_values = [item["heat_score"] for item in scored_rows]
    sentiment_values = [item["sentiment_score"] for item in scored_rows]
    weighted_values = [item["weighted_sentiment"] for item in scored_rows]

    avg_heat = float(sum(heat_values) / len(heat_values))
    avg_sentiment = float(sum(sentiment_values) / len(sentiment_values))
    sentiment_dispersion = (
        float(statistics.pstdev(sentiment_values)) if len(sentiment_values) > 1 else 0.0
    )
    weighted_sentiment = float(sum(weighted_values) / len(weighted_values))

    final_score = 50.0 + weighted_sentiment * 35.0 + (avg_heat - 0.5) * 25.0
    final_score = round(_clamp(final_score, 0.0, 100.0), 1)
    sentiment_level, investment_advice = _map_score_to_level_and_advice(final_score)
    risk_note = _build_risk_note(avg_sentiment, sentiment_dispersion, avg_heat)

    sorted_key = sorted(
        scored_rows,
        key=lambda item: abs(item["sentiment_score"]) * (0.5 + item["heat_score"]),
        reverse=True,
    )
    key_videos = []
    for item in sorted_key[:3]:
        brief = (item["analysis_text"] or "")[:120]
        key_videos.append(
            {
                "aweme_id": item["aweme_id"],
                "creator": item["creator"],
                "create_time": item["create_time"],
                "digg_count": item["digg_count"],
                "comment_count": item["comment_count"],
                "collect_count": item["collect_count"],
                "heat_score": item["heat_score"],
                "sentiment_score": item["sentiment_score"],
                "analysis_brief": brief,
            }
        )

    advice_reason = (
        f"样本{len(scored_rows)}条，平均热度{avg_heat:.2f}，"
        f"平均情绪倾向{avg_sentiment:+.2f}，分歧度{sentiment_dispersion:.2f}。"
    )

    return {
        "generated_at": generated_at,
        "scope_name": scope_name,
        "video_count": len(scored_rows),
        "raw_video_count": len(video_rows),
        "avg_heat": round(avg_heat, 4),
        "avg_sentiment": round(avg_sentiment, 4),
        "sentiment_dispersion": round(sentiment_dispersion, 4),
        "final_score": final_score,
        "sentiment_level": sentiment_level,
        "investment_advice": investment_advice,
        "advice_reason": advice_reason,
        "risk_note": risk_note,
        "key_videos": key_videos,
    }


def format_investment_report_text(report: Dict[str, Any]) -> str:
    """将投资建议报告格式化为邮件可读文本。"""
    lines = [
        f"投资建议：{report.get('investment_advice', '持有/观望')}（{report.get('sentiment_level', '中性')}）",
        f"综合评分：{report.get('final_score', 50.0)} / 100",
        f"样本范围：{report.get('scope_name', '本次新增视频')}",
        f"样本数量：{report.get('video_count', 0)} 条",
        f"结论依据：{report.get('advice_reason', '')}",
        f"风险提示：{report.get('risk_note', '')}",
    ]

    key_videos = report.get("key_videos") or []
    for item in key_videos[:2]:
        lines.append(
            "重点视频："
            f"{item.get('aweme_id', '')}，"
            f"点赞{item.get('digg_count', 0)}，"
            f"评论{item.get('comment_count', 0)}，"
            f"收藏{item.get('collect_count', 0)}，"
            f"情绪倾向{item.get('sentiment_score', 0.0):+.2f}。"
        )

    return "\n".join(lines)


def _extract_report_row(row: Dict[str, Any], creator_name: str) -> Dict[str, Any]:
    """提取分析报告所需最小字段。"""
    return {
        "aweme_id": (row.get("aweme_id") or "").strip(),
        "create_time": row.get("create_time") or "",
        "digg_count": row.get("digg_count") or "0",
        "comment_count": row.get("comment_count") or "0",
        "collect_count": row.get("collect_count") or "0",
        "analysis_text": row.get("analysis_text") or "",
        "creator": creator_name,
    }


def _persist_report(report: Dict[str, Any]) -> Dict[str, Any]:
    """落盘最新投资建议报告并返回包含路径的报告。"""
    out_dir = _storage_analysis_dir()
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "latest_investment_report.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    report["report_path"] = out_path
    return report


def analyze_pending_videos_in_csv(config: AppConfig, only_after: Optional[datetime] = None) -> Dict[str, Any]:
    """扫描作者 CSV 补齐分析列，并返回本次聚合投资建议。"""
    _ = config  # 预留给后续按配置动态切换策略
    videos_dir = _storage_videos_dir()
    if not os.path.isdir(videos_dir):
        logger.info("videos dir does not exist, skip analysis")
        report = build_investment_report([], scope_name="本次新增视频")
        return _persist_report(report)

    files = [f for f in os.listdir(videos_dir) if f.lower().endswith(".csv")]
    if not files:
        logger.info("no video csv files found")
        report = build_investment_report([], scope_name="本次新增视频")
        return _persist_report(report)

    report_rows: List[Dict[str, Any]] = []
    fallback_rows: List[Dict[str, Any]] = []
    newly_analyzed_count = 0
    boundary_ts = int((datetime.now() - timedelta(hours=24)).timestamp())

    for filename in files:
        csv_path = os.path.join(videos_dir, filename)
        creator_name = os.path.splitext(filename)[0]
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
                if not analyzed_at:
                    analysis_text, llm_cents = _analyze_row(row, config)
                    row["analysis_text"] = analysis_text
                    row["llm_cents"] = str(llm_cents)
                    row["analyzed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    analyzed_at = row["analyzed_at"]
                    newly_analyzed_count += 1
                    updated = True

                analyzed_time = _parse_dt(analyzed_at)
                if not analyzed_time:
                    continue

                row_min = _extract_report_row(row, creator_name)
                if only_after is not None and analyzed_time > only_after:
                    report_rows.append(row_min)
                else:
                    create_ts = _safe_int(row.get("create_time") or "0")
                    if create_ts >= boundary_ts:
                        fallback_rows.append(row_min)

            if updated:
                with open(csv_path, "w", encoding="utf-8", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=header)
                    writer.writeheader()
                    for row in rows:
                        writer.writerow({k: row.get(k, "") for k in header})
                logger.info(f"updated analyzed rows in {filename}")
        except Exception as exc:
            logger.error(f"analyze csv failed file={filename} err={exc}")

    scope = "本次新增视频"
    used_rows = report_rows
    if not used_rows and fallback_rows:
        used_rows = fallback_rows
        scope = "近24小时已分析视频"

    report = build_investment_report(used_rows, scope_name=scope)
    report["newly_analyzed_count"] = newly_analyzed_count
    report["source_csv_count"] = len(files)
    report = _persist_report(report)
    logger.info(
        "investment report generated "
        f"videos={report.get('video_count')} score={report.get('final_score')} advice={report.get('investment_advice')}"
    )
    return report
