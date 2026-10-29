"""Check the locked cascade threshold once on the HW5 test labels (Homework 9 Part D).

Offline: reads cascade/results/proxy_test.jsonl and makes no model calls.

    uv run python cascade/check.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cascade"))

from run_proxy import ORACLE_ID, PROXY_MODEL, RESULTS_DIR  # noqa: E402
from thresholds import evaluate, load_records, oracle_costs  # noqa: E402

THRESHOLD = 0.0  # chosen on dev before this check; never changed afterwards
REQUIREMENT = 0.90  # minimum agreement with the oracle, chosen before any proxy result


def main() -> None:
    records = load_records("test")
    row = evaluate(records, THRESHOLD, oracle_costs([record["trace_id"] for record in records]))
    disagreements = [
        {
            "trace_id": record["trace_id"],
            "proxy_verdict": record["proxy_verdict"],
            "proxy_confidence": record["proxy_confidence"],
            "oracle_verdict": record["oracle_verdict"],
            "human_label": record["human_label"],
        }
        for record in records
        if record["proxy_verdict"] != record["oracle_verdict"]
    ]
    result = {
        "split": "test",
        "proxy_model": PROXY_MODEL,
        "oracle": ORACLE_ID,
        "threshold": THRESHOLD,
        "agreement_requirement": REQUIREMENT,
        "n": row["n"],
        "agreement_with_oracle": row["agreement_with_oracle"],
        "disagreements_with_oracle": row["disagreements_with_oracle"],
        "agreement_with_human_labels": row["agreement_with_human_labels"],
        "proxy_share": row["proxy_share"],
        "cost_per_1000_verdicts_usd": row["cost_per_1000_verdicts_usd"],
        "meets_requirement": row["agreement_with_oracle"] >= REQUIREMENT,
        "disagreements": disagreements,
    }
    out = RESULTS_DIR / "check.json"
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "disagreements"}, indent=2))
    print(f"Wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
