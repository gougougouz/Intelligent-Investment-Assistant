from __future__ import annotations

import argparse
import base64
import json
import os
import random
import time
from itertools import combinations
from typing import Any, Dict, List, Tuple

try:
    import numpy as np
except Exception:  # noqa: BLE001
    np = None  # type: ignore[assignment]

try:
    import pandas as pd
except Exception:  # noqa: BLE001
    pd = None  # type: ignore[assignment]

try:
    from .config import (
        ALLOWED_AUTH_TYPES,
        API_RETRY_INTERVAL_SEC,
        API_RETRY_TIMES,
        ARK_API_KEY,
        ARK_BASE_URL,
        COMMENT_ADJUST_CLAMP,
        COMMENT_LIKE_MAX,
        COMMENT_PROMPT,
        EMBEDDING_MODEL_ID,
        FAN_COUNT_MAX,
        HIST_MAX,
        HIST_MIN,
        LOGIC_PROMPT,
        LOGIC_QUALITY_FLOOR,
        LOGIC_QUALITY_FLOOR_CERTAINTY,
        LOGIC_QUALITY_THRESHOLD,
        MULTIMODAL_PROMPT,
        RAW_SENTIMENT_WEIGHT_AUDIO,
        RAW_SENTIMENT_WEIGHT_TEXT,
        RAW_SENTIMENT_WEIGHT_VISUAL,
        SENTIMENT_LEVEL_MAPPING,
        TARGET_STOCK_OR_SECTOR,
        TEXT_MODEL_ID,
        VIDEO_LIKE_MAX,
        VISION_MODEL_ID,
    )
except ImportError:
    from config import (
        ALLOWED_AUTH_TYPES,
        API_RETRY_INTERVAL_SEC,
        API_RETRY_TIMES,
        ARK_API_KEY,
        ARK_BASE_URL,
        COMMENT_ADJUST_CLAMP,
        COMMENT_LIKE_MAX,
        COMMENT_PROMPT,
        EMBEDDING_MODEL_ID,
        FAN_COUNT_MAX,
        HIST_MAX,
        HIST_MIN,
        LOGIC_PROMPT,
        LOGIC_QUALITY_FLOOR,
        LOGIC_QUALITY_FLOOR_CERTAINTY,
        LOGIC_QUALITY_THRESHOLD,
        MULTIMODAL_PROMPT,
        RAW_SENTIMENT_WEIGHT_AUDIO,
        RAW_SENTIMENT_WEIGHT_TEXT,
        RAW_SENTIMENT_WEIGHT_VISUAL,
        SENTIMENT_LEVEL_MAPPING,
        TARGET_STOCK_OR_SECTOR,
        TEXT_MODEL_ID,
        VIDEO_LIKE_MAX,
        VISION_MODEL_ID,
    )

try:
    from volcenginesdkarkruntime import Ark
except ImportError:
    Ark = None  # type: ignore[assignment]

try:
    from .history_bounds import history_bounds_tuple
except ImportError:
    try:
        from history_bounds import history_bounds_tuple  # type: ignore[no-redef]
    except ImportError:
        def history_bounds_tuple(auto_bootstrap: bool = True) -> tuple[float, float, str]:  # type: ignore[no-redef]
            return HIST_MIN, HIST_MAX, "default_fallback"


def to_float(value: Any, field_name: str) -> float:
    """
    将任意数值安全转换为 float。

    输入：
    - value: 原始值
    - field_name: 字段名（用于报错定位）

    输出：
    - 转换后的 float 值
    """
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"字段 {field_name} 不是有效数值：{value}") from exc


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def normalize_logic_quality(
    logic_quality_l: float,
    text_certainty: float,
    full_text: str,
) -> float:
    if logic_quality_l <= 0.0:
        if full_text.strip() and text_certainty >= LOGIC_QUALITY_FLOOR_CERTAINTY:
            return LOGIC_QUALITY_FLOOR
        return 0.0
    return clamp(logic_quality_l, 0.0, 1.0)


def safe_json_loads(text: str) -> Dict[str, Any]:
    """
    解析模型返回的 JSON 字符串，自动处理可能存在的代码块包裹。

    输入：
    - text: 模型返回文本

    输出：
    - 解析后的 dict
    """
    if text is None:
        raise ValueError("模型返回为空，无法解析 JSON")

    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"模型返回 JSON 解析失败：{cleaned}") from exc


def call_with_retry(func, *args, **kwargs):
    """
    通用重试执行器：API 调用失败自动重试。

    输入：
    - func: 待执行函数
    - args/kwargs: 函数参数

    输出：
    - 函数成功执行后的返回值
    """
    fault_mode = (os.getenv("ANALYSIS_FAULT_MODE", "none") or "none").strip().lower()
    fault_remain = int((os.getenv("ANALYSIS_FAULT_FAILS", "0") or "0").strip() or 0)
    backoff_base = float((os.getenv("API_RETRY_INTERVAL_SEC", str(API_RETRY_INTERVAL_SEC)) or API_RETRY_INTERVAL_SEC))

    def _classify_error(exc: Exception) -> str:
        msg = str(exc).lower()
        timeout_keys = ["timeout", "timed out", "read timeout", "connect timeout"]
        rate_keys = ["429", "rate limit", "too many requests", "throttle", "quota exceeded"]
        if any(k in msg for k in timeout_keys):
            return "timeout"
        if any(k in msg for k in rate_keys):
            return "rate_limit"
        return "other"

    def _maybe_inject_fault(fail_idx: int) -> None:
        nonlocal fault_remain
        if fault_mode in {"", "none", "off"}:
            return
        if fault_remain <= 0:
            return
        fault_remain -= 1
        if fault_mode == "timeout":
            raise TimeoutError(f"Injected timeout at retry={fail_idx + 1}")
        if fault_mode in {"rate_limit", "ratelimit", "429"}:
            raise RuntimeError(f"Injected rate limit(429) at retry={fail_idx + 1}")
        # mixed 模式在 timeout 与 rate_limit 之间随机切换。
        if random.random() < 0.5:
            raise TimeoutError(f"Injected timeout at retry={fail_idx + 1}")
        raise RuntimeError(f"Injected rate limit(429) at retry={fail_idx + 1}")

    last_error = None
    last_category = "other"
    for i in range(API_RETRY_TIMES):
        try:
            _maybe_inject_fault(i)
            return func(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            last_category = _classify_error(exc)
            print(
                f"[警告] API调用失败，第{i + 1}/{API_RETRY_TIMES}次重试，"
                f"category={last_category} err={exc}"
            )
            if i < API_RETRY_TIMES - 1:
                # 指数退避 + 轻微随机抖动，减少雪崩重试。
                delay = backoff_base * (2 ** i) + random.uniform(0, min(0.3, backoff_base))
                time.sleep(delay)

    raise RuntimeError(
        f"API调用连续失败，已重试{API_RETRY_TIMES}次，category={last_category}：{last_error}"
    )


class ArkService:
    """
    Ark 大模型服务封装。

    功能：
    - 多模态视频特征提取
    - 文本逻辑质量评分
    - 评论方向与论证质量评分
    - 文本 Embedding 提取
    """

    def __init__(self) -> None:
        if Ark is None:
            raise ImportError("未安装火山引擎 Ark SDK，请先安装 analysis/requirements.txt 依赖。")
        if not ARK_API_KEY:
            raise ValueError("ARK_API_KEY 未配置，请在 config.py 中填写后重试。")
        self.client = Ark(api_key=ARK_API_KEY, base_url=ARK_BASE_URL)
    def analyze_video_multimodal(self, base64_str: str) -> Dict[str, Any]:
        """
        调用多模态模型，直接传入 base64 视频字符串提取固定字段。

        输入：
        - base64_str: 视频 base64 编码

        输出：
        - 包含 full_text/text_sentiment/text_certainty/audio_sentiment_correction/
          visual_sentiment_correction/finance_credibility_bonus 的字典
        """

        def _do_call() -> Dict[str, Any]:
            response = self.client.chat.completions.create(
                model=VISION_MODEL_ID,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": MULTIMODAL_PROMPT},
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
            content = response.choices[0].message.content
            return safe_json_loads(content)

        return call_with_retry(_do_call)

    def score_logic_quality(self, full_text: str) -> Dict[str, Any]:
        """
        调用文本模型完成逻辑质量评分。

        输入：
        - full_text: 视频完整文本

        输出：
        - 包含 logic_quality_L 的字典
        """

        def _do_call() -> Dict[str, Any]:
            response = self.client.chat.completions.create(
                model=TEXT_MODEL_ID,
                messages=[
                    {"role": "system", "content": LOGIC_PROMPT},
                    {
                        "role": "user",
                        "content": f"请基于以下文本评分：\n{full_text}",
                    },
                ],
            )
            content = response.choices[0].message.content
            return safe_json_loads(content)

        return call_with_retry(_do_call)

    def analyze_comment(self, comment_text: str) -> Dict[str, Any]:
        """
        调用文本模型对评论进行方向与论证质量评分。

        输入：
        - comment_text: 评论文本

        输出：
        - 包含 comment_sentiment_dir/comment_argument_quality_D 的字典
        """

        def _do_call() -> Dict[str, Any]:
            response = self.client.chat.completions.create(
                model=TEXT_MODEL_ID,
                messages=[
                    {"role": "system", "content": COMMENT_PROMPT},
                    {
                        "role": "user",
                        "content": f"请分析该评论：\n{comment_text}",
                    },
                ],
            )
            content = response.choices[0].message.content
            return safe_json_loads(content)

        return call_with_retry(_do_call)

    def get_embedding(self, text: str) -> Any:
        """
        调用 Embedding 模型生成向量。

        输入：
        - text: 待向量化文本

        输出：
        - numpy 向量
        """

        def _extract_vector(response: Any) -> List[float]:
            data = getattr(response, "data", None)
            # 兼容 multimodal_embeddings: response.data 可能是单对象（非 list）
            if data is not None:
                direct_vector = getattr(data, "embedding", None)
                if direct_vector is not None:
                    return direct_vector

                if isinstance(data, dict) and "embedding" in data:
                    return data["embedding"]

                if isinstance(data, (list, tuple)) and data:
                    first = data[0]
                    vector = getattr(first, "embedding", None)
                    if vector is None and isinstance(first, dict):
                        vector = first.get("embedding")
                    if vector is not None:
                        return vector

            if isinstance(response, dict):
                data_dict = response.get("data")
                if isinstance(data_dict, dict) and "embedding" in data_dict:
                    return data_dict["embedding"]
                if isinstance(data_dict, list) and data_dict:
                    first_dict = data_dict[0]
                    if isinstance(first_dict, dict) and "embedding" in first_dict:
                        return first_dict["embedding"]

            raise ValueError("Embedding 响应中未找到向量字段 embedding")

        def _do_call() -> Any:
            if np is None:
                raise ImportError("未安装 numpy，无法执行 embedding 向量计算。")
            try:
                response = self.client.embeddings.create(
                    model=EMBEDDING_MODEL_ID,
                    input=text,
                )
            except Exception as exc:  # noqa: BLE001
                message = str(exc)
                # 部分模型（如视觉多模态 embedding）仅支持 multimodal_embeddings API。
                if "does not support this api" in message and "model" in message:
                    response = self.client.multimodal_embeddings.create(
                        model=EMBEDDING_MODEL_ID,
                        input=[
                            {
                                "type": "text",
                                "text": text,
                            }
                        ],
                    )
                else:
                    raise

            vector = _extract_vector(response)
            return np.array(vector, dtype=float)

        return call_with_retry(_do_call)


def analyze_single_video(
    ark_service: ArkService,
    base64_str: str,
    top_comments: List[Dict[str, Any]],
    fan_count: float,
    like_count: float,
    auth_type: str = "普通用户",
    hist_acc: float = 1.0,
) -> Dict[str, Any]:
    """复用 analysis_llm 的单视频核心算法，返回可直接落库的结果。"""
    if auth_type not in ALLOWED_AUTH_TYPES:
        auth_type = "普通用户"

    # 默认使用 config.py 中的固定历史极值，便于人工先确定初值并长期复用。
    bounds_mode = (os.getenv("HISTORY_BOUNDS_MODE", "static") or "static").strip().lower()
    if bounds_mode in {"dynamic", "file", "bootstrap"}:
        hist_min, hist_max, hist_source = history_bounds_tuple(auto_bootstrap=True)
        if hist_max <= hist_min:
            hist_min, hist_max, hist_source = HIST_MIN, HIST_MAX, "default_fallback"
    else:
        hist_min, hist_max, hist_source = HIST_MIN, HIST_MAX, "static_config"

    multi = ark_service.analyze_video_multimodal(base64_str)
    full_text = str(multi.get("full_text", "")).strip()

    text_sentiment = to_float(multi.get("text_sentiment", 0.0), "text_sentiment")
    text_certainty = to_float(multi.get("text_certainty", 0.0), "text_certainty")
    audio_correction = to_float(
        multi.get("audio_sentiment_correction", 0.0),
        "audio_sentiment_correction",
    )
    visual_correction = to_float(
        multi.get("visual_sentiment_correction", 0.0),
        "visual_sentiment_correction",
    )
    finance_bonus = to_float(
        multi.get("finance_credibility_bonus", 0.0),
        "finance_credibility_bonus",
    )

    logic_resp = ark_service.score_logic_quality(full_text)
    logic_quality_l = to_float(logic_resp.get("logic_quality_L", 0.0), "logic_quality_L")
    logic_quality_l = normalize_logic_quality(logic_quality_l, text_certainty, full_text)

    support_score, oppose_score, valid_comment_count = process_comments(ark_service, top_comments)
    net_argument_sentiment = support_score - oppose_score
    if valid_comment_count <= 0:
        comment_adjust_factor = 0.0
    else:
        comment_adjust_factor = net_argument_sentiment / valid_comment_count
        comment_adjust_factor = clamp(comment_adjust_factor, -COMMENT_ADJUST_CLAMP, COMMENT_ADJUST_CLAMP)

    fan_norm = max(0.0, min(1.0, to_float(fan_count, "fan_count") / FAN_COUNT_MAX))
    like_norm = max(0.0, min(1.0, to_float(like_count, "like_count") / VIDEO_LIKE_MAX))
    base_influence = fan_norm + like_norm

    weight_b = base_influence * max(0.0, logic_quality_l) * max(0.0, to_float(hist_acc, "hist_acc"))
    raw_sentiment = (
        RAW_SENTIMENT_WEIGHT_TEXT * text_sentiment
        + RAW_SENTIMENT_WEIGHT_AUDIO * audio_correction
        + RAW_SENTIMENT_WEIGHT_VISUAL * visual_correction
    )
    raw_sentiment = raw_sentiment * (1 + finance_bonus) * text_certainty
    s_v = weight_b * raw_sentiment

    # 单视频场景下将评论修正直接作用在该视频分值上。
    initial_score = s_v * (1 + comment_adjust_factor)
    final_score = ((initial_score - hist_min) / (hist_max - hist_min)) * 100
    final_score = max(0.0, min(100.0, final_score))
    final_score = round(final_score, 1)
    sentiment_level, investment_advice = map_score_to_level_and_advice(final_score)

    text_brief = (full_text or "").replace("\n", " ").strip()
    if len(text_brief) > 120:
        text_brief = text_brief[:120] + "..."
    analysis_text = (
        f"观点摘要：{text_brief or '模型未抽取到有效文本。'} "
        f"L={logic_quality_l:.2f}，情绪分S_v={s_v:.4f}，评论修正={comment_adjust_factor:+.4f}，"
        f"综合{sentiment_level}（{investment_advice}）。"
    )

    llm_cents = 12 + min(20, len(top_comments))
    return {
        "analysis_text": analysis_text,
        "llm_cents": llm_cents,
        "final_score": final_score,
        "initial_score": round(initial_score, 6),
        "hist_min_used": round(hist_min, 6),
        "hist_max_used": round(hist_max, 6),
        "history_bounds_source": hist_source,
        "logic_quality_L": round(logic_quality_l, 4),
        "S_v": round(s_v, 6),
        "comment_adjust_factor": round(comment_adjust_factor, 6),
        "sentiment_level": sentiment_level,
        "investment_advice": investment_advice,
    }


def validate_comment(comment: Dict[str, Any]) -> None:
    """
    校验单条评论必填字段和类型。

    输入：
    - comment: 评论字典

    输出：
    - 无返回；不合规抛 ValueError
    """
    required = ["comment_id", "content", "like_count"]
    for key in required:
        if key not in comment:
            raise ValueError(f"评论缺失字段：{key}")

    if not isinstance(comment["comment_id"], str):
        raise ValueError("comment_id 必须为字符串")
    if not isinstance(comment["content"], str):
        raise ValueError("content 必须为字符串")
    _ = to_float(comment["like_count"], "comment.like_count")


def validate_video(video: Dict[str, Any]) -> None:
    """
    校验单条视频数据是否符合输入规范。

    输入：
    - video: 视频字典

    输出：
    - 无返回；不合规抛 ValueError
    """
    required = [
        "video_id",
        "base64_str",
        "target_stock_or_sector",
        "fan_count",
        "like_count",
        "auth_type",
        "hist_acc",
        "top_comments",
    ]

    for key in required:
        if key not in video:
            raise ValueError(f"视频缺失字段：{key}")

    if not isinstance(video["video_id"], str):
        raise ValueError("video_id 必须为字符串")
    if not isinstance(video["base64_str"], str):
        raise ValueError("base64_str 必须为字符串")

    # 仅做 base64 字符串合法性检查，严格不落地临时文件。
    try:
        base64.b64decode(video["base64_str"], validate=True)
    except Exception as exc:  # noqa: BLE001
        raise ValueError("base64_str 不是合法Base64字符串") from exc

    if video["target_stock_or_sector"] != TARGET_STOCK_OR_SECTOR:
        raise ValueError(f"target_stock_or_sector 必须为：{TARGET_STOCK_OR_SECTOR}")

    _ = to_float(video["fan_count"], "fan_count")
    _ = to_float(video["like_count"], "like_count")

    if video["auth_type"] not in ALLOWED_AUTH_TYPES:
        raise ValueError(f"auth_type 非法：{video['auth_type']}")

    hist_acc = to_float(video["hist_acc"], "hist_acc")
    if hist_acc < 0 or hist_acc > 1.2:
        raise ValueError("hist_acc 必须在 0~1.2 之间")

    if not isinstance(video["top_comments"], list):
        raise ValueError("top_comments 必须为数组")

    for comment in video["top_comments"]:
        if not isinstance(comment, dict):
            raise ValueError("top_comments 内元素必须为对象")
        validate_comment(comment)


def parse_and_validate_input(input_path: str) -> List[Dict[str, Any]]:
    """
    读取并校验输入 JSON，遇到不合规视频跳过。

    输入：
    - input_path: 输入 JSON 文件路径

    输出：
    - 合规视频列表
    """
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("输入JSON顶层必须是数组，每个元素为一个视频对象")

    valid_videos: List[Dict[str, Any]] = []
    for idx, video in enumerate(data):
        try:
            if not isinstance(video, dict):
                raise ValueError("视频数据必须为对象")
            validate_video(video)
            valid_videos.append(video)
        except ValueError as exc:
            print(f"[数据校验失败] 第{idx + 1}条视频已跳过：{exc}")

    return valid_videos


def process_comments(ark_service: ArkService, comments: List[Dict[str, Any]]) -> Tuple[float, float, int]:
    """
    处理高赞评论并汇总支持/反对论证分。

    输入：
    - ark_service: Ark 服务实例
    - comments: 评论列表

    输出：
    - total_support_score: 支持总论证分
    - total_oppose_score: 反对总论证分
    - valid_comment_count: 有效评论数（过滤 neutral 后）
    """
    total_support_score = 0.0
    total_oppose_score = 0.0
    valid_comment_count = 0

    for comment in comments:
        try:
            analysis = ark_service.analyze_comment(comment["content"])
            direction = str(analysis.get("comment_sentiment_dir", "")).strip().lower()
            argument_quality = to_float(
                analysis.get("comment_argument_quality_D", 0.0),
                "comment_argument_quality_D",
            )

            if direction not in {"support", "oppose", "neutral"}:
                print(
                    f"[评论分析异常] comment_id={comment['comment_id']} 方向字段非法，按 neutral 处理"
                )
                direction = "neutral"

            # 中性评论按要求过滤。
            if direction == "neutral":
                continue

            # 单条评论点赞归一化：comment_like_norm = 评论点赞数 / 1000
            comment_like_norm = clamp(
                to_float(comment["like_count"], "comment.like_count") / COMMENT_LIKE_MAX,
                0.0,
                1.0,
            )
            comment_score = argument_quality * comment_like_norm

            if direction == "support":
                total_support_score += comment_score
            elif direction == "oppose":
                total_oppose_score += comment_score

            valid_comment_count += 1
        except Exception as exc:  # noqa: BLE001
            print(f"[评论处理失败] comment_id={comment.get('comment_id', '未知')}：{exc}，已跳过")

    return total_support_score, total_oppose_score, valid_comment_count


def cosine_similarity(vec1: Any, vec2: Any) -> float:
    """
    计算两个向量的余弦相似度。

    输入：
    - vec1, vec2: numpy 向量

    输出：
    - 余弦相似度（float）
    """
    denom = (np.linalg.norm(vec1) * np.linalg.norm(vec2))
    if denom == 0:
        return 0.0
    return float(np.dot(vec1, vec2) / denom)


def compute_consensus_c(embeddings: List[Any]) -> float:
    """
    计算观点共识度 C：所有向量两两余弦相似度均值，保留2位小数。

    输入：
    - embeddings: 高逻辑视频文本向量列表

    输出：
    - C 值（float）
    """
    if len(embeddings) < 2:
        return 0.0

    sims = [cosine_similarity(a, b) for a, b in combinations(embeddings, 2)]
    if not sims:
        return 0.0
    return round(float(np.mean(sims)), 2)


def map_score_to_level_and_advice(final_score: float) -> Tuple[str, str]:
    """
    将百分制分数映射到固定情绪等级与投资建议。

    输入：
    - final_score: 0~100 的百分制分数

    输出：
    - (情绪等级, 投资建议)
    """
    score_int = int(round(final_score))
    for item in SENTIMENT_LEVEL_MAPPING:
        if item["min"] <= score_int <= item["max"]:
            return item["level"], item["advice"]

    # 容错分支（理论上不会到达）
    return "中性", "持有/观望"


def generate_explain_report(
    high_logic_videos: List[Dict[str, Any]],
    consensus_c: float,
    comment_adjust_factor: float,
    sum_weighted_sentiment: float,
) -> str:
    """
    生成简要可解释性报告，说明结果的核心驱动因素。

    输入：
    - high_logic_videos: 通过逻辑阈值的视频结果
    - consensus_c: 观点共识度
    - comment_adjust_factor: 评论修正因子
    - sum_weighted_sentiment: 高逻辑视频加权情绪和

    输出：
    - 中文简要分析文本
    """
    if not high_logic_videos:
        return "高逻辑质量视频数量为0，核心情绪分主要受缺失有效高质量观点影响。"

    avg_logic = float(np.mean([v["logic_quality_L"] for v in high_logic_videos]))
    strongest_video = max(high_logic_videos, key=lambda x: abs(x["S_v"]))

    report = (
        f"共纳入{len(high_logic_videos)}条高逻辑质量视频，平均逻辑评分L={avg_logic:.2f}；"
        f"高逻辑视频加权情绪和={sum_weighted_sentiment:.4f}，观点共识度C={consensus_c:.2f}，"
        f"评论修正因子={comment_adjust_factor:.4f}。"
        f"贡献最显著的视频为video_id={strongest_video['video_id']}，其单视频情绪分S_v={strongest_video['S_v']:.4f}。"
    )
    return report


def run_pipeline(input_path: str, output_path: str) -> None:
    """
    主流程：执行数据校验、模型提取、评分引擎、结果打印与落盘。

    输入：
    - input_path: 输入 JSON 路径
    - output_path: 输出 JSON 路径

    输出：
    - 无返回；通过 print 输出结果并写入输出文件
    """
    print("=" * 88)
    print("机器人行业股票市场情绪评分任务启动")
    print("=" * 88)

    valid_videos = parse_and_validate_input(input_path)
    if not valid_videos:
        print("[结果] 无合规视频，无法计算市场情绪分数。")
        return

    print(f"[信息] 合规视频数量：{len(valid_videos)}")

    ark_service = ArkService()

    high_logic_results: List[Dict[str, Any]] = []

    total_support_score_all = 0.0
    total_oppose_score_all = 0.0
    total_valid_comment_count_all = 0

    for video in valid_videos:
        video_id = video["video_id"]
        try:
            print(f"\n[处理视频] video_id={video_id}")

            # 步骤2：多模态特征提取（严格直接传 base64_str）
            multi = ark_service.analyze_video_multimodal(video["base64_str"])
            full_text = str(multi.get("full_text", "")).strip()

            text_sentiment = to_float(multi.get("text_sentiment", 0.0), "text_sentiment")
            text_certainty = to_float(multi.get("text_certainty", 0.0), "text_certainty")
            audio_correction = to_float(
                multi.get("audio_sentiment_correction", 0.0),
                "audio_sentiment_correction",
            )
            visual_correction = to_float(
                multi.get("visual_sentiment_correction", 0.0),
                "visual_sentiment_correction",
            )
            finance_bonus = to_float(
                multi.get("finance_credibility_bonus", 0.0),
                "finance_credibility_bonus",
            )

            # 步骤3：逻辑质量评分 L
            logic_resp = ark_service.score_logic_quality(full_text)
            logic_quality_l = to_float(logic_resp.get("logic_quality_L", 0.0), "logic_quality_L")
            logic_quality_l = normalize_logic_quality(logic_quality_l, text_certainty, full_text)

            # 步骤4：评论区论证质量评分汇总（全量参与后续修正）
            support_score, oppose_score, valid_comment_count = process_comments(
                ark_service,
                video["top_comments"],
            )
            total_support_score_all += support_score
            total_oppose_score_all += oppose_score
            total_valid_comment_count_all += valid_comment_count

            print(
                f"[中间结果] L={logic_quality_l:.2f}, 支持分={support_score:.4f}, "
                f"反对分={oppose_score:.4f}, 有效评论={valid_comment_count}"
            )

            # 步骤5-1：仅保留 logic_quality_L >= 阈值
            if logic_quality_l < LOGIC_QUALITY_THRESHOLD:
                print(
                    f"[过滤] video_id={video_id} 的 logic_quality_L={logic_quality_l:.2f} 未超过阈值 "
                    f"{LOGIC_QUALITY_THRESHOLD}，不纳入高逻辑视频集合"
                )
                continue

            # 步骤5-2：基础传播影响力
            fan_norm = clamp(to_float(video["fan_count"], "fan_count") / FAN_COUNT_MAX, 0.0, 1.0)
            like_norm = clamp(to_float(video["like_count"], "like_count") / VIDEO_LIKE_MAX, 0.0, 1.0)
            base_influence = fan_norm + like_norm

            # 步骤5-3：博主最终权重 W_b = base_influence × L × hist_acc
            hist_acc = to_float(video["hist_acc"], "hist_acc")
            weight_b = base_influence * logic_quality_l * hist_acc

            # 步骤5-4：单视频情绪分 S_v
            # raw_sentiment = 0.6*text_sentiment + 0.25*audio + 0.15*visual
            raw_sentiment = (
                RAW_SENTIMENT_WEIGHT_TEXT * text_sentiment
                + RAW_SENTIMENT_WEIGHT_AUDIO * audio_correction
                + RAW_SENTIMENT_WEIGHT_VISUAL * visual_correction
            )
            # raw_sentiment = raw_sentiment × (1 + finance_bonus) × text_certainty
            raw_sentiment = raw_sentiment * (1 + finance_bonus) * text_certainty
            # S_v = W_b × raw_sentiment
            s_v = weight_b * raw_sentiment

            high_logic_results.append(
                {
                    "video_id": video_id,
                    "full_text": full_text,
                    "logic_quality_L": logic_quality_l,
                    "fan_norm": fan_norm,
                    "like_norm": like_norm,
                    "base_influence": base_influence,
                    "W_b": weight_b,
                    "raw_sentiment": raw_sentiment,
                    "S_v": s_v,
                    "text_sentiment": text_sentiment,
                    "text_certainty": text_certainty,
                    "audio_sentiment_correction": audio_correction,
                    "visual_sentiment_correction": visual_correction,
                    "finance_credibility_bonus": finance_bonus,
                }
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[视频处理失败] video_id={video_id}：{exc}，已跳过")

    # 步骤5-5：高逻辑视频加权情绪和
    sum_weighted_sentiment = float(np.sum([x["S_v"] for x in high_logic_results])) if high_logic_results else 0.0

    # 步骤5-6：观点共识度 C（高逻辑视频 full_text Embedding）
    embeddings = []
    for item in high_logic_results:
        try:
            emb = ark_service.get_embedding(item["full_text"])
            embeddings.append(emb)
        except Exception as exc:  # noqa: BLE001
            print(f"[Embedding失败] video_id={item['video_id']}：{exc}，该条不参与共识计算")

    consensus_c = compute_consensus_c(embeddings)

    # 步骤5-7：共识情绪分
    consensus_sentiment = sum_weighted_sentiment * (1 + consensus_c ** 2)

    # 步骤5-8：评论修正因子
    net_argument_sentiment = total_support_score_all - total_oppose_score_all
    if total_valid_comment_count_all == 0:
        comment_adjust_factor = 0.0
    else:
        comment_adjust_factor = net_argument_sentiment / total_valid_comment_count_all
        comment_adjust_factor = clamp(comment_adjust_factor, -COMMENT_ADJUST_CLAMP, COMMENT_ADJUST_CLAMP)

    # 步骤5-9：初始综合分
    initial_score = consensus_sentiment * (1 + comment_adjust_factor)

    # 步骤5-10：百分制映射 + 截断
    final_score = ((initial_score - HIST_MIN) / (HIST_MAX - HIST_MIN)) * 100
    final_score = max(0.0, min(100.0, final_score))
    final_score = round(final_score, 1)

    # 步骤5-11：情绪等级与建议映射
    sentiment_level, investment_advice = map_score_to_level_and_advice(final_score)

    # 步骤5-12：可解释性报告
    explain_report = generate_explain_report(
        high_logic_results,
        consensus_c,
        comment_adjust_factor,
        sum_weighted_sentiment,
    )

    # 结果打印（突出最终市场情绪分数）
    print("\n" + "=" * 88)
    print("机器人行业股票市场情绪评分结果")
    print("=" * 88)
    print(f"高逻辑质量视频数: {len(high_logic_results)}")
    print(f"高逻辑视频加权情绪和 sum_weighted_sentiment: {sum_weighted_sentiment:.4f}")
    print(f"观点共识度 C: {consensus_c:.2f}")
    print(f"共识情绪分 consensus_sentiment: {consensus_sentiment:.4f}")
    print(f"评论修正因子: {comment_adjust_factor:.4f}")
    print(f"初始综合分 initial_score: {initial_score:.4f}")
    print("-" * 88)
    print(f"最终市场情绪分数 final_score: {final_score}")
    print(f"情绪等级: {sentiment_level}")
    print(f"投资建议: {investment_advice}")
    print(f"可解释性报告: {explain_report}")

    if high_logic_results:
        df = pd.DataFrame(high_logic_results)
        print("\n[高逻辑视频明细]")
        print(df[["video_id", "logic_quality_L", "W_b", "raw_sentiment", "S_v"]].to_string(index=False))

    output_data = {
        "target_stock_or_sector": TARGET_STOCK_OR_SECTOR,
        "input_video_count": len(valid_videos),
        "high_logic_video_count": len(high_logic_results),
        "sum_weighted_sentiment": round(sum_weighted_sentiment, 6),
        "consensus_c": consensus_c,
        "consensus_sentiment": round(consensus_sentiment, 6),
        "total_support_score": round(total_support_score_all, 6),
        "total_oppose_score": round(total_oppose_score_all, 6),
        "total_valid_comment_count": total_valid_comment_count_all,
        "comment_adjust_factor": round(comment_adjust_factor, 6),
        "initial_score": round(initial_score, 6),
        "final_score": final_score,
        "sentiment_level": sentiment_level,
        "investment_advice": investment_advice,
        "explain_report": explain_report,
        "high_logic_video_details": high_logic_results,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"\n[输出] 结果已保存至: {output_path}")


def main() -> None:
    """
    命令行入口函数。

    输入：
    - --input: 输入 JSON 文件路径
    - --output: 输出 JSON 文件路径

    输出：
    - 无返回
    """
    parser = argparse.ArgumentParser(description="机器人行业股票市场情绪评分引擎")
    parser.add_argument(
        "--input",
        type=str,
        default="sample_input.json",
        help="输入JSON文件路径",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="final_result.json",
        help="输出JSON文件路径",
    )
    args = parser.parse_args()

    try:
        run_pipeline(args.input, args.output)
    except json.JSONDecodeError as exc:
        print(f"[致命错误] 输入JSON解析失败：{exc}")
    except FileNotFoundError as exc:
        print(f"[致命错误] 输入文件不存在：{exc}")
    except Exception as exc:  # noqa: BLE001
        print(f"[致命错误] 程序执行异常：{exc}")



