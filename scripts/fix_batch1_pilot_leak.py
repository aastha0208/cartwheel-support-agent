"""One-time correction: batch 1 (HW4) leaked 6 pilot-phase traces.

select_batch1.py originally sampled from every Langfuse trace carrying a
cartwheel.scenario_id, which includes HW3's 30 pilot-phase runs (ids like
"pilot-028") alongside the 250 final scenarios ("support-0028"). A pilot
scenario carries forward into the final set nearly verbatim when it didn't
need revision, so reviewing both a pilot and its final counterpart
double-counts one underlying case and draws from a population HW4 was never
meant to sample. select_batch1.py is now fixed for future runs; this script
performs the one-time surgical correction on the *existing* batch 1: it
keeps the 24 already-correct (support-*) samples exactly as they are — so
existing annotations, which reference their trace_ids, stay linked — drops
the 6 pilot-tagged ones, and draws 6 replacements (matching the 3 uniform /
3 cluster-representative split the removed ones came from) from the
correctly-scoped pool.

Usage:
    uv run python scripts/fix_batch1_pilot_leak.py
"""

from __future__ import annotations

from analysis.helpers import _state, langfuse_io
from analysis.helpers.selection import select
from observability.instrument import load_env

# From sample_manifest.json's "picks": the 6 pilot-tagged trace ids and how
# each was originally selected, so the replacement preserves the split.
PILOT_TRACE_IDS = {
    "16b6ca3e48e2250f4a345ce15078c26c": "random pick",
    "713e78c4e51f5f177538b8584f09edfb": "random pick",
    "3e0669f558745deec3922f39449bf13e": "random pick",
    "083b7a845ca52407f6eb153978a70254": "cluster 6 representative",
    "04832973b8bd6c024104b9c2cf3fb335": "cluster 1 representative",
    "0a20d95fa5ddfb62dd68ea7ac91f5d29": "cluster 4 representative",
}


def main() -> None:
    load_env()
    if not langfuse_io.is_configured():
        raise SystemExit(
            "Langfuse is not configured (.env needs LANGFUSE_PUBLIC_KEY / "
            "LANGFUSE_SECRET_KEY / LANGFUSE_HOST)"
        )

    samples = _state.read_json(_state.state_path("samples.json"), default=[])
    manifest = _state.read_json(_state.state_path("sample_manifest.json"), default={})
    if not samples or not manifest:
        raise SystemExit("no existing batch 1 samples/manifest found to correct")

    kept_samples = [s for s in samples if s["trace_id"] not in PILOT_TRACE_IDS]
    removed = len(samples) - len(kept_samples)
    if removed != len(PILOT_TRACE_IDS):
        raise SystemExit(
            f"expected to remove {len(PILOT_TRACE_IDS)} pilot samples, "
            f"actually removed {removed} — samples.json may have changed; investigate"
        )
    n_uniform_needed = sum(1 for r in PILOT_TRACE_IDS.values() if r == "random pick")
    n_cluster_needed = len(PILOT_TRACE_IDS) - n_uniform_needed

    all_traces = langfuse_io.fetch_traces()
    if not all_traces:
        raise SystemExit("Langfuse returned no traces for the Module 2 slice")
    traces = [
        t for t in all_traces
        if str(t.get("meta", {}).get("scenario_id", "")).startswith("support-")
    ]
    if not traces:
        raise SystemExit("no final (support-*) scenario traces found after filtering")

    already_used = {s["trace_id"] for s in kept_samples} | set(PILOT_TRACE_IDS)

    new_uniform = select(traces, k=n_uniform_needed, strategy="random", exclude_ids=already_used)
    if len(new_uniform) < n_uniform_needed:
        raise SystemExit(f"only found {len(new_uniform)} uniform replacements, needed {n_uniform_needed}")
    used_plus_uniform = already_used | {p["trace_id"] for p in new_uniform}

    # Same over-ask-then-filter trick as select_batch1.py: ask for more than
    # needed since "diversity" always mixes in some random picks too.
    diversity_raw = select(traces, k=n_cluster_needed + 8, strategy="diversity", exclude_ids=used_plus_uniform)
    new_cluster = [p for p in diversity_raw if p["reason"].startswith("cluster ")][:n_cluster_needed]
    if len(new_cluster) < n_cluster_needed:
        raise SystemExit(f"only found {len(new_cluster)} cluster replacements, needed {n_cluster_needed}")

    new_picks = new_uniform + new_cluster
    traces_by_id = {t["id"]: t for t in traces}
    new_samples = []
    for pick in new_picks:
        trace = traces_by_id[pick["trace_id"]]
        new_samples.append(
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

    final_samples = kept_samples + new_samples
    ids = [s["trace_id"] for s in final_samples]
    if len(ids) != len(set(ids)) or len(final_samples) != len(samples):
        raise SystemExit("sanity check failed: duplicate id or wrong final count; nothing written")

    # Update the manifest's picks list the same way: drop the pilot entries,
    # append the replacements. Keep everything else (source, k, strategy) as
    # a record that a correction happened, via batch_description.
    old_picks = [p for p in manifest.get("picks", []) if p["trace_id"] not in PILOT_TRACE_IDS]
    manifest["picks"] = old_picks + new_picks
    manifest["batch_description"] = (
        manifest.get("batch_description", "")
        + " | corrected: removed 6 pilot-scenario traces that leaked in from "
        "fetch_traces()'s unfiltered population, replaced with support-* picks"
    )

    # The one existing annotation on a removed pilot trace (0a20d95f..., a
    # content-free "no failure observed" marker) would be orphaned. Drop it
    # so it doesn't linger in the state pointing at a trace no longer in the
    # sample.
    annotations = _state.read_json(_state.state_path("annotations.json"), default=[])
    annotations = [a for a in annotations if a.get("trace_id") not in PILOT_TRACE_IDS]

    _state.write_json(_state.state_path("samples.json"), final_samples)
    _state.write_json(_state.state_path("sample_manifest.json"), manifest)
    _state.write_json(_state.state_path("annotations.json"), annotations)
    print(
        f"kept {len(kept_samples)}, removed {removed} pilot samples, "
        f"added {len(new_samples)} replacements "
        f"({len(new_uniform)} uniform, {len(new_cluster)} cluster) — "
        f"final count: {len(final_samples)}"
    )


if __name__ == "__main__":
    main()
