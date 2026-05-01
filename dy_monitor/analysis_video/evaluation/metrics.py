from __future__ import annotations

from typing import Dict, Iterable, List

POSITIVE_HINTS = [
    "看多",
    "上涨",
    "反弹",
    "利好",
    "突破",
    "增持",
    "买入",
    "加仓",
    "重点关注",
    "景气",
    "改善",
    "热度上升",
    "热度较高",
]

NEGATIVE_HINTS = [
    "看空",
    "下跌",
    "利空",
    "风险",
    "回撤",
    "减仓",
    "卖出",
    "规避",
    "高估",
    "泡沫",
    "承压",
    "亏损",
    "热度一般",
]

UP_ADVICES = {
    "加仓/持有",
    "重点关注/择机买入",
}

DOWN_ADVICES = {
    "卖出/规避",
    "减仓/观望",
}

NEUTRAL_ADVICES = {
    "持有/观望",
}


def normalize_direction(value: str) -> str:
    """将标注或预测统一到 up/down/flat/unknown。"""
    text = str(value or "").strip().lower()
    mapping = {
        "up": "up",
        "bull": "up",
        "bullish": "up",
        "rise": "up",
        "涨": "up",
        "上涨": "up",
        "down": "down",
        "bear": "down",
        "bearish": "down",
        "fall": "down",
        "跌": "down",
        "下跌": "down",
        "flat": "flat",
        "neutral": "flat",
        "中性": "flat",
        "观望": "flat",
        "持有": "flat",
    }
    return mapping.get(text, "unknown")


def predict_direction_from_text(text: str) -> str:
    """基于分析文本做三分类方向预测。"""
    normalized = (text or "").strip()
    if not normalized:
        return "flat"

    score = 0
    for keyword in POSITIVE_HINTS:
        if keyword in normalized:
            score += 1
    for keyword in NEGATIVE_HINTS:
        if keyword in normalized:
            score -= 1

    if score >= 2:
        return "up"
    if score <= -2:
        return "down"
    return "flat"


def predict_direction_from_advice(advice: str) -> str:
    """将投资建议映射到方向标签。"""
    text = str(advice or "").strip()
    if text in UP_ADVICES:
        return "up"
    if text in DOWN_ADVICES:
        return "down"
    if text in NEUTRAL_ADVICES:
        return "flat"
    return "flat"


def compute_directional_hit_rate(pairs: Iterable[Dict[str, str]]) -> Dict[str, float]:
    """计算三分类方向命中率。"""
    total = 0
    correct = 0
    skipped = 0
    confusion = {
        "up": {"up": 0, "down": 0, "flat": 0},
        "down": {"up": 0, "down": 0, "flat": 0},
        "flat": {"up": 0, "down": 0, "flat": 0},
    }

    for pair in pairs:
        predicted = normalize_direction(pair.get("predicted_direction", ""))
        actual = normalize_direction(pair.get("actual_direction", ""))
        if predicted == "unknown" or actual == "unknown":
            skipped += 1
            continue
        total += 1
        confusion.setdefault(actual, {"up": 0, "down": 0, "flat": 0})
        confusion[actual][predicted] = confusion[actual].get(predicted, 0) + 1
        if predicted == actual:
            correct += 1

    accuracy = round(correct / total, 4) if total else 0.0
    return {
        "samples": total,
        "correct": correct,
        "skipped": skipped,
        "directional_hit_rate": accuracy,
        "up_precision_proxy": round(
            confusion["up"]["up"] / max(1, confusion["up"]["up"] + confusion["down"]["up"] + confusion["flat"]["up"]),
            4,
        ),
        "down_precision_proxy": round(
            confusion["down"]["down"] / max(1, confusion["down"]["up"] + confusion["down"]["down"] + confusion["flat"]["down"]),
            4,
        ),
        "neutral_precision_proxy": round(
            confusion["flat"]["flat"] / max(1, confusion["flat"]["up"] + confusion["flat"]["down"] + confusion["flat"]["flat"]),
            4,
        ),
    }
