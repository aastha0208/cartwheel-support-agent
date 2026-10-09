"""Build the review app's "HW7 monitor" sample set from the monitor's runs.

Reads monitoring/output/<label>.json for each configured period, fetches the
listed traces from Langfuse (read-only, no model calls), merges each
conversation's turns, and writes analysis/state/hw7_samples.json. Each sample
uses the monitor's conversation ID, so the Monitor periods view can open it in
the trace tab. The reason line says the period, how the conversation was
selected, and the judge's verdict.

    uv run python scripts/build_hw7_review_set.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUTPUT_DIR = ROOT / "monitoring" / "output"
CONFIG = ROOT / "monitoring" / "config.json"
TARGET = ROOT / "analysis" / "state" / "hw7_samples.json"


def _reason(label: str, conv_id: str, run: dict) -> str:
    random_ids = set(run.get("random_ids", []))
    groups = [g for g, ids in run.get("risk_groups", {}).items() if conv_id in ids]
    picked = []
    if conv_id in random_ids:
        picked.append("random sample")
    if groups:
        picked.append("risk groups: " + ", ".join(groups))
    verdicts = {**run.get("risk_verdicts", {}), **run.get("random_verdicts", {})}
    verdict = {1: "judge: Fail", 0: "judge: Pass"}.get(verdicts.get(conv_id), "not judged")
    return f"HW7 {label} · " + (" · ".join(picked) or "not selected") + f" · {verdict}"


def main() -> int:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    from analysis.helpers.langfuse_io import _client
    from analysis.helpers.normalization import merge_traces, normalize_trace

    lf = _client()
    labels = [p["label"] for p in json.loads(CONFIG.read_text(encoding="utf-8"))["periods"]]
    samples = []
    for label in labels:
        path = OUTPUT_DIR / f"{label}.json"
        if not path.exists():
            continue
        run = json.loads(path.read_text(encoding="utf-8"))
        for conv in run.get("conversations", []):
            turns = [normalize_trace(lf.api.trace.get(tid)) for tid in conv["trace_ids"]]
            (merged,) = merge_traces(turns)
            samples.append({
                "trace_id": conv["id"],
                "reason": _reason(label, conv["id"], run),
                "trace": merged["trace"],
                "text": merged["text"],
                "features": merged["features"],
                "meta": {**merged["meta"], "hw7_period": label},
                "permalink": None,
                "flags": [],
            })
        print(f"{label}: {len(run.get('conversations', []))} conversations")
    TARGET.write_text(json.dumps(samples, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {len(samples)} samples to {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
