"""Push Homework 4 Part E's present/absent labels to Langfuse as scores.

Each label file under analysis/state/labels/<mode>.json holds one row per
gradable trace: {trace_id, scenario_id, batch, present, is_close_negative}.
This writes each row as a numeric 0/1 score named after the mode, attached to
its trace, so the labels live in Langfuse (the canonical store) and not only
in the local JSON files.

Reuses a single Langfuse client and flushes once at the end rather than once
per score (analysis/helpers/langfuse_io.write_label_score flushes per call,
which is fine for interactive single writes but too slow for ~900 of them
here).

Usage:
    uv run python scripts/push_labels_to_langfuse.py
"""

from __future__ import annotations

import json
from pathlib import Path

from analysis.helpers import langfuse_io
from observability.instrument import load_env

REPO_ROOT = Path(__file__).resolve().parents[1]
LABELS_DIR = REPO_ROOT / "analysis" / "state" / "labels"


def main() -> None:
    load_env()
    if not langfuse_io.is_configured():
        raise SystemExit(
            "Langfuse is not configured (.env needs LANGFUSE_PUBLIC_KEY / "
            "LANGFUSE_SECRET_KEY / LANGFUSE_HOST)"
        )

    from langfuse import Langfuse

    lf = Langfuse()

    label_files = sorted(LABELS_DIR.glob("*.json"))
    if not label_files:
        raise SystemExit(f"no label files found under {LABELS_DIR}")

    total = 0
    for path in label_files:
        mode = path.stem
        rows = json.loads(path.read_text(encoding="utf-8"))
        for row in rows:
            langfuse_id = langfuse_io.logical_to_langfuse_id(row["trace_id"], lf)
            comment = "close negative" if row.get("is_close_negative") else None
            lf.create_score(
                name=mode,
                value=int(row["present"]),
                trace_id=langfuse_id,
                data_type="NUMERIC",
                comment=comment,
            )
            total += 1
        print(f"queued {len(rows)} scores for {mode}")

    print(f"flushing {total} scores to Langfuse...")
    lf.flush()
    print("done")


if __name__ == "__main__":
    main()
