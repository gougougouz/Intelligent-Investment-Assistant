from __future__ import annotations

import csv
import json
import os
import statistics
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

DEFAULT_HIST_MIN = -3.0
DEFAULT_HIST_MAX = 4.0
HISTORY_BOUNDS_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "storage", "analysis", "history_bounds.json")
)

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

_CACHED_BOUNDS: Optional[Dict[str, Any]] = None


def _storage_videos_dir() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "storage", "videos"))


def _safe_int(value: Any) -> int:
    try:
        return int((value or "0").strip())
    except Exception:
        return 0


def _safe_float(value: Any) -> float:
    try:
        return float(str(value or "0").strip())
    except Exception:
        return 0.0


def _clamp(value: float, low: float, high: float) -> float:
    if value < low:
        return low
    if value > high:
        return high
    return value


def _parse_dt(value: Any) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def _default_payload(source: str, lookback_days: int, sample_count: int = 0) -> Dict[str, Any]:
    return {
        "hist_min": DEFAULT_HIST_MIN,
        "hist_max": DEFAULT_HIST_MAX,
        "source": source,
        "lookback_days": lookback_days,
        "sample_count": sample_count,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "method": "default_fallback",
    }


def _parse_row_day(row: Dict[str, Any]) -> Optional[date]:
    create_ts = _safe_int(row.get("create_time") or "0")
    if create_ts > 0:
        try:
            return datetime.fromtimestamp(create_ts).date()
        except Exception:
            pass

    analyzed_at = _parse_dt(row.get("analyzed_at"))
    if analyzed_at is not None:
        return analyzed_at.date()
    return None


def _load_recent_rows(lookback_days: int, reference_now: Optional[datetime] = None) -> List[Dict[str, Any]]:
    ref = reference_now or datetime.now()
    start_day = (ref - timedelta(days=lookback_days)).date()
    end_day = (ref - timedelta(days=1)).date()
    videos_dir = _storage_videos_dir()
    if not os.path.isdir(videos_dir):
        return []

    rows: List[Dict[str, Any]] = []
    for filename in os.listdir(videos_dir):
        if not filename.lower().endswith(".csv"):
            continue
        csv_path = os.path.join(videos_dir, filename)
        try:
            with open(csv_path, "r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    row_day = _parse_row_day(row)
                    if row_day is None or row_day < start_day or row_day > end_day:
                        continue
                    row["_source_file"] = filename
                    row["_score_day"] = row_day.isoformat()
                    rows.append(row)
        except Exception:
            continue
    return rows


def _estimate_text_sentiment(text: str) -> float:
    normalized = (text or "").strip()
    if not normalized:
        return 0.0

    score = 0.0
    for keyword in POSITIVE_HINTS:
        if keyword in normalized:
            score += 0.18
    for keyword in NEGATIVE_HINTS:
        if keyword in normalized:
            score -= 0.18

    if "热度上升" in normalized or "热度较高" in normalized:
        score += 0.08
    if "卖出/规避" in normalized or "减仓/观望" in normalized:
        score -= 0.12

    return round(_clamp(score, -1.0, 1.0), 3)


def _interaction_heat(row: Dict[str, Any]) -> float:
    digg_norm = _clamp(_safe_int(row.get("digg_count")) / 5000.0, 0.0, 1.0)
    comment_norm = _clamp(_safe_int(row.get("comment_count")) / 500.0, 0.0, 1.0)
    collect_norm = _clamp(_safe_int(row.get("collect_count")) / 300.0, 0.0, 1.0)
    return round(digg_norm * 0.55 + comment_norm * 0.30 + collect_norm * 0.15, 4)


def estimate_proxy_raw_score(row: Dict[str, Any]) -> float:
    """基于上一周样本的最小代理分，用于历史极值初始化。"""
    heat_score = _interaction_heat(row)
    text_score = _estimate_text_sentiment(str(row.get("analysis_text") or ""))
    proxy = (text_score * 2.8) + ((heat_score - 0.5) * 2.2)
    return round(_clamp(proxy, -6.0, 6.0), 4)


def _build_daily_initial_scores(
    rows: List[Dict[str, Any]],
    lookback_days: int,
    reference_now: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    ref_day = (reference_now or datetime.now()).date()
    day_list = [ref_day - timedelta(days=offset) for offset in range(lookback_days, 0, -1)]
    buckets: Dict[date, List[float]] = {day: [] for day in day_list}

    for row in rows:
        row_day = _parse_row_day(row)
        if row_day not in buckets:
            continue
        buckets[row_day].append(estimate_proxy_raw_score(row))

    out: List[Dict[str, Any]] = []
    for day in day_list:
        values = buckets.get(day, [])
        score = round(statistics.mean(values), 4) if values else 0.0
        out.append(
            {
                "date": day.isoformat(),
                "video_count": len(values),
                "initial_score": score,
            }
        )
    return out


def _build_payload_from_daily_scores(
    daily_scores: List[Dict[str, Any]],
    lookback_days: int,
    source: str,
) -> Dict[str, Any]:
    values = [float(item.get("initial_score", 0.0)) for item in daily_scores]
    hist_min = round(min(values), 4)
    hist_max = round(max(values), 4)
    adjusted = False

    if hist_max <= hist_min:
        adjusted = True
        hist_min = round(hist_min - 0.5, 4)
        hist_max = round(hist_max + 0.5, 4)

    non_empty_days = sum(1 for item in daily_scores if int(item.get("video_count", 0)) > 0)
    return {
        "hist_min": hist_min,
        "hist_max": hist_max,
        "source": source,
        "lookback_days": lookback_days,
        "sample_count": sum(int(item.get("video_count", 0)) for item in daily_scores),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "method": "seven_day_daily_extrema",
        "non_empty_day_count": non_empty_days,
        "daily_initial_scores": daily_scores,
        "score_stats": {
            "min": hist_min,
            "max": hist_max,
            "mean": round(statistics.mean(values), 4),
            "adjusted_for_degenerate_range": adjusted,
        },
    }


def save_history_bounds(bounds: Dict[str, Any], path: str = HISTORY_BOUNDS_PATH) -> Dict[str, Any]:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(bounds, f, ensure_ascii=False, indent=2)
    return bounds


def bootstrap_history_bounds(lookback_days: int = 7, reference_now: Optional[datetime] = None) -> Dict[str, Any]:
    rows = _load_recent_rows(lookback_days, reference_now)
    if not rows:
        bounds = _default_payload("default_no_samples", lookback_days, 0)
        save_history_bounds(bounds)
        global _CACHED_BOUNDS
        _CACHED_BOUNDS = bounds
        return bounds

    daily_scores = _build_daily_initial_scores(rows, lookback_days, reference_now)
    bounds = _build_payload_from_daily_scores(
        daily_scores,
        lookback_days,
        source="seven_day_daily_extrema_bootstrap",
    )
    save_history_bounds(bounds)
    _CACHED_BOUNDS = bounds
    return bounds


def load_history_bounds(auto_bootstrap: bool = True) -> Dict[str, Any]:
    global _CACHED_BOUNDS
    if _CACHED_BOUNDS is not None:
        return dict(_CACHED_BOUNDS)

    if os.path.exists(HISTORY_BOUNDS_PATH):
        try:
            with open(HISTORY_BOUNDS_PATH, "r", encoding="utf-8") as f:
                payload = json.load(f)
            hist_min = _safe_float(payload.get("hist_min", DEFAULT_HIST_MIN))
            hist_max = _safe_float(payload.get("hist_max", DEFAULT_HIST_MAX))
            if hist_max <= hist_min:
                raise ValueError("invalid history bounds")
            payload["hist_min"] = hist_min
            payload["hist_max"] = hist_max
            payload.setdefault("source", "history_file")
            payload.setdefault("method", "loaded_from_file")
            _CACHED_BOUNDS = payload
            return dict(payload)
        except Exception:
            pass

    if auto_bootstrap:
        return bootstrap_history_bounds()

    payload = _default_payload("default_fallback", 7, 0)
    _CACHED_BOUNDS = payload
    return dict(payload)


def history_bounds_tuple(auto_bootstrap: bool = True) -> tuple[float, float, str]:
    payload = load_history_bounds(auto_bootstrap=auto_bootstrap)
    hist_min = _safe_float(payload.get("hist_min", DEFAULT_HIST_MIN))
    hist_max = _safe_float(payload.get("hist_max", DEFAULT_HIST_MAX))
    source = str(payload.get("source", "default"))
    if hist_max <= hist_min:
        return DEFAULT_HIST_MIN, DEFAULT_HIST_MAX, "default_fallback"
    return hist_min, hist_max, source
