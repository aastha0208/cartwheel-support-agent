"""Monitor one failure mode over a Langfuse time window.

Usage:
    uv run python -m monitoring.run --period before [--dry-run]
    uv run python -m monitoring.run --period after [--dry-run]
    uv run python -m monitoring.run --last-hours 24 [--dry-run]

A period comes from ``monitoring/config.json`` and must contain exactly one
completed conversation for each of the 50 monitoring scenarios, all on the
configured Cartwheel model. ``--last-hours`` reads recent traffic instead and
keeps every completed conversation on that model.

Steps: fetch the window's traces, group the per-turn traces into
conversations, build the Homework 5 judge text, select the random sample and
risk groups, show the counts, then (unless ``--dry-run``) judge the union
once with the frozen judge and save the random and risk verdicts separately.
Verdicts use 1 = failure present, 0 = absent.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from monitoring.sample import DEFAULT_RISK_GROUPS, select_traces

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "monitoring" / "config.json"
SCENARIOS_PATH = ROOT / "scenarios" / "monitoring_scenarios.jsonl"
OUTPUT_DIR = ROOT / "monitoring" / "output"
HISTORY_PATH = ROOT / "monitoring" / "history.jsonl"
CHART_PATH = ROOT / "monitoring" / "prevalence.svg"


class PeriodError(ValueError):
    """The window cannot be monitored as one comparable period."""


def load_config() -> dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def monitored_scenario_ids() -> set[str]:
    lines = SCENARIOS_PATH.read_text(encoding="utf-8").splitlines()
    return {json.loads(line)["id"] for line in lines if line.strip()}


def _scenario_of(summary: Any) -> str | None:
    metadata = summary.metadata or {}
    attributes = metadata.get("attributes", {}) if isinstance(metadata, dict) else {}
    return attributes.get("cartwheel.scenario_id") or metadata.get("cartwheel.scenario_id")


def fetch_window(
    start: datetime, end: datetime, scenario_ids: set[str] | None = None
) -> list[dict[str, Any]]:
    """Normalized per-turn traces whose timestamp falls in [start, end].

    With ``scenario_ids``, traces from other scenarios that ran in the same
    window are skipped before their full records are fetched.
    """
    from analysis.helpers.langfuse_io import _client
    from analysis.helpers.normalization import normalize_trace

    lf = _client()
    summaries: list[Any] = []
    page = 1
    while True:
        resp = lf.api.trace.list(
            from_timestamp=start, to_timestamp=end, limit=100, page=page
        )
        summaries.extend(resp.data or [])
        if page >= (resp.meta.total_pages or 1):
            break
        page += 1
    if scenario_ids is not None:
        summaries = [s for s in summaries if _scenario_of(s) in scenario_ids]
    turns = []
    for summary in summaries:
        try:
            turns.append(normalize_trace(lf.api.trace.get(summary.id)))
        except ValueError:
            if scenario_ids is not None:
                raise
            # Daily traffic can include traces that are not Cartwheel turns
            # (no messages); they cannot be judged, so they are left out.
    return turns


def _model_ok(observed: str, configured: str) -> bool:
    from agent.agent import LITELLM_COURSE_MODELS

    return observed in {configured, LITELLM_COURSE_MODELS.get(configured, configured)}


def _completed(turn: dict[str, Any]) -> bool:
    """A turn completed when the agent produced a reply (errored turns have none)."""
    return turn.get("output") is not None and any(
        m.get("role") == "assistant" and str(m.get("text", "")).strip()
        for m in turn["trace"]
    )


def judge_text(messages: list[dict[str, Any]]) -> str:
    """The conversation text exactly as the Homework 5 judge saw it.

    Same two steps as ``analysis.run_judges.prepare_inputs`` plus the
    judge's own loader: keep user turns, replies, tool calls and tool results
    (with tool names), drop thinking, then flatten with ``normalize_trace``.
    No labels, notes, or scenario metadata are included.
    """
    from analysis.helpers.normalization import normalize_trace
    from analysis.run_judges import _judge_message

    kept = [jm for m in messages if (jm := _judge_message(m)) is not None]
    return normalize_trace({"trace_id": "conversation", "trace": kept})["text"]


def build_conversations(
    turns: list[dict[str, Any]], model: str, strict_model: bool = True
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Group per-turn traces by session into conversation records.

    Each record uses the final turn's trace ID as its ID (so the score lands
    on the last turn) and carries the tools called and the number of user
    turns, taken from the trace itself. Conversations with an errored turn
    are excluded. A conversation on another model rejects a comparison
    period (``strict_model``); in daily monitoring it is skipped and counted.
    Returns the records and counts of what was excluded.
    """
    by_session: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for turn in turns:
        key = turn["meta"].get("session_id") or turn["meta"].get("scenario_id") or turn["trace_id"]
        by_session[key].append(turn)

    records: list[dict[str, Any]] = []
    skipped = {"errored": 0, "other_model": 0}
    for session_id, group in by_session.items():
        group.sort(key=lambda t: t.get("timestamp") or "")
        if not all(_completed(t) for t in group):
            skipped["errored"] += 1
            continue
        messages = [m for t in group for m in t["trace"]]
        models = sorted({m for t in group for m in t.get("models", [])})
        wrong = [m for m in models if not _model_ok(m, model)]
        if wrong and strict_model:
            raise PeriodError(f"session {session_id} used {wrong}, not {model}")
        if wrong or not models:
            skipped["other_model"] += 1
            continue
        records.append({
            "id": group[-1]["trace_id"],
            "session_id": session_id,
            "scenario_id": group[0]["meta"].get("scenario_id"),
            "trace_ids": [t["trace_id"] for t in group],
            "models": models,
            "tools": sorted({str(m["name"]) for m in messages if m.get("role") == "tool_call" and m.get("name")}),
            "turn_count": sum(m.get("role") == "user" for m in messages),
            "timestamp": group[-1].get("timestamp"),
            "text": judge_text(messages),
        })
    records.sort(key=lambda r: (r["scenario_id"] or "", r["id"]))
    return records, skipped


def check_period(records: list[dict[str, Any]], scenario_ids: set[str]) -> None:
    """Exactly one completed conversation for each monitored scenario."""
    counts: dict[str, int] = defaultdict(int)
    for record in records:
        counts[record["scenario_id"]] += 1
    missing = sorted(scenario_ids - set(counts))
    repeated = sorted(s for s, n in counts.items() if n > 1)
    if missing:
        raise PeriodError(f"{len(missing)} scenario(s) have no completed conversation: {missing[:5]}")
    if repeated:
        raise PeriodError(f"scenario(s) with more than one completed conversation (separate retries?): {repeated[:5]}")


def conversation_summaries(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per-conversation facts kept with a run's output (no conversation text)."""
    keys = ("id", "scenario_id", "session_id", "trace_ids", "tools", "turn_count", "timestamp")
    return [{key: record[key] for key in keys} for record in records]


def risk_groups_for(config: dict[str, Any]) -> dict[str, Any]:
    unknown = [g for g in config["risk_groups"] if g not in DEFAULT_RISK_GROUPS]
    if unknown:
        raise ValueError(f"unknown risk groups in config: {unknown}")
    return {name: DEFAULT_RISK_GROUPS[name] for name in config["risk_groups"]}


def run(label: str, start: datetime, end: datetime, check_scenarios: bool, dry_run: bool) -> dict[str, Any]:
    config = load_config()
    scenario_ids = monitored_scenario_ids() if check_scenarios else None
    print(f"[{label}] window {start.isoformat()} to {end.isoformat()}")
    print(f"[{label}] judge {config['judge_id']} | Cartwheel model {config['model']}")

    turns = fetch_window(start, end, scenario_ids)
    records, skipped = build_conversations(turns, config["model"], strict_model=check_scenarios)
    if scenario_ids is not None:
        check_period(records, scenario_ids)
    print(f"[{label}] {len(turns)} Langfuse traces -> {len(records)} completed conversations "
          f"({skipped['errored']} with an errored turn excluded"
          + (f", {skipped['other_model']} on another model skipped" if skipped["other_model"] else "") + ")")

    result: dict[str, Any] = {
        "label": label,
        "judge_id": config["judge_id"],
        "mode": config["judge_mode"],
        "model": config["model"],
        "window": {"from": start.isoformat(), "to": end.isoformat()},
        "n_traces": len(turns),
        "n_conversations": len(records),
        "n_excluded_errored": skipped["errored"],
        "n_excluded_other_model": skipped["other_model"],
    }
    if not records:
        print(f"[{label}] no eligible conversations; nothing to judge")
        result.update({"n_random": 0, "n_risk": 0, "n_judged": 0})
        if not dry_run:
            save(result)
        return result

    plan = select_traces(records, config["random_rate"], risk_groups_for(config))
    risk_ids = {t["id"] for members in plan["risk_groups"].values() for t in members}
    result["conversations"] = conversation_summaries(records)
    result.update({
        "n_random": len(plan["random"]),
        "n_risk": len(risk_ids),
        "n_judged": len(plan["to_judge"]),
        "random_ids": [t["id"] for t in plan["random"]],
        "risk_groups": {name: [t["id"] for t in members] for name, members in plan["risk_groups"].items()},
    })
    print(f"[{label}] random sample: {len(plan['random'])}")
    for name, members in plan["risk_groups"].items():
        print(f"[{label}] risk group {name}: {len(members)}")
    overlap = len({t['id'] for t in plan['random']} & risk_ids)
    print(f"[{label}] judge calls: {len(plan['to_judge'])} "
          f"({len(plan['random'])} random + {len(risk_ids)} risk - {overlap} in both) "
          f"on {config['judge_id']}")

    if dry_run:
        print(f"[{label}] dry run: stopping before the judge")
        return result

    from monitoring.correct import corrected_mode_prevalence
    from monitoring.run_judges import judge_sample, judge_test_data
    from monitoring.write_scores import post_scores

    verdicts = judge_sample(config["judge_id"], plan["to_judge"])
    result["random_verdicts"] = {tid: verdicts[tid] for tid in result["random_ids"]}
    result["risk_verdicts"] = {tid: verdicts[tid] for tid in sorted(risk_ids)}
    print(f"[{label}] random sample flagged {sum(result['random_verdicts'].values())}/{len(result['random_verdicts'])}; "
          f"risk flagged {sum(result['risk_verdicts'].values())}/{len(result['risk_verdicts'])}")

    # Only the random verdicts estimate the failure rate.
    test_labels, test_preds = judge_test_data(config["judge_id"])
    estimate = corrected_mode_prevalence(list(result["random_verdicts"].values()), test_labels, test_preds)
    result["estimate"] = estimate
    result["threshold"] = config["threshold"]
    result["crossed_threshold"] = estimate["corrected"] > config["threshold"]
    print(f"[{label}] raw {estimate['raw']} -> corrected {estimate['corrected']} "
          f"(95% CI {estimate['ci_low']}-{estimate['ci_high']}); threshold {config['threshold']}: "
          f"{'CROSSED' if result['crossed_threshold'] else 'not crossed'}")

    result["n_scores_posted"] = post_scores(score_records(config, result, label))
    print(f"[{label}] posted {result['n_scores_posted']} scores to Langfuse")
    save(result)
    return result


def score_records(config: dict[str, Any], result: dict[str, Any], label: str) -> list[dict[str, Any]]:
    """Score records for one run; the period-level rate goes on a monitor session.

    Each score is dated by what it measures, so dashboards plot it over time:
    a verdict at its conversation's last turn, the period rate at the end of
    the window.
    """
    from monitoring.write_scores import build_score_records

    records = build_score_records(config["judge_mode"], result["random_verdicts"],
                                  result["risk_verdicts"], result["estimate"], label)
    when = {c["id"]: c.get("timestamp") for c in result.get("conversations", [])}
    for record in records:
        if record["trace_id"] is None:
            record["session_id"] = f"hw7-monitor-{config['judge_mode']}"
            record["timestamp"] = result["window"]["to"]
        else:
            record["timestamp"] = when.get(record["trace_id"])
    return records


def save(result: dict[str, Any]) -> None:
    """Write the run's details, its history line, and the chart."""
    label = result["label"]
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTPUT_DIR / f"{label}.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")

    estimate = result.get("estimate", {})
    line = {
        "label": label,
        "judge_id": result["judge_id"],
        "model": result["model"],
        "window": result["window"],
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "n_traces": result["n_traces"],
        "n_conversations": result["n_conversations"],
        "n_random": result["n_random"],
        "n_risk": result["n_risk"],
        "n_judged": result["n_judged"],
        **{key: estimate.get(key) for key in (
            "raw", "corrected", "ci_low", "ci_high", "confidence",
            "failure_sensitivity", "pass_specificity")},
        "threshold": result.get("threshold"),
        "crossed_threshold": result.get("crossed_threshold"),
    }
    # One line per label: a rerun of a period replaces its earlier line.
    history = [json.loads(x) for x in HISTORY_PATH.read_text(encoding="utf-8").splitlines() if x.strip()] \
        if HISTORY_PATH.exists() else []
    history = [h for h in history if h["label"] != label] + [line]
    order = {p["label"]: i for i, p in enumerate(load_config()["periods"])}
    history.sort(key=lambda h: (order.get(h["label"], len(order)), h["run_at"]))
    HISTORY_PATH.write_text("".join(json.dumps(h) + "\n" for h in history), encoding="utf-8")

    from monitoring.chart import prevalence_chart

    points = [h for h in history if h.get("corrected") is not None]
    if points:
        config = load_config()
        CHART_PATH.write_text(prevalence_chart(points, config["threshold"], config["judge_mode"]), encoding="utf-8")
    print(f"[{label}] saved {out.name}, {HISTORY_PATH.name}, {CHART_PATH.name} in {out.parent}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    which = parser.add_mutually_exclusive_group(required=True)
    which.add_argument("--period", help="a period label from monitoring/config.json")
    which.add_argument("--last-hours", type=float, help="monitor the most recent N hours")
    parser.add_argument("--dry-run", action="store_true", help="show the counts and stop before the judge")
    args = parser.parse_args(argv)

    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    config = load_config()
    if args.period:
        periods = {p["label"]: p for p in config["periods"]}
        if args.period not in periods:
            parser.error(f"unknown period {args.period!r}; choose from {sorted(periods)}")
        period = periods[args.period]
        label, start, end, check = args.period, _parse_time(period["from"]), _parse_time(period["to"]), True
    else:
        end = datetime.now(timezone.utc)
        start = end - timedelta(hours=args.last_hours)
        label, check = f"last-{args.last_hours:g}h-{end:%Y%m%dT%H%M}Z", False
    try:
        run(label, start, end, check, args.dry_run)
    except PeriodError as exc:
        print(f"[{label}] period rejected: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
