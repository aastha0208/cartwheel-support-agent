"""Build (part of) Homework 4 Part B's batch 3: depth search for candidate
modes (Module 2, HW4).

Batch 3, per homework/module-2/hw4.md Part B: "Add 25 traces retrieved
during depth searches for candidate modes and close negative examples."

This pulls semantic-neighbor candidates (analysis.helpers.selection.
next_candidates, bag-of-words cosine similarity against each mode's known
positive examples) for the three watch-list modes that are stuck at 2
confirmed instances and need a 3rd to become real final modes:

    store_identity_not_resolved   (seeds: 806de685e1ca, 055f7cc1d0ec)
    policy_citation_missing       (seeds: 62c973650e12, 059cb6485250)
    order_disambiguation_unsound  (seeds: 0d759a5e4d9f, 302a2ca584e0)

IMPORTANT: this only *retrieves* candidates -- a similarity score is a
retrieval signal, not a label (hw4.md is explicit on this point). Every
trace added here is unjudged until a human actually reads it and decides
whether the mode's definition applies. Expect some -- maybe most -- of
these to be rejected; the handout requires at least one rejected suggestion
in the saved state, and semantic (bag-of-words) similarity is a loose signal
that will often surface topically-related but not-actually-matching traces.

Usage:
    uv run python scripts/select_batch3_depth_search.py
"""

from __future__ import annotations

import json
from pathlib import Path

from analysis.helpers import _state, langfuse_io
from analysis.helpers.selection import next_candidates
from observability.instrument import load_env

REPO_ROOT = Path(__file__).resolve().parents[1]

TARGETS = [
    ("store_identity_not_resolved", ["806de685e1cac28c6f02022946fbea38", "055f7cc1d0ec5c7d15b1f50218d5c833"], 9),
    ("policy_citation_missing", ["62c973650e1230553d5ae25b74da5d32", "059cb6485250785b429748a2d0740fbb"], 8),
    ("order_disambiguation_unsound", ["0d759a5e4d9f82d621e3b3e083ef200c", "302a2ca584e060ee3cb51c8706d85fed"], 8),
]


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
    whitelisted = [t for t in all_traces if t.get("trace_id") in final_ids]
    traces_by_id = {t["trace_id"]: t for t in whitelisted}

    samples = _state.read_json(_state.state_path("samples.json"), [])
    already_labeled = {s["trace_id"] for s in samples}
    suggestions = _state.read_json(_state.state_path("suggestions.json"), [])

    new_samples = []
    new_suggestions = []
    for mode, seeds, k in TARGETS:
        candidates = next_candidates(
            traces=whitelisted,
            mode=mode,
            k=k,
            strategy="enrich",
            confirmed_failures=seeds,
            already_labeled=already_labeled,
            seed=7,
        )
        for c in candidates:
            trace_id = c["trace_id"]
            trace = traces_by_id[trace_id]
            already_labeled.add(trace_id)  # no duplicate picks across modes
            reason = f"batch 3 depth search: candidate for {mode} ({c['signal']})"
            new_samples.append(
                {
                    "trace_id": trace_id,
                    "reason": reason,
                    "trace": trace["trace"],
                    "text": trace["text"],
                    "features": trace["features"],
                    "meta": trace["meta"],
                    "permalink": trace.get("permalink"),
                    "flags": [],
                    "batch": 3,
                }
            )
            new_suggestions.append(
                {
                    "id": f"sugg-{mode}-{trace_id[:8]}",
                    "trace_id": trace_id,
                    "mode": mode,
                    "quote": f"retrieval signal: {c['signal']}",
                }
            )

    samples.extend(new_samples)
    _state.write_json(_state.state_path("samples.json"), samples)

    suggestions.extend(new_suggestions)
    _state.write_json(_state.state_path("suggestions.json"), suggestions)

    manifest = _state.read_json(_state.state_path("sample_manifest.json"), {"source": "langfuse", "batches": []})
    manifest.setdefault("batches", []).append(
        {
            "batch": 3,
            "batch_description": (
                "Depth search (hw4.md Part B, batch 3): semantic-neighbor "
                "candidates for the three watch-list modes stuck at 2 "
                "confirmed instances (store_identity_not_resolved, "
                "policy_citation_missing, order_disambiguation_unsound). "
                "Retrieval only -- every trace is unjudged until reviewed; "
                "a candidate that turns out not to fit becomes a recorded "
                "rejected suggestion, not a silent drop."
            ),
            "k": len(new_samples),
            "strategy": "semantic neighbor (bag-of-words cosine vs. each mode's 2 known positives)",
            "picks": [{"trace_id": s["trace_id"], "reason": s["reason"]} for s in new_samples],
        }
    )
    _state.write_json(_state.state_path("sample_manifest.json"), manifest)

    print(f"added {len(new_samples)} depth-search candidates to samples.json and suggestions.json")
    for mode, seeds, k in TARGETS:
        count = sum(1 for s in new_samples if mode in s["reason"])
        print(f"  {mode}: {count} candidates")
    print(f"samples.json now has {len(samples)} traces total")


if __name__ == "__main__":
    main()
