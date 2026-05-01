import json
import os
import sys
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from analysis_video.analysis.csv_analyzer import analyze_pending_videos_in_csv
from analysis_video.config import load_config


def _set_env(key: str, value: str) -> None:
    os.environ[key] = value


def run_drill() -> dict:
    scenarios = [
        {"name": "baseline", "mode": "none", "fails": 0},
        {"name": "timeout_storm", "mode": "timeout", "fails": 9999},
        {"name": "rate_limit_storm", "mode": "rate_limit", "fails": 9999},
    ]

    out = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "scenarios": [],
    }

    for scenario in scenarios:
        _set_env("ANALYSIS_FORCE_REANALYZE", "true")
        _set_env("ANALYSIS_FAULT_MODE", scenario["mode"])
        _set_env("ANALYSIS_FAULT_FAILS", str(scenario["fails"]))

        cfg = load_config()
        report = analyze_pending_videos_in_csv(cfg)
        resilience = report.get("resilience_summary") or {}
        stats = resilience.get("stats") or {}

        out["scenarios"].append(
            {
                "name": scenario["name"],
                "fault_mode": scenario["mode"],
                "fault_fails": scenario["fails"],
                "final_score": report.get("final_score"),
                "investment_advice": report.get("investment_advice"),
                "video_count": report.get("video_count"),
                "rows_reanalyzed": stats.get("rows_reanalyzed", 0),
                "fallback_count": stats.get("fallback_count", 0),
                "fallback_timeout": stats.get("fallback_timeout", 0),
                "fallback_rate_limit": stats.get("fallback_rate_limit", 0),
                "degrade_ratio": stats.get("degrade_ratio", 0),
            }
        )

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "storage", "analysis"))
    os.makedirs(base_dir, exist_ok=True)
    out_path = os.path.join(base_dir, "resilience_drill_report.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    return {"report_path": out_path, "result": out}


if __name__ == "__main__":
    result = run_drill()
    print(f"resilience drill report: {result['report_path']}")
