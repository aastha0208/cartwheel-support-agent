"""Homework 5: exports, judge runs, and metrics for one LLM judge.

Mode: ``dispute_not_escalated`` (definition: analysis/report/hw5_failure_definition.md).

HW5 label convention: 1 = Pass (failure absent), 0 = Fail (failure present).
HW4 label files (``analysis/state/labels/<mode>.json``, ``present`` = failure)
are read but never modified.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from analysis.helpers import _state

ROOT = Path(__file__).resolve().parent.parent
MODE = "dispute_not_escalated"

# Judge runs read the saved export, never live Langfuse (handout Part B).
os.environ.setdefault("CARTWHEEL_JUDGE_TRACE_SOURCE",
                      str(ROOT / "analysis" / "state" / "hw5_trace_inputs.json"))


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def hw5_labels_path(mode: str = MODE) -> Path:
    return _state.state_path("hw5_labels", f"{mode}.jsonl")


def _hw4_notes_by_trace() -> dict[str, list[dict[str, str]]]:
    """HW4 annotation notes per trace, used as the label's evidence."""
    notes: dict[str, list[dict[str, str]]] = {}
    for ann in _state.read_json(_state.state_path("annotations.json"), default=[]):
        if ann.get("note"):
            notes.setdefault(ann["trace_id"], []).append(
                {"quote": ann.get("quote", ""), "note": ann["note"]}
            )
    return notes


def seed_hw5_labels(mode: str = MODE) -> int:
    """Seed ``hw5_labels/<mode>.jsonl`` from the HW4 labels (run once).

    Refuses to run if the HW5 file already exists, so it never overwrites
    labels added afterwards.
    """
    path = hw5_labels_path(mode)
    if path.exists():
        raise FileExistsError(f"{path} already exists; append corrections with relabel().")
    hw4 = json.loads(_state.state_path("labels", f"{mode}.json").read_text(encoding="utf-8"))
    notes = _hw4_notes_by_trace()
    ts = _utcnow()
    records = [
        {
            "trace_id": row["trace_id"],
            "scenario_id": row.get("scenario_id"),
            "label": 0 if row["present"] else 1,
            "source": "human:hw4",
            "ts": ts,
            "label_id": f"{row['trace_id']}#0",
            "is_close_negative": row.get("is_close_negative", False),
            "evidence": notes.get(row["trace_id"], []),
        }
        for row in hw4
    ]
    _state.write_jsonl(path, records)
    return len(records)


TRACE_SOURCES = (
    ROOT / "traces" / "support_traces.json",       # Module 1 export (HW3 scenarios)
    ROOT / "traces" / "hw5_targeted_traces.json",  # HW5 targeted scenarios
    ROOT / "traces" / "hw5_targeted_traces_round2.json",  # HW5 targeted, round 2
)


def build_hw5_samples(
    to_review: dict[str, str],
    mode: str = MODE,
    trace_sources: tuple[str | Path, ...] = TRACE_SOURCES,
) -> int:
    """Write ``state/hw5_samples.json`` for the review interface's HW5 set.

    ``to_review`` maps scenario id -> why it needs a (re)label; those come
    first, followed by every trace already in the HW5 label file. The HW4
    review set in ``samples.json`` is read but left alone. It is the source
    for already-labeled traces because it also holds the HW4 replacement
    runs (``-r`` scenarios), which are not in the Module 1 export.
    """
    from analysis.helpers.tools import _load_trace_source

    traces = [t for src in trace_sources if Path(src).exists() for t in _load_trace_source(str(src))]
    by_scenario = {t["meta"].get("scenario_id"): t for t in traces}
    by_trace = {t["trace_id"]: t for t in traces}
    hw4_samples = _state.read_json(_state.state_path("samples.json"), default=[])
    by_trace.update({s["trace_id"]: s for s in hw4_samples})
    missing = [sid for sid in to_review if sid not in by_scenario]
    if missing:
        raise KeyError(f"scenarios not in {[str(s) for s in trace_sources]}: {missing}")

    picks: list[tuple[dict[str, Any], str]] = [
        (by_scenario[sid], reason) for sid, reason in to_review.items()
    ]
    seen = {t["trace_id"] for t, _ in picks}
    labeled = sorted(
        {r["trace_id"] for r in _state.read_jsonl(hw5_labels_path(mode))} - seen,
        key=lambda tid: by_trace[tid]["meta"].get("scenario_id", ""),
    )
    picks += [(by_trace[tid], "labeled (HW4 or HW5)") for tid in labeled]

    samples = [
        {
            "trace_id": t["trace_id"],
            "reason": reason,
            "trace": t["trace"],
            "text": t["text"],
            "features": t["features"],
            "meta": t["meta"],
            "permalink": t.get("permalink"),
            "flags": [],
        }
        for t, reason in picks
    ]
    _state.write_json(_state.state_path("hw5_samples.json"), samples)
    return len(samples)


def move_hw5_annotations() -> list[str]:
    """Move notes on HW5-only traces (in hw5_samples.json but not in the HW4
    samples.json) from annotations.json to hw5_annotations.json, so the HW4
    file holds only HW4 review notes.

    Notes on any other trace stay put, including HW4-era notes on traces that
    later left the HW4 sample. Backs up annotations.json to
    .annotation_backups/ first. Returns the ids moved.
    """
    import shutil

    hw4_ids = {s["trace_id"] for s in _state.read_json(_state.state_path("samples.json"), default=[])}
    hw5_ids = {s["trace_id"] for s in _state.read_json(_state.state_path("hw5_samples.json"), default=[])}
    src = _state.state_path("annotations.json")
    notes = _state.read_json(src, default=[])
    move = [a for a in notes if a.get("trace_id") in hw5_ids - hw4_ids]
    if not move:
        return []
    backup_dir = _state.state_path(".annotation_backups")
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    shutil.copy2(src, backup_dir / f"annotations_{stamp}_before_hw5_move.json")

    # Same format as the review server's writes, so the diff shows only the move.
    def write(path: Path, data: list[dict[str, Any]]) -> None:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    dst = _state.state_path("hw5_annotations.json")
    existing = _state.read_json(dst, default=[])
    have = {a.get("id") for a in existing}
    write(dst, existing + [a for a in move if a.get("id") not in have])
    moved = {a.get("id") for a in move}
    write(src, [a for a in notes if a.get("id") not in moved])
    return sorted(moved)


INPUTS_PATH = ROOT / "analysis" / "state" / "hw5_trace_inputs.json"
EXCLUDED_PATH = ROOT / "analysis" / "state" / "hw5_excluded_variants.json"


def _judge_message(m: dict[str, Any]) -> dict[str, Any] | None:
    """One message as the judge should see it: role plus text or tool data.

    The helper's flattener renders a tool call as its arguments only, which
    would hide which tool ran (the deciding fact for escalation). The tool
    name is therefore carried inside the rendered data as well.
    """
    role = m.get("role")
    if role in ("user", "assistant"):
        return {"role": role, "text": m.get("text", "")}
    if role == "tool_call":
        return {"role": "tool_call", "name": m.get("name"),
                "arguments": {"tool": m.get("name"), "arguments": m.get("arguments")}}
    if role == "tool_result":
        return {"role": "tool_result", "name": m.get("name"),
                "content": {"tool": m.get("name"), "result": m.get("content")}}
    if role == "turn_boundary":
        return {"role": "turn_boundary"}
    return None


def prepare_inputs(mode: str = MODE) -> int:
    """Save the judge inputs: one record per labeled, non-excluded conversation.

    Each record is {"trace_id", "trace": [messages]} with user turns, earlier
    turns, tool calls, tool results (policy text and order records), and
    replies. Labels, notes, evidence, scenario ids, expected outcomes, and
    other metadata are left out so nothing leaks the answer. Run once; every
    prompt version uses the same file.
    """
    if INPUTS_PATH.exists():
        raise FileExistsError(f"{INPUTS_PATH} already exists; keep it unchanged across prompt versions.")
    from analysis.helpers.tools import _load_trace_source

    by_trace = {t["trace_id"]: t for src in TRACE_SOURCES if Path(src).exists()
                for t in _load_trace_source(str(src))}
    # HW4 replacement runs (-r scenarios) are only in the HW4 sample set.
    by_trace.update({s["trace_id"]: s for s in _state.read_json(_state.state_path("samples.json"), default=[])})
    live: dict[str, dict[str, Any]] = {}
    for row in _state.read_jsonl(hw5_labels_path(mode)):
        live[row["trace_id"]] = row
    excluded = {e["trace_id"] for e in json.loads(EXCLUDED_PATH.read_text(encoding="utf-8"))["excluded"]}
    eligible = sorted(tid for tid in live if tid not in excluded)
    missing = [tid for tid in eligible if tid not in by_trace]
    if missing:
        raise KeyError(f"no trace content for labeled ids: {missing[:5]}")
    records = []
    for tid in eligible:
        messages = [jm for m in by_trace[tid]["trace"] if (jm := _judge_message(m)) is not None]
        records.append({"trace_id": tid, "trace": messages})
    INPUTS_PATH.write_text(json.dumps(records, indent=1, ensure_ascii=False), encoding="utf-8")
    return len(records)


def split_data(mode: str = MODE) -> dict[str, list[str]]:
    """Split the eligible labels 20/40/40 (train/dev/test) with split_labels. Run once.

    Eligible ids are exactly the records in hw5_trace_inputs.json. The
    assignment is saved under ``mode`` in state/splits.json and must stay
    unchanged during development.
    """
    from analysis.helpers import split_labels

    existing = _state.read_json(_state.state_path("splits.json"), default={})
    if mode in existing:
        raise FileExistsError(f"splits.json already has '{mode}'; keep the split unchanged.")
    records = json.loads(INPUTS_PATH.read_text(encoding="utf-8"))
    return split_labels(
        mode,
        fractions=(0.20, 0.40, 0.40),
        seed=7,
        min_per_class=10,
        eligible_trace_ids=[record["trace_id"] for record in records],
    )


JUDGE_MODEL = "gpt-4o-mini"  # handout: same judge model for development and test
REPORT_DIR = ROOT / "analysis" / "report"


def _load_env() -> None:
    """Load model keys from .env (values are never printed)."""
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env", override=False)


def register_version(prompt_path: str | Path, mode: str = MODE) -> dict[str, str]:
    """Register a saved prompt file as the next judge version (offline, no model call)."""
    from analysis.helpers import register_judge

    text = Path(prompt_path).read_text(encoding="utf-8")
    for seq in ("{{", "{%", "{#"):
        if seq in text:
            raise ValueError(f"prompt contains Jinja sequence {seq!r}; DocETL would render it")
    return register_judge(mode, text, judge_model=JUDGE_MODEL)


def run_development(judge_id: str) -> dict[str, Any]:
    """Run a registered judge on the dev split (live model) and save
    analysis/report/dev-<judge_id>.json with TPR, TNR, Wilson intervals,
    confusion counts, and disagreement ids."""
    from analysis.helpers import judge_alignment, run_judge

    _load_env()
    run_judge(judge_id, split="dev", batch_size=10)
    result = judge_alignment(judge_id, "dev")
    result["judge_model"] = JUDGE_MODEL
    result["saved_at"] = _utcnow()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / f"dev-{judge_id}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def run_test(judge_id: str) -> dict[str, Any]:
    """Run a frozen judge once on the test split (live model) and save
    analysis/report/test-<judge_id>.json. judge_alignment refuses the test
    split unless the judge is frozen."""
    from analysis.helpers import judge_alignment, run_judge

    _load_env()
    run_judge(judge_id, split="test", batch_size=10)
    result = judge_alignment(judge_id, "test")
    result["judge_model"] = JUDGE_MODEL
    result["saved_at"] = _utcnow()
    (REPORT_DIR / f"test-{judge_id}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def relabel(
    trace_id: str,
    label: int,
    reason: str,
    mode: str = MODE,
    scenario_id: str | None = None,
) -> dict[str, Any]:
    """Append a human label (new trace or correction). Earlier records stay in
    the file; the helpers use the last record written for each trace."""
    if label not in (0, 1):
        raise ValueError("label must be 1 (Pass) or 0 (Fail)")
    path = hw5_labels_path(mode)
    prior = [r for r in _state.read_jsonl(path) if r["trace_id"] == trace_id]
    record = {
        "trace_id": trace_id,
        "scenario_id": scenario_id or (prior[-1].get("scenario_id") if prior else None),
        "label": label,
        "source": "human:hw5",
        "ts": _utcnow(),
        "label_id": f"{trace_id}#{len(prior)}",
        "evidence": [{"note": reason}],
    }
    _state.append_jsonl(path, record)
    return record


def recalc_test(judge_id: str = f"{MODE}-v0") -> dict[str, Any]:
    """Recompute test metrics from the saved predictions and labels.

    Offline: no model call and nothing is written (judge_alignment on test
    only reads). For the video: ``uv run python -m analysis.run_judges recalc``.
    """
    from analysis.helpers import judge_alignment

    r = judge_alignment(judge_id, "test")
    n_pass, n_fail = r["tp"] + r["fn"], r["tn"] + r["fp"]
    tpr_lo, tpr_hi = r["tpr_interval"]
    tnr_lo, tnr_hi = r["tnr_interval"]
    print(f"{judge_id} on test: {r['n']} traces ({n_pass} Pass, {n_fail} Fail)")
    print(f"TP {r['tp']}  FN {r['fn']}  TN {r['tn']}  FP {r['fp']}")
    print(f"TPR {r['tp']}/{n_pass} = {r['tpr']:.2f}  [{tpr_lo:.2f}, {tpr_hi:.2f}]")
    print(f"TNR {r['tn']}/{n_fail} = {r['tnr']:.2f}  [{tnr_lo:.2f}, {tnr_hi:.2f}]")
    return r


if __name__ == "__main__":
    import sys

    if sys.argv[1:2] == ["recalc"]:
        recalc_test(*sys.argv[2:3])
    else:
        print("usage: uv run python -m analysis.run_judges recalc [judge_id]")
