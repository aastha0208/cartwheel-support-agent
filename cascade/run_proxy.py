"""Run the cascade proxy on the HW5 dispute_not_escalated labels (Homework 9 Part D).

The proxy gets the frozen HW5 judge prompt and the same trace text the oracle
read, wrapped the way analysis/helpers/scale.py wraps it, plus one instruction
asking for its confidence from 0 to 1. Each answer is saved with the token
counts the LLM API returned. Already saved traces are skipped, so a stopped
run can be resumed with the same command.

    uv run python cascade/run_proxy.py --split dev
    uv run python cascade/run_proxy.py --split test
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
# The saved HW5 judge inputs, as in analysis/run_judges.py (also keeps Langfuse out).
os.environ["CARTWHEEL_JUDGE_TRACE_SOURCE"] = str(
    ROOT / "analysis" / "state" / "hw5_trace_inputs.json"
)

from analysis.helpers.scale import _trace_text, load_store_traces  # noqa: E402
from observability.instrument import load_env  # noqa: E402

MODE = "dispute_not_escalated"
ORACLE_ID = f"{MODE}-v0"
PROXY_MODEL = "gpt-5-nano"
RESULTS_DIR = ROOT / "cascade" / "results"

# The oracle's wrapper text (analysis/helpers/scale.py), then the one added
# confidence instruction and the answer format.
INSTRUCTIONS = (
    "First write a critique of the trace against the criterion. "
    "Use specific evidence from the provided trace. Then return result "
    "as exactly Pass when the named failure is absent, or Fail when present."
)
CONFIDENCE = (
    "Also state your confidence that your result is correct, as a number from 0 to 1."
)
FORMAT = 'Answer with a JSON object: {"critique": string, "result": "Pass" or "Fail", "confidence": number}.'
# Strict structured output, so result and confidence are always separate
# fields (in the first dev run, 7 of 51 answers put them inside the critique).
ANSWER_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "judge_verdict",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "critique": {"type": "string"},
                "result": {"type": "string", "enum": ["Pass", "Fail"]},
                "confidence": {"type": "number"},
            },
            "required": ["critique", "result", "confidence"],
            "additionalProperties": False,
        },
    },
}


def proxy_prompt(judge_prompt: str, trace_text: str) -> str:
    return (
        f"{judge_prompt}\n\n--- Trace to evaluate ---\n{trace_text}\n\n"
        f"{INSTRUCTIONS}\n{CONFIDENCE}\n{FORMAT}"
    )


def parse_answer(text: str) -> tuple[int | None, float | None]:
    """Return (verdict, confidence); verdict 1 = Pass, as in the HW5 labels."""
    try:
        answer = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        answer = json.loads(match.group(0)) if match else {}
    result = str(answer.get("result", "")).strip().lower()
    verdict = {"pass": 1, "fail": 0}.get(result)
    try:
        confidence = min(max(float(answer.get("confidence")), 0.0), 1.0)
    except (TypeError, ValueError):
        confidence = None
    return verdict, confidence


def latest_human_labels() -> dict[str, int]:
    rows = [
        json.loads(line)
        for line in (ROOT / "analysis" / "state" / "hw5_labels" / f"{MODE}.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    rows.sort(key=lambda row: row["ts"])
    return {row["trace_id"]: int(row["label"]) for row in rows}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("dev", "test"), required=True)
    args = parser.parse_args()

    load_env()
    from openai import OpenAI

    judges = ROOT / "analysis" / "state" / "judges"
    oracle = json.loads((judges / f"{ORACLE_ID}.json").read_text(encoding="utf-8"))
    oracle_verdicts = oracle["predictions"][oracle["prompt_hash"]]
    split = json.loads((ROOT / "analysis" / "state" / "splits.json").read_text())[MODE]
    trace_ids = split[args.split]
    human = latest_human_labels()
    store = {trace["trace_id"]: trace for trace in load_store_traces()}

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / f"proxy_{args.split}.jsonl"
    done = set()
    if out_path.exists():
        done = {
            json.loads(line)["trace_id"]
            for line in out_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }

    client = OpenAI()
    todo = [trace_id for trace_id in trace_ids if trace_id not in done]
    print(f"{args.split}: {len(trace_ids)} traces, {len(done)} saved, {len(todo)} to run")
    for number, trace_id in enumerate(todo, 1):
        response = client.chat.completions.create(
            model=PROXY_MODEL,
            reasoning_effort="minimal",
            response_format=ANSWER_SCHEMA,
            messages=[
                {"role": "user", "content": proxy_prompt(oracle["prompt_text"], _trace_text(trace_id, store))}
            ],
        )
        text = response.choices[0].message.content or ""
        verdict, confidence = parse_answer(text)
        usage = response.usage
        details = usage.prompt_tokens_details
        record = {
            "trace_id": trace_id,
            "proxy_model": PROXY_MODEL,
            "proxy_verdict": verdict,
            "proxy_confidence": confidence,
            "oracle_verdict": oracle_verdicts[trace_id],
            "human_label": human[trace_id],
            "input_tokens": usage.prompt_tokens,
            "cached_input_tokens": (details.cached_tokens or 0) if details else 0,
            "output_tokens": usage.completion_tokens,
            "raw": text,
        }
        with out_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(f"{number}/{len(todo)} {trace_id[:8]} verdict={verdict} confidence={confidence}")
    print(f"Saved {out_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
