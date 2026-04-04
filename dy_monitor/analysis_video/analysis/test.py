"""批量测试视频：自动补齐缺失字段并调用分析主流程。"""

import base64
import hashlib
import json
from pathlib import Path
from typing import Dict, List

from analysis_llm import run_pipeline


# 目录
VIDEO_DIR = Path(r"E:\AI\Intelligent Investment Assistant\video")
INPUT_PATH = Path("multi_video_input.json")
OUTPUT_PATH = Path("final_result_multi_video.json")

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}
AUTH_TYPES = ["普通用户", "垂类财经博主", "券商认证", "基金从业认证"]


def file_to_base64(video_path: Path) -> str:
    return base64.b64encode(video_path.read_bytes()).decode("utf-8")


def stable_int(seed_text: str, min_val: int, max_val: int) -> int:
    """基于文件名生成稳定伪随机整数，避免每次测试数据波动。"""
    digest = hashlib.md5(seed_text.encode("utf-8")).hexdigest()
    value = int(digest[:8], 16)
    return min_val + (value % (max_val - min_val + 1))


def stable_float(seed_text: str, min_val: float, max_val: float, precision: int = 2) -> float:
    digest = hashlib.md5(seed_text.encode("utf-8")).hexdigest()
    value = int(digest[8:16], 16) / 0xFFFFFFFF
    result = min_val + (max_val - min_val) * value
    return round(result, precision)


def build_comments(video_stem: str, idx: int) -> List[Dict[str, object]]:
    like_1 = stable_int(f"{video_stem}-c1", 200, 1000)
    like_2 = stable_int(f"{video_stem}-c2", 200, 1000)

    return [
        {
            "comment_id": f"cmt_{idx:03d}_01",
            "content": "机器人产业链景气度在抬升，龙头公司值得继续跟踪。",
            "like_count": like_1,
        },
        {
            "comment_id": f"cmt_{idx:03d}_02",
            "content": "短期波动可能加大，建议关注业绩兑现和估值匹配度。",
            "like_count": like_2,
        },
    ]


def build_video_record(video_path: Path, idx: int) -> Dict[str, object]:
    stem = video_path.stem
    fan_count = stable_int(f"{stem}-fan", 500_000, 2_000_000)
    like_count = stable_int(f"{stem}-like", 800, 3_000)
    hist_acc = stable_float(f"{stem}-hist", 0.55, 0.98, precision=2)
    auth_type = AUTH_TYPES[stable_int(f"{stem}-auth", 0, len(AUTH_TYPES) - 1)]

    return {
        "video_id": f"video_local_{idx:03d}",
        "base64_str": file_to_base64(video_path),
        "target_stock_or_sector": "机器人行业股票",
        "fan_count": fan_count,
        "like_count": like_count,
        "auth_type": auth_type,
        "hist_acc": hist_acc,
        "top_comments": build_comments(stem, idx),
    }


def build_input_file(video_dir: Path, input_path: Path) -> None:
    if not video_dir.exists() or not video_dir.is_dir():
        raise FileNotFoundError(f"视频目录不存在或不是目录: {video_dir}")

    video_files = sorted(
        p for p in video_dir.iterdir() if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS
    )
    if not video_files:
        raise FileNotFoundError(
            f"目录内未找到视频文件，支持格式: {', '.join(sorted(VIDEO_EXTENSIONS))}"
        )

    payload = [build_video_record(video_path, idx + 1) for idx, video_path in enumerate(video_files)]
    input_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[输入构建完成] 共{len(payload)}条视频，已写入: {input_path}")


def main() -> None:
    build_input_file(VIDEO_DIR, INPUT_PATH)
    run_pipeline(str(INPUT_PATH), str(OUTPUT_PATH))


if __name__ == "__main__":
    main()
