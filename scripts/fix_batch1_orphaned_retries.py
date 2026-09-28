"""One-time correction: batch 1 (HW4) had 8 orphaned/duplicate traces.

Even after the pilot-leak fix (fix_batch1_pilot_leak.py), 8 of the 30 batch-1
samples turned out to have zero assistant replies — just the shopper's
opening message and nothing else. Cause: a Cartwheel scenario run that fails
partway through (per homework/module-1/hw3.md, "the server stopped before
its spans were sent") gets rerun, but its incomplete first attempt stays in
Langfuse forever under a different trace id, carrying the same
cartwheel.scenario_id as the successful rerun. fetch_traces()'s live pull,
filtered only by scenario_id prefix, has no way to prefer the complete run
over the abandoned one — and in one case (support-0121) it pulled in both,
counting one scenario twice toward the sample.

select_batch1.py is now hardened to whitelist against
traces/support_traces.json (the verified-complete 250-scenario export),
which rules out this whole class of problem for future runs. This script
performs the one-time surgical correction on the *existing* batch: keeps the
22 already-good samples exactly as they are (so existing annotations stay
linked), drops the 8 orphaned/duplicate ones, and draws 8 replacements
(6 uniform / 2 cluster-representative, matching how the removed ones were
originally selected) from the now-whitelisted pool.

Usage:
    uv run python scripts/fix_batch1_orphaned_retries.py
"""

from __future__ import annotations

from analysis.helpers import _state, langfuse_io
from analysis.helpers.selection import select
from observability.instrument import load_env
from scripts.select_batch1 import _final_scenario_trace_ids

# From sample_manifest.json's "picks": the 8 orphaned/duplicate trace ids and
# how each was originally selected, so the replacement preserves the split.
BAD_TRACE_IDS = {
    "0f5daaeeafd3b20f50edcc8785e44759": "random pick",   # support-0128, no reply
    "b50842c20777b8458f1b73637ca157e3": "random pick",   # support-0090, no reply
    "c4358c13ae918cb0231a476346684746": "random pick",   # support-0108, no reply
    "12f76806eed1233adba2843973a9f519": "random pick",   # support-0125, no reply
    "aaaed0fda37f1b02fcfda88f23dcd2ed": "random pick",   # support-0127, no reply
    "02718d6b823fbcb03e32c66abdce394d": "cluster 1 representative",  # support-0123, no reply
    "ae3446fe874c9a9d8c6a5444c970b60d": "random pick",   # support-0087, no reply
    "078a805f440233ab0205ff5ebdd90b85": "cluster 1 representative",  # support-0121, duplicate + no reply
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

    kept_samples = [s for s in samples if s["trace_id"] not in BAD_TRACE_IDS]
    removed = len(samples) - len(kept_samples)
    if removed != len(BAD_TRACE_IDS):
        raise SystemExit(
            f"expected to remove {len(BAD_TRACE_IDS)} samples, "
            f"actually removed {removed} — samples.json may have changed; investigate"
        )
    n_uniform_needed = sum(1 for r in BAD_TRACE_IDS.values() if r == "random pick")
    n_cluster_needed = len(BAD_TRACE_IDS) - n_uniform_needed

    all_traces = langfuse_io.fetch_traces()
    if not all_traces:
        raise SystemExit("Langfuse returned no traces for the Module 2 slice")
    final_ids = _final_scenario_trace_ids()
    traces = [t for t in all_traces if t.get("trace_id") in final_ids]
    if not traces:
        raise SystemExit("no traces matched the final-scenario id whitelist after filtering")

    already_used = {s["trace_id"] for s in kept_samples} | set(BAD_TRACE_IDS)

    new_uniform = select(traces, k=n_uniform_needed, strategy="random", exclude_ids=already_used)
    if len(new_uniform) < n_uniform_needed:
        raise SystemExit(f"only found {len(new_uniform)} uniform replacements, needed {n_uniform_needed}")
    used_plus_uniform = already_used | {p["trace_id"] for p in new_uniform}

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

    old_picks = [p for p in manifest.get("picks", []) if p["trace_id"] not in BAD_TRACE_IDS]
    manifest["picks"] = old_picks + new_picks
    manifest["batch_description"] = (
        manifest.get("batch_description", "")
        + " | corrected: removed 8 orphaned/duplicate traces (failed-then-retried "
        "HW3 runs with no assistant reply) found via fetch_traces()'s unfiltered "
        "pull, replaced with picks from the traces/support_traces.json whitelist"
    )

    # None of the 8 removed traces were ever annotated (confirmed before
    # running this), so no annotations.json cleanup is needed this time.
    _state.write_json(_state.state_path("samples.json"), final_samples)
    _state.write_json(_state.state_path("sample_manifest.json"), manifest)
    print(
        f"kept {len(kept_samples)}, removed {removed} orphaned/duplicate samples, "
        f"added {len(new_samples)} replacements "
        f"({len(new_uniform)} uniform, {len(new_cluster)} cluster) — "
        f"final count: {len(final_samples)}"
    )


if __name__ == "__main__":
    main()
