"""Build Homework 4 Part B's batch 2 sample set (Module 2, HW4).

Batch 2, per homework/module-2/hw4.md Part B: "Choose one product dimension
before looking at the outcomes, e.g., user role, then add 30 traces
distributed across its values."

Dimension chosen: user role (shopper/merchant/support), split evenly
10/10/10. Rationale: the actual scenario population is 51% shopper / 27%
merchant / 22% support, but batch 1 + the batch-3 down payment reviewed so
far skew 67% / 22% / 11% shopper-heavy. An even 10/10/10 split brings the
*cumulative* 66-trace reviewed set back to ~51.5% / 27.3% / 21.2% -- almost
exactly the true population proportions -- rather than overcorrecting into
an artificially merchant/support-heavy batch.

Excludes every trace_id already in samples.json (batches 1 and 3), per the
handout's "do not count one trace toward more than one batch."

Usage:
    uv run python scripts/select_batch2.py
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from analysis.helpers import _state, langfuse_io
from observability.instrument import load_env

REPO_ROOT = Path(__file__).resolve().parents[1]
SEED = 7
K_PER_ROLE = 10
ROLES = ("shopper", "merchant", "support")


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
    if not pool:
        raise SystemExit("no eligible traces left after excluding already-sampled ones")

    by_role: dict[str, list[dict]] = {r: [] for r in ROLES}
    for t in pool:
        role = t.get("meta", {}).get("role")
        if role in by_role:
            by_role[role].append(t)

    rng = random.Random(SEED)
    picks_by_role: dict[str, list[dict]] = {}
    for role in ROLES:
        candidates = by_role[role]
        if len(candidates) < K_PER_ROLE:
            raise SystemExit(
                f"only {len(candidates)} unsampled {role} traces available, need {K_PER_ROLE}"
            )
        picks_by_role[role] = rng.sample(candidates, K_PER_ROLE)

    new_samples = []
    new_picks = []
    for role in ROLES:
        for trace in picks_by_role[role]:
            reason = f"batch 2: role-stratified ({role})"
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
                    "batch": 2,
                }
            )
            new_picks.append({"trace_id": trace["trace_id"], "reason": reason})

    samples.extend(new_samples)
    _state.write_json(_state.state_path("samples.json"), samples)

    manifest = _state.read_json(_state.state_path("sample_manifest.json"), {"source": "langfuse", "batches": []})
    manifest.setdefault("batches", []).append(
        {
            "batch": 2,
            "batch_description": (
                "Dimension-stratified (hw4.md Part B, batch 2): user role, "
                "10 shopper + 10 merchant + 10 support, chosen to correct "
                "batch 1's shopper-heavy skew back toward the true scenario "
                "population proportions (51%/27%/22%)"
            ),
            "k": len(new_picks),
            "strategy": f"stratified random by role, {K_PER_ROLE} per value, seed={SEED}",
            "picks": new_picks,
        }
    )
    _state.write_json(_state.state_path("sample_manifest.json"), manifest)

    print(f"added {len(new_samples)} batch-2 traces to samples.json ({K_PER_ROLE} per role)")
    print(f"samples.json now has {len(samples)} traces total")


if __name__ == "__main__":
    main()
