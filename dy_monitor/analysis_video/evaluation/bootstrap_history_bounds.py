from __future__ import annotations

import json
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from analysis_video.analysis.history_bounds import HISTORY_BOUNDS_PATH, bootstrap_history_bounds


def main() -> None:
    bounds = bootstrap_history_bounds(lookback_days=7)
    print(json.dumps(bounds, ensure_ascii=False, indent=2))
    print(f"history bounds saved to: {HISTORY_BOUNDS_PATH}")


if __name__ == "__main__":
    main()
