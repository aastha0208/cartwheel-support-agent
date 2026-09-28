"""Add replacement traces to the HW4 review batch.

Each of these replaces a scenario in our HW4 sample that turned out to have a
scenario-generation bug (ground truth contradicting the scenario's own
dialogue). The originals are marked excluded/invalid rather than pass/fail;
these replacements carry corrected dialogue against the same or an
equivalent grading target. See scenarios/replacement_scenarios.jsonl for the
corrected records and analysis/state/annotations.json for each original's
excluded note.

- support-0177r/0183r/0191r replace support-0177/0183/0191: opening_message
  was a topic-blind fallback that never mentioned the graded topic (see
  scenarios/results/stage_b_situations.py:306-307).
- support-0087r replaces support-0087: the followup claimed the corrected
  order was "more recent" and "electronics", but the DB record for the
  expected target order (#1080) was older and from an office-supply store.
- support-0179r/0189r replace support-0179/0189: expected graded the
  shipping topic, but the paraphrased opening_message asked only about
  returns/refunds (same fallback bug, caught by content not exact string
  match -- the true footprint is 17 scenarios, not the original 14; see
  scenarios/support_scenarios.KNOWN_ISSUES.md).
- support-0178r replaces support-0178 (found in batch 4): expected graded
  cancel_cutoff, but opening_message asked only about shipping times and
  damaged-item returns.
- support-0184r replaces support-0184 (found in batch 4): expected graded
  shipping, but opening_message asked only about returns (merchant role).

Usage:
    uv run python scripts/add_replacement_scenarios.py
"""

from __future__ import annotations

from analysis.helpers import _state, langfuse_io
from observability.instrument import load_env

REPLACES = {
    "support-0177r": "support-0177",
    "support-0183r": "support-0183",
    "support-0191r": "support-0191",
    "support-0087r": "support-0087",
    "support-0179r": "support-0179",
    "support-0189r": "support-0189",
    "support-0178r": "support-0178",
    "support-0184r": "support-0184",
}


def main() -> None:
    load_env()
    if not langfuse_io.is_configured():
        raise SystemExit(
            "Langfuse is not configured (.env needs LANGFUSE_PUBLIC_KEY / "
            "LANGFUSE_SECRET_KEY / LANGFUSE_HOST)"
        )

    all_traces = langfuse_io.fetch_traces()
    by_scenario: dict[str, dict] = {}
    for t in all_traces:
        sid = t.get("meta", {}).get("scenario_id")
        if sid in REPLACES:
            by_scenario[sid] = t

    missing = REPLACES.keys() - by_scenario.keys()
    if missing:
        raise SystemExit(f"not found in Langfuse yet: {missing} (try again in a moment)")

    samples = _state.read_json(_state.state_path("samples.json"), [])
    existing_ids = {s["trace_id"] for s in samples}

    added = []
    for new_sid, old_sid in REPLACES.items():
        trace = by_scenario[new_sid]
        if trace["trace_id"] in existing_ids:
            print(f"skip {new_sid}: already in samples.json")
            continue
        # inherit the batch the original invalid trace belonged to
        old_sample = next((s for s in samples if s["meta"].get("scenario_id") == old_sid), None)
        batch = old_sample.get("batch") if old_sample else None
        samples.append(
            {
                "trace_id": trace["trace_id"],
                "reason": f"replacement for {old_sid} (scenario-generation bug, see annotations.json)",
                "trace": trace["trace"],
                "text": trace["text"],
                "features": trace["features"],
                "meta": trace["meta"],
                "permalink": trace.get("permalink"),
                "flags": [],
                "batch": batch,
            }
        )
        added.append((new_sid, trace["trace_id"], batch))

    _state.write_json(_state.state_path("samples.json"), samples)
    print(f"added {len(added)} replacement traces:")
    for sid, tid, batch in added:
        print(f"  {sid}  {tid}  batch={batch}")
    print(f"samples.json now has {len(samples)} traces total")


if __name__ == "__main__":
    main()
