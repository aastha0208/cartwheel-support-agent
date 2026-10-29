"""Agreement, proxy share, and cost for a range of cascade thresholds (Homework 9 Part D).

Offline: reads the saved proxy answers (cascade/run_proxy.py) and makes no model
calls. The cascade keeps the proxy's verdict when its confidence is at or above
the threshold and uses the oracle's saved verdict otherwise. An answer with no
usable verdict or confidence goes to the oracle.

Proxy cost uses the token counts the LLM API returned. The HW5 oracle runs did
not save token counts, so the oracle's cost per verdict is estimated with the
gpt-4o-mini tokenizer from its prompt, wrapper, trace text, and saved critique,
billed at the full input price (a lower bound: DocETL's own system prompt and
schema text are not counted).

    uv run python cascade/thresholds.py
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import tiktoken

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cascade"))

from run_proxy import INSTRUCTIONS, ORACLE_ID, PROXY_MODEL, RESULTS_DIR, _trace_text, load_store_traces  # noqa: E402

PRICES = json.loads((ROOT / "optimize" / "config.json").read_text())[
    "prices_per_million_tokens_usd"
]
ORACLE_MODEL = "gpt-4o-mini"
THRESHOLDS = [0.0, 0.55, 0.6, 0.62, 0.64, 0.66, 0.68, 0.7, 0.72, 0.74, 0.76, 0.78, 0.8, 1.0]
COLUMNS = [
    "threshold",
    "agreement_with_oracle",
    "agreement_with_human_labels",
    "proxy_share",
    "cost_per_1000_verdicts_usd",
]


def load_records(split: str) -> list[dict]:
    path = RESULTS_DIR / f"proxy_{split}.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def proxy_cost(record: dict) -> float:
    p = PRICES[PROXY_MODEL]
    cached = record["cached_input_tokens"]
    return (
        (record["input_tokens"] - cached) * p["input"]
        + cached * p["cached_input"]
        + record["output_tokens"] * p["output"]
    ) / 1_000_000


def oracle_costs(trace_ids: list[str]) -> dict[str, float]:
    """Estimated cost of one oracle verdict per trace (see the module docstring)."""
    enc = tiktoken.get_encoding("o200k_base")
    oracle = json.loads((ROOT / "analysis" / "state" / "judges" / f"{ORACLE_ID}.json").read_text(encoding="utf-8"))
    critiques = oracle["critiques"][oracle["prompt_hash"]]
    store = {trace["trace_id"]: trace for trace in load_store_traces()}
    wrapper = f"\n\n--- Trace to evaluate ---\n\n\n{INSTRUCTIONS}"
    overhead = len(enc.encode('{"critique": "", "result": "Pass"}'))
    p = PRICES[ORACLE_MODEL]
    costs = {}
    for trace_id in trace_ids:
        input_tokens = len(enc.encode(oracle["prompt_text"] + wrapper + _trace_text(trace_id, store)))
        output_tokens = len(enc.encode(critiques[trace_id])) + overhead
        costs[trace_id] = (input_tokens * p["input"] + output_tokens * p["output"]) / 1_000_000
    return costs


def usable(record: dict) -> bool:
    return record["proxy_verdict"] is not None and record["proxy_confidence"] is not None


def evaluate(records: list[dict], threshold: float, oracle_cost: dict[str, float]) -> dict:
    """One row of the threshold table for the given proxy answers."""
    same_oracle = same_human = by_proxy = 0
    cost = 0.0
    for record in records:
        cost += proxy_cost(record)  # the proxy always runs first
        if usable(record) and record["proxy_confidence"] >= threshold:
            verdict = record["proxy_verdict"]
            by_proxy += 1
        else:
            verdict = record["oracle_verdict"]
            cost += oracle_cost[record["trace_id"]]
        same_oracle += verdict == record["oracle_verdict"]
        same_human += verdict == record["human_label"]
    n = len(records)
    return {
        "threshold": threshold,
        "agreement_with_oracle": round(same_oracle / n, 4),
        "agreement_with_human_labels": round(same_human / n, 4),
        "proxy_share": round(by_proxy / n, 4),
        "cost_per_1000_verdicts_usd": round(cost / n * 1000, 4),
        "disagreements_with_oracle": n - same_oracle,
        "n": n,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", default="dev")
    args = parser.parse_args()
    records = load_records(args.split)
    oracle_cost = oracle_costs([record["trace_id"] for record in records])
    rows = [evaluate(records, threshold, oracle_cost) for threshold in THRESHOLDS]
    out = RESULTS_DIR / "thresholds.csv"
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    oracle_only = sum(oracle_cost.values()) / len(records) * 1000
    print(f"{args.split}: {len(records)} verdicts; oracle alone (estimated) ${oracle_only:.4f} per 1,000")
    print(f"{'threshold':>9} {'agree oracle':>12} {'agree human':>11} {'proxy share':>11} {'$/1000':>8} {'disagree':>8}")
    for row in rows:
        print(f"{row['threshold']:>9} {row['agreement_with_oracle']:>12} {row['agreement_with_human_labels']:>11} "
              f"{row['proxy_share']:>11} {row['cost_per_1000_verdicts_usd']:>8} {row['disagreements_with_oracle']:>8}")
    print(f"Wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
