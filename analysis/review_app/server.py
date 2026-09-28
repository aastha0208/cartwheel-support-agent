"""File-backed review server for Homework 4 (adapted from the reference server).

Same design as ``analysis/server.py``: a Python standard-library HTTP server
(no dependencies) serving the single-file HTML app in ``ui/`` and a small
JSON API over plain files. The human annotates in the browser, the app
auto-saves every change here, and a coding agent can watch
``state/annotations.json`` on a poll loop (see the error-discovery skill's
review-loop.md) to group notes into a taxonomy.

Two differences from the reference server, both deliberate:

1. ``STATE_DIR`` points at the *shared* ``analysis/state/`` directory, two
   levels up from this file, not a local ``review_app/state/``. The handout's
   "Files to commit" list names ``analysis/state/sample_manifest.json``,
   ``analysis/state/annotations.json``, etc. — the same state directory the
   reference server and ``analysis/helpers`` already use. Populating
   ``samples.json`` itself is Part B's sampling work
   (``analysis.helpers.tools.select_traces``, already implemented), not this
   server's job — this stays a dumb file-backed API, same contract as the
   reference.
2. Default port is 8021, not 8020, so this can run alongside the reference
   server (``analysis/server.py``) for side-by-side comparison, per Part A of
   the homework.

Langfuse is the canonical store for traces and accepted labels. The state
files are an inspectable local mirror and hold workflow state that does not
belong in the trace store.

API (kept compatible with the reference server so the UI's fetch calls work
unchanged):

    GET  /                    the HTML review app
    GET  /api/samples         current sample set (+ manifest of why picked)
    POST /api/samples         push a new or updated sample set
    GET  /api/annotations     current human annotations
    POST /api/annotations     save annotations (the app posts on every change)
    GET  /api/graph           the 2D projection of all traces for the map view
    GET  /api/patterns        the taxonomy as the agent currently holds it
    POST /api/patterns        push the updated taxonomy
    GET  /api/suggestions     agent depth-scan suggestions awaiting accept/reject
    GET  /api/scenarios       read-only {id, intent, role} for every HW3 scenario,
                               for the Batch Ledger's coverage view
    POST /api/suggestions     push suggestions

Run it:

    uv run python analysis/review_app/server.py                # serve on :8021
    uv run python analysis/review_app/server.py --port 8022
    uv run python analysis/review_app/server.py --replay analysis/state/demo_annotations.json
"""

from __future__ import annotations

import argparse
import json
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
STATE_DIR = HERE.parent / "state"
UI_DIR = HERE / "ui"
# The full HW3 scenario set, for the Batch Ledger's coverage view -- read-only
# reference data (not writable via this API), so it stays outside API_FILES.
SCENARIOS_PATH = HERE.parent.parent / "scenarios" / "support_scenarios.jsonl"
# Every version of annotations.json ever overwritten gets copied here first,
# so an accidental delete-click or bad edit is always one file away from
# recovery, not gone the moment the next save fires.
ANNOTATION_BACKUP_DIR = STATE_DIR / ".annotation_backups"
MAX_ANNOTATION_BACKUPS = 200

# API path -> the state file that backs it. GET reads the file, POST overwrites
# it. Keeping this a plain table makes the whole contract inspectable and keeps
# the handler tiny.
API_FILES: dict[str, Path] = {
    "/api/samples": STATE_DIR / "samples.json",
    "/api/annotations": STATE_DIR / "annotations.json",
    "/api/graph": STATE_DIR / "graph.json",
    "/api/patterns": STATE_DIR / "patterns.json",
    "/api/suggestions": STATE_DIR / "suggestions.json",
}

# Default empty document per endpoint, so a fresh checkout serves valid JSON
# before the agent has written anything. samples/annotations/suggestions are
# lists; graph and patterns are objects.
API_DEFAULTS: dict[str, Any] = {
    "/api/samples": [],
    "/api/annotations": [],
    "/api/graph": {"nodes": [], "clusters": []},
    "/api/patterns": {},
    "/api/suggestions": [],
}


def _read_json(path: Path, default: Any) -> Any:
    """Return the parsed JSON at ``path``, or ``default`` if missing or bad.

    A half-written file (the app crashed mid-save) reads as the default rather
    than crashing the server; the next good POST repairs it.

    ``encoding="utf-8"`` is required, not cosmetic: ``Path.read_text()``
    without it falls back to the OS locale encoding, which on Windows is
    typically cp1252, not UTF-8. A state file containing a real non-ASCII
    character (an emoji, an em dash, a curly quote) then reads back as
    mojibake — each UTF-8 byte misread as its own cp1252 character.
    """
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def _write_json(path: Path, data: Any) -> None:
    """Write ``data`` to ``path`` atomically (write temp, then replace).

    ``encoding="utf-8"`` matches ``_read_json``. Harmless today, since
    ``json.dumps`` escapes non-ASCII into ``\\uXXXX`` by default (plain ASCII
    either way) — but explicit rather than relying on that default staying
    true forever.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)


def _backup_annotations() -> None:
    """Copy the current annotations.json to a timestamped file before it
    gets overwritten. Every save (including an accidental delete-click)
    creates a new on-disk version instead of destroying the old one, so
    recovery is "find the right backup file," not "it's gone." Keeps only
    the most recent MAX_ANNOTATION_BACKUPS to avoid growing unbounded.
    """
    src = API_FILES["/api/annotations"]
    if not src.exists():
        return
    ANNOTATION_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    dest = ANNOTATION_BACKUP_DIR / f"annotations_{ts}.json"
    dest.write_bytes(src.read_bytes())
    backups = sorted(ANNOTATION_BACKUP_DIR.glob("annotations_*.json"))
    for old in backups[: -MAX_ANNOTATION_BACKUPS]:
        old.unlink(missing_ok=True)


class ReviewHandler(BaseHTTPRequestHandler):
    """Serves the UI and the file-backed JSON API."""

    # Quiet by default; the agent narrates the session, not the access log.
    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A002
        return

    # -- helpers ----------------------------------------------------------

    def _send_json(self, data: Any, status: int = 200) -> None:
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        # Local single-user tool; permissive CORS keeps a file:// or
        # different-port UI from tripping over the browser same-origin check.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, content_type: str) -> None:
        if not path.exists():
            self._send_json({"error": f"not found: {path.name}"}, status=404)
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> Any:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return None
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    # -- routes -----------------------------------------------------------

    def do_OPTIONS(self) -> None:  # noqa: N802  (http.server naming)
        self._send_json({}, status=204)

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]

        if path in ("/", "/index.html"):
            self._send_file(UI_DIR / "index.html", "text/html; charset=utf-8")
            return

        # Any other static asset the UI references (kept single-file by
        # default, but this lets an adapted UI ship a companion file).
        if path.startswith("/ui/"):
            asset = UI_DIR / path[len("/ui/"):]
            if asset.is_file() and UI_DIR in asset.resolve().parents:
                self._send_file(asset, _guess_type(asset))
                return

        if path in API_FILES:
            data = _read_json(API_FILES[path], API_DEFAULTS[path])
            self._send_json(data)
            return

        if path == "/api/scenarios":
            self._send_json(_read_scenarios_lite())
            return

        self._send_json({"error": f"unknown path: {path}"}, status=404)

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path not in API_FILES:
            self._send_json({"error": f"cannot POST to {path}"}, status=404)
            return
        data = self._read_body()
        if data is None:
            self._send_json({"error": "expected a JSON body"}, status=400)
            return
        synced = 0
        if path == "/api/annotations":
            _backup_annotations()
            try:
                synced = _sync_annotation_scores(data)
            except Exception as exc:  # pragma: no cover - network-only path
                # Preserve a resumable local copy, but tell the client that
                # the canonical write did not complete.
                _write_json(API_FILES[path], data)
                self._send_json(
                    {
                        "error": f"Langfuse score write failed: {exc}",
                        "cached_locally": True,
                    },
                    status=502,
                )
                return
        _write_json(API_FILES[path], data)
        result = {"ok": True, "count": _count(data)}
        if synced:
            result["langfuse_scores_written"] = synced
        self._send_json(result)


def _count(data: Any) -> int:
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        return len(data)
    return 0


def _annotation_list(data: Any) -> list[dict[str, Any]]:
    """Normalize the annotations payload (a bare list or ``{"annotations": []}``)."""
    if isinstance(data, dict):
        data = data.get("annotations", [])
    return [a for a in data if isinstance(a, dict)] if isinstance(data, list) else []


def _sync_annotation_scores(data: Any) -> int:
    """Write labeled annotations to Langfuse scores when configured.

    Langfuse is canonical when configured, while ``annotations.json`` is the
    local mirror. The function does nothing when the ``LANGFUSE_*``
    environment is absent, so the offline demo, the ``--replay`` path, and the
    test suite never make a network call here. An annotation is written as a
    score only when it carries both a ``mode`` and a 0/1 ``label`` (a
    per-trace binary verdict); free-text-only notes are stored on disk but
    have nothing to score against.

    Return the number of scores written, or zero in offline mode. Propagate a
    Langfuse error so the server can report that the canonical write failed.
    """
    try:
        from analysis.helpers import langfuse_io
    except Exception:
        return 0
    if not langfuse_io.is_configured():
        return 0

    written = 0
    client = langfuse_io._client()
    for ann in _annotation_list(data):
        trace_id = ann.get("trace_id")
        mode = ann.get("mode")
        label = ann.get("label")
        if not trace_id or not mode or label not in (0, 1, "0", "1"):
            continue
        langfuse_io.write_label_score(
            trace_id=str(trace_id),
            mode=str(mode),
            label=int(label),
            comment=ann.get("note"),
            client=client,
        )
        written += 1
    return written


def _read_scenarios_lite() -> list[dict[str, Any]]:
    """Read the coverage-relevant fields per scenario from the full HW3 dataset.

    Lightweight on purpose: the Batch Ledger only needs these fields to show
    coverage by category, not the full opening_message/expected payload.
    """
    if not SCENARIOS_PATH.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in SCENARIOS_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        tup = d.get("tuple", {})
        out.append(
            {
                "id": d.get("id"),
                "intent": tup.get("intent"),
                "role": tup.get("role"),
                "difficulty": tup.get("difficulty"),
                "scenario_group": d.get("scenario_group"),
                "data_quality_case_id": d.get("data_quality_case_id"),
                "tools_needed": tup.get("tools_needed"),
                "user_style": tup.get("user_style"),
            }
        )
    return out


def _guess_type(path: Path) -> str:
    return {
        ".html": "text/html; charset=utf-8",
        ".css": "text/css",
        ".js": "text/javascript",
        ".json": "application/json",
        ".svg": "image/svg+xml",
    }.get(path.suffix, "application/octet-stream")


# ---------------------------------------------------------------------------
# Demo replay: append canned annotations on a timer.
# ---------------------------------------------------------------------------


def _load_canned(replay_path: Path) -> list[Any]:
    """Read the canned annotations, accepting either on-disk shape.

    The committed demo file wraps its list as ``{"annotations": [...]}`` (it
    carries a little metadata alongside), while an ad-hoc file may be a bare
    list. Accept both so the demo fallback does not care which the course seed
    produced. Each annotation is given a stable ``id`` if it lacks one, so the
    UI's id-based merge and de-duplication work on replayed items.
    """
    raw = _read_json(replay_path, None)
    if isinstance(raw, dict):
        raw = raw.get("annotations", [])
    if not isinstance(raw, list):
        return []
    out: list[Any] = []
    for i, ann in enumerate(raw):
        if isinstance(ann, dict) and "id" not in ann:
            ann = {**ann, "id": f"replay-{i}"}
        out.append(ann)
    return out


def _replay_annotations(replay_path: Path, interval: float) -> None:
    """Append the canned annotations to state/annotations.json on a timer.

    Reads the whole canned list up front, then adds one annotation every
    ``interval`` seconds. The watcher and the UI both poll annotations.json, so
    grouping and the suggestion pipeline fire exactly as they would in a live
    session. Idempotent enough for a demo: it starts from an empty live file so
    a re-run replays from the top.
    """
    canned = _load_canned(replay_path)
    if not canned:
        print(f"[replay] nothing to replay from {replay_path}")
        return
    live_path = API_FILES["/api/annotations"]
    _write_json(live_path, [])
    print(f"[replay] replaying {len(canned)} annotations, one per {interval:g}s")
    accumulated: list[Any] = []
    for i, ann in enumerate(canned, start=1):
        time.sleep(interval)
        accumulated.append(ann)
        _write_json(live_path, accumulated)
        note = ann.get("note", "") if isinstance(ann, dict) else ""
        print(f"[replay] {i}/{len(canned)}: {note[:70]}")
    print("[replay] done")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8021)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument(
        "--replay",
        metavar="PATH",
        help="canned annotations file to replay on a timer (e.g. "
        "analysis/state/demo_annotations.json), for the demo fallback",
    )
    parser.add_argument(
        "--replay-interval",
        type=float,
        default=4.0,
        help="seconds between replayed annotations (default 4)",
    )
    args = parser.parse_args()

    STATE_DIR.mkdir(parents=True, exist_ok=True)

    if args.replay:
        # Relative to the current directory (the repo root, per the project's
        # own convention), not to this file's location under review_app/ —
        # so `--replay analysis/state/demo_annotations.json`, as documented
        # above, resolves correctly.
        replay_path = Path(args.replay)
        thread = threading.Thread(
            target=_replay_annotations,
            args=(replay_path, args.replay_interval),
            daemon=True,
        )
        thread.start()

    server = ThreadingHTTPServer((args.host, args.port), ReviewHandler)
    url = f"http://{args.host}:{args.port}/"
    print(f"review interface on {url}")
    print(f"serving state from {STATE_DIR}")
    print("open the URL, read a session, select the failing text, type a note.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down")
        server.shutdown()


if __name__ == "__main__":
    main()
