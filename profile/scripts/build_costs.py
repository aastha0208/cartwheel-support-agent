"""Build profile/results/costs.csv: model cost per call site (Homework 9 Part A).

Offline: reads saved traces, run results, and judge records. Makes no model calls.

Customer conversation rows use the token counts the LLM API returned (via
Langfuse or optimize.runner). The judge runs did not save token counts, so
judge rows are estimated with the gpt-4o-mini tokenizer (o200k_base) from the
saved judge prompts, the saved judge inputs, and the saved critiques.
"""

from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path

import tiktoken

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))  # for analysis.helpers
# The saved HW5 judge inputs, as in analysis/run_judges.py (also keeps Langfuse out).
os.environ["CARTWHEEL_JUDGE_TRACE_SOURCE"] = str(
    ROOT / "analysis" / "state" / "hw5_trace_inputs.json"
)
OUT = ROOT / "profile" / "results" / "costs.csv"
PRICES = json.loads((ROOT / "optimize" / "config.json").read_text())[
    "prices_per_million_tokens_usd"
]
ENC = tiktoken.get_encoding("o200k_base")

# Text DocETL adds around the judge prompt (analysis/helpers/scale.py,
# monitoring/run_judges.py). DocETL's own system prompt and output schema are
# not counted, so judge input estimates are a lower bound.
DOCETL_WRAPPER = (
    "\n\n--- Trace to evaluate ---\n\n\n"
    "First write a critique of the trace against the criterion. "
    "Use specific evidence from the provided trace. Then return result "
    "as exactly Pass when the named failure is absent, or Fail when present."
)
# JSON keys and the verdict around each critique.
OUTPUT_OVERHEAD = len(ENC.encode('{"critique": "", "result": "Pass"}'))

COLUMNS = [
    "cost_category", "call_site", "purpose", "model",
    "calls", "input_tokens", "output_tokens", "cost_usd",
]


def tokens(text: str) -> int:
    return len(ENC.encode(text))


def price(model: str, input_tokens: int, output_tokens: int) -> float:
    p = PRICES[model]
    return (input_tokens * p["input"] + output_tokens * p["output"]) / 1_000_000


def read(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def server_agent_row(paths: list[str], purpose: str) -> dict:
    """Scenario runs through the server; tokens and cost from the Langfuse export."""
    generations = [
        obs
        for path in paths
        for trace in read(path)["traces"]
        for obs in trace["observations"]
        if obs["type"] == "GENERATION"
    ]
    (model,) = {g["model"] for g in generations}
    return {
        "cost_category": "customer_conversation",
        "call_site": "server/app.py:215",
        "purpose": purpose,
        "model": model.split("/")[-1],
        "calls": len(generations),
        "input_tokens": sum(g["usageDetails"]["input"] for g in generations),
        "output_tokens": sum(g["usageDetails"]["output"] for g in generations),
        "cost_usd": sum(g["costDetails"]["total"] for g in generations),
    }


def hw6_harbor_rows(judge_input_per_call: float, judge_output_per_call: float) -> list[dict]:
    """HW6 Harbor runs. Agent token totals as recorded in hw6_run_log.md."""
    # (requests, input, output): baselines e-001..e-014, CI run 1, CI run 2,
    # Part E e-014 x15, e-015 baseline.
    runs = [
        (177, 423_970, 38_577),
        (159, 385_242, 37_041),
        (179, 432_310, 39_041),
        (39, 95_841, 8_923),
        (21, 53_307, 5_253),
    ]
    calls = sum(run[0] for run in runs)
    input_tokens = sum(run[1] for run in runs)
    output_tokens = sum(run[2] for run in runs)
    judge_calls = 5 + 5 + 5  # e-009 in the baselines and both CI runs
    judge_input = round(judge_calls * judge_input_per_call)
    judge_output = round(judge_calls * judge_output_per_call)
    return [
        {
            "cost_category": "customer_conversation",
            "call_site": "harbor_adapter (Harbor trial; agent loop in replay/rollout.py:210)",
            "purpose": "HW6 Harbor runs (baselines, 2 CI runs, e-014 x15, e-015); API token "
                       "totals recorded in hw6_run_log.md; cost from optimize/config.json prices",
            "model": "claude-opus-4-6",
            "calls": calls,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": price("claude-opus-4-6", input_tokens, output_tokens),
        },
        {
            "cost_category": "judge",
            "call_site": "harbor_adapter (Harbor verifier, dispute_not_escalated on e-009)",
            "purpose": "HW6 judge calls on e-009 (count from hw6_run_log.md); ESTIMATED tokens "
                       "= HW8 replay judge average per call",
            "model": "gpt-4o-mini",
            "calls": judge_calls,
            "input_tokens": judge_input,
            "output_tokens": judge_output,
            "cost_usd": price("gpt-4o-mini", judge_input, judge_output),
        },
    ]


def hw7_agent_row() -> dict:
    """HW7 after-period agent run; only the Langfuse cost was recorded."""
    return {
        "cost_category": "customer_conversation",
        "call_site": "server/app.py:215",
        "purpose": "HW7 after-period scenario run (50 scenarios, 61 traces); cost recorded by "
                   "Langfuse in hw7_run_log.md; calls and tokens not exported (blank)",
        "model": "claude-opus-4-6",
        "calls": "",
        "input_tokens": "",
        "output_tokens": "",
        "cost_usd": 2.43,
    }


def hw8_agent_rows() -> list[dict]:
    """HW8 optimize.runner runs; tokens from the saved results, one row per model."""
    paths = sorted((ROOT / "optimize" / "results").glob("development-*.json"))
    paths += sorted((ROOT / "optimize" / "results").glob("test-configuration-*.json"))
    by_model: dict[str, dict] = {}
    for path in paths:  # latest-development.json duplicates the final run, so it is skipped
        result = json.loads(path.read_text())
        row = by_model.setdefault(result["model"], {
            "cost_category": "customer_conversation",
            "call_site": "replay/rollout.py:210",
            "purpose": "HW8 optimize.runner runs; tokens from saved results; "
                       "calls = conversations (model calls per conversation not saved)",
            "model": result["model"],
            "calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0,
        })
        row["calls"] += result["evaluated_case_runs"]
        row["input_tokens"] += result["input_tokens"]
        row["output_tokens"] += result["output_tokens"]
        row["cost_usd"] += result["cost_usd"]
    return list(by_model.values())


def hw5_judge_row() -> tuple[dict, float, float]:
    """HW5 dispute_not_escalated runs: v0 dev, v1 dev, v0 dev stability, v0 test."""
    from analysis.helpers.scale import _trace_text, load_store_traces

    store = {t["trace_id"]: t for t in load_store_traces()}
    split = read("analysis/state/splits.json")["dispute_not_escalated"]
    v0 = read("analysis/state/judges/dispute_not_escalated-v0.json")
    v1 = read("analysis/state/judges/dispute_not_escalated-v1.json")
    v0_critiques = v0["critiques"][v0["prompt_hash"]]
    v1_critiques = v1["critiques"][v1["prompt_hash"]]

    # (judge, trace ids, critiques). The stability rerun saved no critiques,
    # so its output is estimated with the v0 dev critiques.
    runs = [
        (v0, split["dev"], v0_critiques),
        (v1, split["dev"], v1_critiques),
        (v0, split["dev"], v0_critiques),
        (v0, split["test"], v0_critiques),
    ]
    calls = input_tokens = output_tokens = 0
    for judge, trace_ids, critiques in runs:
        prompt = tokens(judge["prompt_text"] + DOCETL_WRAPPER)
        for trace_id in trace_ids:
            calls += 1
            input_tokens += prompt + tokens(_trace_text(trace_id, store))
            output_tokens += tokens(critiques[trace_id]) + OUTPUT_OVERHEAD
    model = v0["model"]
    row = {
        "cost_category": "judge",
        "call_site": "analysis/helpers/scale.py:201",
        "purpose": "HW5 dispute_not_escalated judge, 4 runs (v0 dev, v1 dev, v0 stability, "
                   "v0 test); ESTIMATED tokens (tiktoken), glitch retries not counted",
        "model": model,
        "calls": calls,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": price(model, input_tokens, output_tokens),
    }
    return row, input_tokens / calls, output_tokens / calls


def hw7_judge_row(input_per_call: float, output_per_call: float) -> dict:
    """HW7 monitoring: before (30), after (29), stability (29); the rerun hit DocETL's cache."""
    calls = 30 + 29 + 29
    input_tokens = round(calls * input_per_call)
    output_tokens = round(calls * output_per_call)
    return {
        "cost_category": "judge",
        "call_site": "monitoring/run_judges.py:80",
        "purpose": "HW7 monitoring with the HW5 v0 judge (3 real runs, call counts from "
                   "hw7_run_log.md); ESTIMATED tokens = HW5 average per call (texts not saved)",
        "model": "gpt-4o-mini",
        "calls": calls,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": price("gpt-4o-mini", input_tokens, output_tokens),
    }


def hw8_replay_judge_row() -> tuple[dict, float, float]:
    """The replay judge on case e-009, once per development run in HW8."""
    judge = read("analysis/state/judges/dispute_not_escalated-v0.json")
    prompt = tokens(judge["prompt_text"])
    calls = input_tokens = output_tokens = 0
    for path in sorted((ROOT / "optimize" / "results").glob("development-*.json")):
        for case in json.loads(path.read_text())["cases"]:
            for run in case["run_details"]:
                reason = run.get("judge_reasons", {}).get("dispute_not_escalated")
                if reason is None:
                    continue
                calls += 1
                input_tokens += prompt + tokens(run["final_reply"])
                output_tokens += tokens(reason)
    row = {
        "cost_category": "judge",
        "call_site": "replay/rollout.py:426",
        "purpose": "HW8 replay judge (dispute_not_escalated) on case e-009; ESTIMATED tokens "
                   "(tiktoken, policy documents in the judge input not counted)",
        "model": judge["model"],
        "calls": calls,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": price(judge["model"], input_tokens, output_tokens),
    }
    return row, input_tokens / calls, output_tokens / calls


def main() -> None:
    hw5, input_per_call, output_per_call = hw5_judge_row()
    replay, replay_input_per_call, replay_output_per_call = hw8_replay_judge_row()
    rows = [
        server_agent_row(
            ["traces/support_traces.json"],
            "HW3 scenario run (250 scenarios); tokens and cost from Langfuse",
        ),
        server_agent_row(
            ["traces/hw5_targeted_traces.json", "traces/hw5_targeted_traces_round2.json"],
            "HW5 targeted trace generation (2 rounds); tokens and cost from Langfuse",
        ),
        hw7_agent_row(),
        *hw6_harbor_rows(replay_input_per_call, replay_output_per_call),
        *hw8_agent_rows(),
        hw5,
        hw7_judge_row(input_per_call, output_per_call),
        replay,
    ]
    rows.sort(key=lambda row: row["cost_usd"], reverse=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({**row, "cost_usd": f"{row['cost_usd']:.6f}"})
    print(f"Wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
