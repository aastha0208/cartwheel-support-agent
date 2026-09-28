"""Build Homework 4 Part B's batch 4 sample set (Module 2, HW4).

Batch 4, per homework/module-2/hw4.md Part B: "After drafting the taxonomy,
review 15 additional uniformly sampled traces to check whether new modes
continue to appear."

Deliberately TRUE uniform random -- no stratification by role, intent, or
anything else, even though batches 1-3 left real coverage gaps (return_deadline,
out_of_scope, order_status). Batch 4's whole purpose is a taxonomy stability
check: "how many of these 15 produce a previously unseen mode" only means
something if the sample wasn't steered toward known-thin areas first. Any
deliberate coverage-gap targeting belongs in a separate, explicitly-labeled
supplementary pull, not folded into this batch.

Excludes every trace_id already in samples.json (batches 1-3), per the
handout's "do not count one trace toward more than one batch."

Usage:
    uv run python scripts/select_batch4.py
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from analysis.helpers import _state, langfuse_io
from observability.instrument import load_env

REPO_ROOT = Path(__file__).resolve().parents[1]
SEED = 7
K = 15


def _final_scenario_trace_ids() -> set[str]:
    path = REPO_ROOT / "traces" / "support_traces.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    records = data.get("traces", data) if isinstance(data, dict) else data
    return {str(r["id"]) for r in records}


def main() -> None:
    load_env()
    if not langfuse_io.is_configured():
        raise SystemExit(
            "Langfuse is not configured (.env needs LANGFUSE_PUBLIC_KEY / "
            "LANGFUSE_SECRET_KEY / LANGFUSE_HOST)"
        )
    all_traces = langfuse_io.fetch_traces()
    if not all_traces:
        raise SystemExit("Langfuse returned no traces for the Module 2 slice")

    final_ids = _final_scenario_trace_ids()
    samples = _state.read_json(_state.state_path("samples.json"), [])
    already_sampled = {s["trace_id"] for s in samples}

    pool = [
        t for t in all_traces
        if t.get("trace_id") in final_ids and t.get("trace_id") not in already_sampled
    ]
    if len(pool) < K:
        raise SystemExit(f"only {len(pool)} unsampled traces available, need {K}")

    rng = random.Random(SEED)
    picks = rng.sample(pool, K)

    new_samples = []
    new_picks = []
    for trace in picks:
        reason = "batch 4: uniform random (taxonomy stability check)"
        new_samples.append(
            {
                "trace_id": trace["trace_id"],
                "reason": reason,
                "trace": trace["trace"],
                "text": trace["text"],
                "features": trace["features"],
                "meta": trace["meta"],
                "permalink": trace.get("permalink"),
                "flags": [],
                "batch": 4,
            }
        )
        new_picks.append({"trace_id": trace["trace_id"], "reason": reason})

    samples.extend(new_samples)
    _state.write_json(_state.state_path("samples.json"), samples)

    manifest = _state.read_json(_state.state_path("sample_manifest.json"), {"source": "langfuse", "batches": []})
    manifest.setdefault("batches", []).append(
        {
            "batch": 4,
            "batch_description": (
                "Final uniform check (hw4.md Part B, batch 4): 15 traces drawn "
                "by true uniform random sample from every scenario not yet "
                "reviewed in batches 1-3, to test whether the drafted taxonomy "
                "is stable -- deliberately not steered toward known coverage "
                "gaps, so the 'new modes found' count stays a fair signal."
            ),
            "k": len(new_picks),
            "strategy": f"uniform random, seed={SEED}",
            "picks": new_picks,
        }
    )
    _state.write_json(_state.state_path("sample_manifest.json"), manifest)

    print(f"added {len(new_samples)} batch-4 traces to samples.json (uniform random)")
    for s in new_samples:
        print(f"  {s['meta'].get('scenario_id')}  {s['trace_id']}")
    print(f"samples.json now has {len(samples)} traces total")


if __name__ == "__main__":
    main()
