"""Build Homework 4 Part B's batch 1 sample set (Module 2, HW4).

Batch 1, per homework/module-2/hw4.md Part B: "15 uniformly sampled traces
and 15 cluster representatives" — two distinct, non-overlapping groups, kept
separate so their composition stays reportable later (review_summary.md
asks for the size and composition of the reviewed sample).

Why this script exists rather than a bare call to
``analysis.helpers.tools.select_traces``: that function writes
``samples.json``/``sample_manifest.json`` fresh on every call (it does not
append), and its own "diversity" strategy blends cluster representatives
with random picks into one batch rather than returning them as two separate
counts. This calls the lower-level ``analysis.helpers.selection.select``
directly for each half, then merges and writes the combined result once.

Usage:
    uv run python scripts/select_batch1.py
"""

from __future__ import annotations

import json
from pathlib import Path

from analysis.helpers import _state, langfuse_io
from analysis.helpers.selection import select
from observability.instrument import load_env

REPO_ROOT = Path(__file__).resolve().parents[1]


def _final_scenario_trace_ids() -> set[str]:
    """The trace ids homework/module-1/hw3.md's export_langfuse.py verified
    as the complete, successful run for each of the 250 final scenarios —
    the authoritative "known good" set, used as a whitelist rather than
    filtering fetch_traces()'s live pull by a cartwheel.scenario_id prefix.

    A prefix check alone isn't enough: fetch_traces() returns everything in
    Langfuse carrying any scenario_id, which includes (1) HW3's 30
    pilot-phase runs (ids like "pilot-028", which can be near-duplicates of
    their final "support-0028" counterpart), and (2) orphaned retries — a
    scenario run that failed partway through and was rerun still leaves its
    incomplete first attempt sitting in Langfuse under a different trace id,
    carrying the same scenario_id. Both classes produce traces with no real
    assistant reply, or a duplicate of a scenario already in the sample.
    This local export already resolved all of that during HW3 — it's the
    deduplicated, verified-complete set — so matching against its trace ids
    rules out both problems at once instead of pattern-matching each one.
    """
    path = REPO_ROOT / "traces" / "support_traces.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    records = data.get("traces", data) if isinstance(data, dict) else data
    return {str(r["id"]) for r in records}


def main() -> None:
    load_env()  # .env is not auto-loaded; this populates os.environ from it.
    if not langfuse_io.is_configured():
        raise SystemExit(
            "Langfuse is not configured (.env needs LANGFUSE_PUBLIC_KEY / "
            "LANGFUSE_SECRET_KEY / LANGFUSE_HOST)"
        )
    all_traces = langfuse_io.fetch_traces()
    if not all_traces:
        raise SystemExit("Langfuse returned no traces for the Module 2 slice")

    final_ids = _final_scenario_trace_ids()
    traces = [t for t in all_traces if t.get("trace_id") in final_ids]
    if not traces:
        raise SystemExit("no traces matched the final-scenario id whitelist after filtering")

    uniform = select(traces, k=15, strategy="random", exclude_ids=set())
    uniform_ids = {p["trace_id"] for p in uniform}

    # Ask for more than 15: select()'s "diversity" strategy always fills the
    # remainder with random picks (roughly one third of k), which get
    # filtered back out below, leaving pure cluster-representative picks.
    diversity_raw = select(traces, k=23, strategy="diversity", exclude_ids=uniform_ids)
    cluster_reps = [p for p in diversity_raw if p["reason"].startswith("cluster ")][:15]
    if len(cluster_reps) < 15:
        raise SystemExit(
            f"only found {len(cluster_reps)} cluster representatives from a "
            "k=23 diversity call; raise k in this script and rerun"
        )

    picks = uniform + cluster_reps
    if len({p["trace_id"] for p in picks}) != len(picks):
        raise SystemExit("a trace id appears in both sub-batches; investigate before saving")

    traces_by_id = {t["id"]: t for t in traces}
    samples = []
    for pick in picks:
        trace = traces_by_id[pick["trace_id"]]
        samples.append(
            {
                "trace_id": trace["trace_id"],
                "reason": pick["reason"],
                "trace": trace["trace"],
                "text": trace["text"],
                "features": trace["features"],
                "meta": trace["meta"],
                "permalink": trace.get("permalink"),
                "flags": [],
            }
        )

    manifest = {
        "source": "langfuse",
        "batch": 1,
        "batch_description": "15 uniform + 15 cluster representatives (hw4.md Part B, batch 1)",
        "k": len(picks),
        "strategy": "random (uniform half) + diversity (cluster-representative half)",
        "picks": picks,
    }

    _state.write_json(_state.state_path("samples.json"), samples)
    _state.write_json(_state.state_path("sample_manifest.json"), manifest)
    print(
        f"wrote {len(samples)} samples to analysis/state/samples.json "
        f"({len(uniform)} uniform, {len(cluster_reps)} cluster representatives)"
    )


if __name__ == "__main__":
    main()
