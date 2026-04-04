import argparse
import json
from pathlib import Path


def keep_top_digg_comments(input_path: Path, output_path: Path, top_n: int) -> int:
    with input_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    comments = payload.get("data", {}).get("comments", [])
    if not isinstance(comments, list):
        raise ValueError("JSON 中 data.comments 不是列表，无法处理。")

    # 按点赞数从高到低排序；缺失或异常值按 0 处理
    sorted_comments = sorted(
        comments,
        key=lambda c: int(c.get("digg_count", 0)) if isinstance(c, dict) else 0,
        reverse=True,
    )

    top_comments = sorted_comments[:top_n]
    payload["data"]["comments"] = top_comments

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return len(top_comments)


def main() -> None:
    base_dir = Path(__file__).resolve().parent

    parser = argparse.ArgumentParser(description="保留 digg_count 最高的前 N 条评论")
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        default=base_dir / "single_video_comments_output.json",
        help="输入 JSON 文件路径",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=base_dir / "single_video_comments_top20.json",
        help="输出 JSON 文件路径",
    )
    parser.add_argument(
        "-n",
        "--top-n",
        type=int,
        default=20,
        help="保留的评论数量，默认 20",
    )

    args = parser.parse_args()

    if args.top_n <= 0:
        raise ValueError("top-n 必须大于 0")
    if not args.input.exists():
        raise FileNotFoundError(f"输入文件不存在: {args.input}")

    kept_count = keep_top_digg_comments(args.input, args.output, args.top_n)
    print(f"处理完成，已保留 digg_count 最高的 {kept_count} 条评论。")
    print(f"输出文件: {args.output}")


if __name__ == "__main__":
    main()
