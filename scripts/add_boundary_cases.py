"""Append the refund/return boundary-day scenarios to the review batch.

Ad hoc follow-up to batch 1 (hw4.md Part B): while reviewing support-0123
(a 374-day-late refund denial), the agent's "the window has passed" claim
turned out to rest on no grounded "today" reference anywhere in its context
(SYSTEM_PROMPT_TEMPLATE injects only role/user_id/store_id; no tool exposes
world_asof). That's harmless at a 344-day margin but could flip a decision
at a 1-day margin. These six scenarios are exactly those margins:

    support-0062  Meridian Cycles, 21-day override, no restocking fee
    support-0073  Meridian Cycles, day 20 of 21 (eligible)
    support-0074  Meridian Cycles, day 22 of 21 (not eligible)
    support-0075  Cascade Audio, day 19, opened item, restocking fee
                  (6ea6b763... is an orphaned retry of this scenario;
                  only 7987dca1... is the complete run)
    support-0076  Copperline Tools, day 30 of 30 (eligible, inclusive)
    support-0077  Trailhead Supply, day 31 of 30 (not eligible)

Appends to samples.json/sample_manifest.json rather than replacing them, so
batch 1's 30 traces and their annotations are untouched. Reuses
langfuse_io.fetch_traces() (the same live, normalized source select_batch1.py
draws from) rather than traces/support_traces.json, which lacks the `trace`/
`text`/`features`/`meta` shape the UI expects.

Usage:
    uv run python scripts/add_boundary_cases.py
"""

from __future__ import annotations

from analysis.helpers import _state, langfuse_io
from observability.instrument import load_env

TARGET_TRACE_IDS = {
    "1072dc7d908d48b052310e787f74cd2c": "support-0062",
    "2f49d006ebd79634075620f0502527d8": "support-0073",
    "f2f01224f4534881e68b12ca91a24e80": "support-0074",
    "7987dca1130313cc8a1e42bd28ff9481": "support-0075",
    "b6af3fd154492c4223fe41686d198e56": "support-0076",
    "d4786980450df6328f693d660ccaaf97": "support-0077",
}


def main() -> None:
    load_env()
    if not langfuse_io.is_configured():
        raise SystemExit(
            "Langfuse is not configured (.env needs LANGFUSE_PUBLIC_KEY / "
            "LANGFUSE_SECRET_KEY / LANGFUSE_HOST)"
        )

    all_traces = langfuse_io.fetch_traces()
    traces_by_id = {t["trace_id"]: t for t in all_traces}

    missing = TARGET_TRACE_IDS.keys() - traces_by_id.keys()
    if missing:
        raise SystemExit(f"not found in fetch_traces(): {missing}")

    samples = _state.read_json(_state.state_path("samples.json"), [])
    manifest = _state.read_json(_state.state_path("sample_manifest.json"), {})
    existing_ids = {s["trace_id"] for s in samples}

    added = []
    for trace_id, scenario_id in TARGET_TRACE_IDS.items():
        if trace_id in existing_ids:
            print(f"skip {trace_id} ({scenario_id}): already in samples.json")
            continue
        trace = traces_by_id[trace_id]
        reason = (
            f"boundary case ({scenario_id}) — refund/return window edge day, "
            "added to probe whether the agent's ungrounded 'today' assumption "
            "(no world_asof exposed anywhere in its context) can flip a "
            "close eligibility verdict"
        )
        samples.append(
            {
                "trace_id": trace["trace_id"],
                "reason": reason,
                "trace": trace["trace"],
                "text": trace["text"],
                "features": trace["features"],
                "meta": trace["meta"],
                "permalink": trace.get("permalink"),
                "flags": [],
            }
        )
        manifest.setdefault("picks", []).append({"trace_id": trace_id, "reason": reason})
        added.append((trace_id, scenario_id))

    _state.write_json(_state.state_path("samples.json"), samples)
    _state.write_json(_state.state_path("sample_manifest.json"), manifest)

    print(f"added {len(added)} boundary-case traces to samples.json:")
    for trace_id, scenario_id in added:
        print(f"  {scenario_id}  {trace_id}")
    print(f"samples.json now has {len(samples)} traces total")


if __name__ == "__main__":
    main()
