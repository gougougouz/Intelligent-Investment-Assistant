import csv
import json
import os
import statistics
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from analysis_video.config.settings import AppConfig
from analysis_video.providers.comments import fetch_top_comments_by_digg
from analysis_video.utils.logger import get_logger
from analysis_video.utils.video_base64 import video_to_base64

logger = get_logger("analysis.csv_analyzer")

LLM_COVERAGE_THRESHOLD = 0.2
LLM_MIN_COUNT = 1
FINAL_SCORE_BIAS = 11.8

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

_FAULT_REMAINING: Optional[int] = None


def _classify_error_category(exc: Exception) -> str:
    """将异常粗分为 timeout / rate_limit / other。"""
    msg = str(exc).lower()
    timeout_keys = ["timeout", "timed out", "read timeout", "connect timeout"]
    rate_keys = ["429", "rate limit", "too many requests", "throttle", "quota exceeded"]
    if any(k in msg for k in timeout_keys):
        return "timeout"
    if any(k in msg for k in rate_keys):
        return "rate_limit"
    return "other"


def _fault_injection_profile() -> Dict[str, Any]:
    """读取当前故障注入配置，便于写入报告。"""
    return {
        "mode": (os.getenv("ANALYSIS_FAULT_MODE", "none") or "none").strip().lower(),
        "failures": _safe_int(os.getenv("ANALYSIS_FAULT_FAILS", "0")),
        "force_reanalyze": (os.getenv("ANALYSIS_FORCE_REANALYZE", "false") or "false").strip().lower() == "true",
    }


def _should_inject_fault() -> bool:
    """按环境变量控制故障注入次数，返回当前调用是否注入。"""
    global _FAULT_REMAINING
    mode = (os.getenv("ANALYSIS_FAULT_MODE", "none") or "none").strip().lower()
    if mode in {"", "none", "off"}:
        _FAULT_REMAINING = None
        return False

    if _FAULT_REMAINING is None:
        _FAULT_REMAINING = _safe_int(os.getenv("ANALYSIS_FAULT_FAILS", "0"))

    if _FAULT_REMAINING <= 0:
        return False

    _FAULT_REMAINING -= 1
    return True


def _storage_videos_dir() -> str:
    """返回视频 CSV 存储目录。"""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "storage", "videos"))


def _storage_analysis_dir() -> str:
    """返回分析报告存储目录。"""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "storage", "analysis"))


def _ensure_analysis_columns(header: List[str]) -> List[str]:
    """确保 CSV 头包含分析结果字段，并维持调度器所需列顺序。"""
    required = [
        "analysis_text",
        "llm_cents",
        "analyzed_at",
        "analysis_path",
        "llm_final_score",
        "llm_initial_score",
        "logic_quality_L",
        "comment_adjust_factor",
        "hist_min_used",
        "hist_max_used",
        "history_bounds_source",
    ]
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


def _has_value(value: Any) -> bool:
    return str(value or "").strip() != ""


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


def _analyze_with_ark(download_url: str, aweme_id: str) -> tuple[Optional[str], Dict[str, Any]]:
    """尝试调用 Ark 多模态模型，失败时返回 None 和错误分类。"""
    begin = time.perf_counter()
    meta: Dict[str, Any] = {
        "path": "ark_secondary",
        "ok": False,
        "error_category": "none",
        "error": "",
        "latency_ms": 0,
    }
    api_key = os.getenv("ARK_API_KEY", "").strip()
    if not api_key:
        meta["error_category"] = "other"
        meta["error"] = "ARK_API_KEY missing"
        meta["latency_ms"] = round((time.perf_counter() - begin) * 1000.0, 3)
        return None, meta

    try:
        ark_module = __import__("volcenginesdkarkruntime", fromlist=["Ark"])
        Ark = getattr(ark_module, "Ark")
    except Exception:
        logger.warning("Ark SDK not installed, fallback to rule-based summary.")
        meta["error_category"] = "other"
        meta["error"] = "Ark SDK not installed"
        meta["latency_ms"] = round((time.perf_counter() - begin) * 1000.0, 3)
        return None, meta

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
        text = content or None
        if text:
            meta["ok"] = True
        else:
            meta["error_category"] = "other"
            meta["error"] = "empty model response"
        meta["latency_ms"] = round((time.perf_counter() - begin) * 1000.0, 3)
        return text, meta
    except Exception as exc:
        category = _classify_error_category(exc)
        logger.warning(f"Ark analyze failed for aweme_id={aweme_id}: {exc}")
        meta["error_category"] = category
        meta["error"] = str(exc)
        meta["latency_ms"] = round((time.perf_counter() - begin) * 1000.0, 3)
        return None, meta


def _analyze_with_analysis_llm(row: dict, config: AppConfig) -> tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """优先使用 analysis_llm 的单视频算法（多模态+逻辑评分+评论修正）。"""
    begin = time.perf_counter()
    meta: Dict[str, Any] = {
        "path": "analysis_llm_primary",
        "ok": False,
        "error_category": "none",
        "error": "",
        "latency_ms": 0,
    }
    download_url = (row.get("download_url") or "").strip()
    aweme_id = (row.get("aweme_id") or "").strip()
    if not download_url or not aweme_id:
        meta["error_category"] = "other"
        meta["error"] = "missing download_url or aweme_id"
        meta["latency_ms"] = round((time.perf_counter() - begin) * 1000.0, 3)
        return None, meta

    inject_mode = (os.getenv("ANALYSIS_FAULT_MODE", "none") or "none").strip().lower()
    if _should_inject_fault():
        if inject_mode == "timeout":
            simulated = TimeoutError("Simulated timeout on primary track")
        elif inject_mode in {"rate_limit", "ratelimit", "429"}:
            simulated = RuntimeError("Simulated rate limit(429) on primary track")
        else:
            simulated = RuntimeError("Simulated generic primary-track failure")
        category = _classify_error_category(simulated)
        meta["error_category"] = category
        meta["error"] = str(simulated)
        meta["latency_ms"] = round((time.perf_counter() - begin) * 1000.0, 3)
        logger.warning(f"analysis_llm simulated failure, fallback. aweme_id={aweme_id} err={simulated}")
        return None, meta

    try:
        from analysis_video.analysis.analysis_llm import ArkService, analyze_single_video
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"analysis_llm import failed, fallback. aweme_id={aweme_id} err={exc}")
        meta["error_category"] = "other"
        meta["error"] = f"import failed: {exc}"
        meta["latency_ms"] = round((time.perf_counter() - begin) * 1000.0, 3)
        return None, meta

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
            meta["error_category"] = "other"
            meta["error"] = "empty analysis_text"
            meta["latency_ms"] = round((time.perf_counter() - begin) * 1000.0, 3)
            return None, meta
        meta["ok"] = True
        meta["latency_ms"] = round((time.perf_counter() - begin) * 1000.0, 3)
        payload = {
            "analysis_text": text,
            "llm_cents": max(1, llm_cents),
            "llm_final_score": result.get("final_score", ""),
            "llm_initial_score": result.get("initial_score", ""),
            "logic_quality_L": result.get("logic_quality_L", ""),
            "comment_adjust_factor": result.get("comment_adjust_factor", ""),
            "hist_min_used": result.get("hist_min_used", ""),
            "hist_max_used": result.get("hist_max_used", ""),
            "history_bounds_source": result.get("history_bounds_source", ""),
        }
        return payload, meta
    except Exception as exc:  # noqa: BLE001
        category = _classify_error_category(exc)
        logger.warning(f"analysis_llm analyze failed, fallback. aweme_id={aweme_id} err={exc}")
        meta["error_category"] = category
        meta["error"] = str(exc)
        meta["latency_ms"] = round((time.perf_counter() - begin) * 1000.0, 3)
        return None, meta


def _analyze_row(row: dict, config: AppConfig) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """分析单条视频记录，返回 (分析结果, 容灾元信息)。"""
    aweme_id = (row.get("aweme_id") or "").strip()
    download_url = (row.get("download_url") or "").strip()

    llm_result, llm_meta = _analyze_with_analysis_llm(row, config)
    if llm_result:
        return llm_result, {
            "analysis_path": "analysis_llm_primary",
            "degraded": False,
            "primary": llm_meta,
            "secondary": None,
            "fallback_reason": "",
        }

    if download_url:
        ark_text, ark_meta = _analyze_with_ark(download_url, aweme_id)
        if ark_text:
            return {"analysis_text": ark_text, "llm_cents": 10}, {
                "analysis_path": "ark_secondary",
                "degraded": True,
                "primary": llm_meta,
                "secondary": ark_meta,
                "fallback_reason": llm_meta.get("error_category", "other"),
            }
    else:
        ark_meta = {
            "path": "ark_secondary",
            "ok": False,
            "error_category": "other",
            "error": "missing download_url",
            "latency_ms": 0,
        }

    fallback_reason = llm_meta.get("error_category") or ark_meta.get("error_category") or "other"
    return {"analysis_text": _fallback_summary(row), "llm_cents": 1}, {
        "analysis_path": "fallback_summary",
        "degraded": True,
        "primary": llm_meta,
        "secondary": ark_meta,
        "fallback_reason": fallback_reason,
    }


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
    digg_norm = _clamp(_safe_int(row.get("digg_count")) / 200.0, 0.0, 1.0)
    comment_norm = _clamp(_safe_int(row.get("comment_count")) / 40.0, 0.0, 1.0)
    collect_norm = _clamp(_safe_int(row.get("collect_count")) / 30.0, 0.0, 1.0)
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
            "score_mode": "none",
            "llm_score_count": 0,
            "llm_score_coverage": 0.0,
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
        llm_score_raw = row.get("llm_final_score")
        llm_final_score = _safe_float(llm_score_raw) if _has_value(llm_score_raw) else None
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
                "llm_final_score": llm_final_score,
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

    llm_scores = [
        (item["llm_final_score"], 0.7 + 0.3 * item["heat_score"])
        for item in scored_rows
        if item.get("llm_final_score") is not None
    ]
    llm_score_count = len(llm_scores)
    llm_coverage = round(llm_score_count / len(scored_rows), 4)
    use_llm = llm_score_count >= max(LLM_MIN_COUNT, int(len(scored_rows) * LLM_COVERAGE_THRESHOLD))

    if use_llm:
        weight_sum = float(sum(weight for _, weight in llm_scores)) or 1.0
        llm_weighted_avg = float(sum(score * weight for score, weight in llm_scores)) / weight_sum
        final_score = round(_clamp(llm_weighted_avg + FINAL_SCORE_BIAS, 0.0, 100.0), 1)
        score_mode = "llm_fine"
    else:
        final_score = 50.0 + weighted_sentiment * 35.0 + (avg_heat - 0.5) * 25.0
        final_score = round(_clamp(final_score + FINAL_SCORE_BIAS, 0.0, 100.0), 1)
        score_mode = "csv_heuristic"

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

    if score_mode == "llm_fine":
        advice_reason = (
            f"样本{len(scored_rows)}条，LLM精细评分覆盖{llm_score_count}条（覆盖率{llm_coverage:.0%}），"
            f"平均热度{avg_heat:.2f}，平均情绪倾向{avg_sentiment:+.2f}。"
        )
    else:
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
        "score_bias": FINAL_SCORE_BIAS,
        "score_mode": score_mode,
        "llm_score_count": llm_score_count,
        "llm_score_coverage": llm_coverage,
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
        "llm_final_score": row.get("llm_final_score") or "",
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
    fault_profile = _fault_injection_profile()
    force_reanalyze = bool(fault_profile.get("force_reanalyze"))

    resilience_stats: Dict[str, Any] = {
        "rows_seen": 0,
        "rows_reanalyzed": 0,
        "primary_success": 0,
        "secondary_success": 0,
        "fallback_count": 0,
        "fallback_timeout": 0,
        "fallback_rate_limit": 0,
        "fallback_other": 0,
        "max_latency_ms": 0.0,
    }

    videos_dir = _storage_videos_dir()
    if not os.path.isdir(videos_dir):
        logger.info("videos dir does not exist, skip analysis")
        report = build_investment_report([], scope_name="本次新增视频")
        report["resilience_summary"] = {
            "fault_injection": fault_profile,
            "stats": resilience_stats,
        }
        return _persist_report(report)

    files = [f for f in os.listdir(videos_dir) if f.lower().endswith(".csv")]
    if not files:
        logger.info("no video csv files found")
        report = build_investment_report([], scope_name="本次新增视频")
        report["resilience_summary"] = {
            "fault_injection": fault_profile,
            "stats": resilience_stats,
        }
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
                resilience_stats["rows_seen"] += 1
                analyzed_at = (row.get("analyzed_at") or "").strip()
                analysis_path = str(row.get("analysis_path") or "").strip()
                needs_llm_score = not _has_value(row.get("llm_final_score"))
                should_reanalyze = force_reanalyze or (not analyzed_at) or (
                    needs_llm_score and analysis_path in {"", "analysis_llm_primary"}
                )
                if should_reanalyze:
                    analysis_result, analysis_meta = _analyze_row(row, config)
                    row["analysis_text"] = str(analysis_result.get("analysis_text") or "")
                    row["llm_cents"] = str(analysis_result.get("llm_cents") or 1)
                    row["analysis_path"] = str(analysis_meta.get("analysis_path") or "fallback_summary")
                    row["llm_final_score"] = str(analysis_result.get("llm_final_score") or "")
                    row["llm_initial_score"] = str(analysis_result.get("llm_initial_score") or "")
                    row["logic_quality_L"] = str(analysis_result.get("logic_quality_L") or "")
                    row["comment_adjust_factor"] = str(analysis_result.get("comment_adjust_factor") or "")
                    row["hist_min_used"] = str(analysis_result.get("hist_min_used") or "")
                    row["hist_max_used"] = str(analysis_result.get("hist_max_used") or "")
                    row["history_bounds_source"] = str(analysis_result.get("history_bounds_source") or "")
                    row["analyzed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    analyzed_at = row["analyzed_at"]
                    newly_analyzed_count += 1
                    resilience_stats["rows_reanalyzed"] += 1

                    primary_meta = (analysis_meta or {}).get("primary") or {}
                    secondary_meta = (analysis_meta or {}).get("secondary") or {}
                    path_used = (analysis_meta or {}).get("analysis_path") or "fallback_summary"
                    path_used = str(path_used)

                    if path_used == "analysis_llm_primary":
                        resilience_stats["primary_success"] += 1
                    elif path_used == "ark_secondary":
                        resilience_stats["secondary_success"] += 1
                    else:
                        resilience_stats["fallback_count"] += 1
                        reason = str((analysis_meta or {}).get("fallback_reason") or "other").lower()
                        if reason == "timeout":
                            resilience_stats["fallback_timeout"] += 1
                        elif reason == "rate_limit":
                            resilience_stats["fallback_rate_limit"] += 1
                        else:
                            resilience_stats["fallback_other"] += 1

                    latency_values = [
                        _safe_float(primary_meta.get("latency_ms", 0.0)),
                        _safe_float(secondary_meta.get("latency_ms", 0.0)),
                    ]
                    max_latency = max(latency_values) if latency_values else 0.0
                    resilience_stats["max_latency_ms"] = max(
                        _safe_float(resilience_stats.get("max_latency_ms", 0.0)),
                        max_latency,
                    )
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
    report["resilience_summary"] = {
        "fault_injection": fault_profile,
        "stats": {
            **resilience_stats,
            "degrade_ratio": round(
                (_safe_float(resilience_stats.get("fallback_count", 0.0)) / max(1, _safe_float(resilience_stats.get("rows_reanalyzed", 0.0)))),
                4,
            ),
        },
    }
    report = _persist_report(report)
    logger.info(
        "investment report generated "
        f"videos={report.get('video_count')} score={report.get('final_score')} advice={report.get('investment_advice')}"
    )
    return report
