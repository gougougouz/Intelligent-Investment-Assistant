import json
from pathlib import Path


base_dir = Path(__file__).resolve().parent
candidates = [
    base_dir / "single_video_output.json",
    base_dir.parent.parent / "single_video_output.json",
]

json_path = next((p for p in candidates if p.exists()), None)
if json_path is None:
    raise FileNotFoundError(
        "未找到 single_video_output.json，请确认文件在 test1 目录或 dy_monitor 根目录。"
    )

with json_path.open("r", encoding="utf-8") as f:
    data = json.load(f)

# 正确字段层级：data -> aweme_detail -> author -> uid
uid = data["data"]["aweme_detail"]["author"]["uid"]

print(uid)