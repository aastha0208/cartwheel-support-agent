"""Recompute the Homework 8 frontier numbers from the saved test results.

Offline, no model calls. Reads optimize/results/test-configuration-N.json
(each case's passes and runs) and rebuilds score, write_pass_5, cost per 100
conversations and the dominated flag, for comparison with frontier.csv.

    uv run python scripts/hw8_recompute_frontier.py
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

from optimize.workflow import RESULTS_DIR, mark_dominated


def main() -> None:
    rows = []
    for number in (1, 2, 3, 4):
        result = json.loads(Path(RESULTS_DIR / f"test-configuration-{number}.json").read_text())
        cases = result["cases"]
        writes = [case for case in cases if case["expected_write"]]
        rows.append(
            {
                "configuration": number,
                "model": result["model"],
                "score": round(statistics.mean(case["passes"] / case["runs"] for case in cases), 6),
                "write_pass_5": statistics.mean(case["passes"] == case["runs"] for case in writes),
                "cost_per_100_conversations_usd": round(
                    result["cost_usd"] / result["evaluated_case_runs"] * 100, 6
                ),
            }
        )
    for row in mark_dominated(rows):
        print(row)


if __name__ == "__main__":
    main()
