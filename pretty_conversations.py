"""Render hw1-conversations.jsonl as a readable Markdown digest.

The .jsonl file stays the canonical, one-record-per-line deliverable.
This just produces a human-readable view next to it.

    uv run python pretty_conversations.py            # -> hw1-conversations.pretty.md
    uv run python pretty_conversations.py --text      # -> hw1-conversations.pretty.txt
"""
from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

SRC = Path("hw1-conversations.jsonl")
WRAP = 96


def wrap(text: str, indent: str = "") -> str:
    out = []
    for para in str(text).split("\n"):
        if not para.strip():
            out.append("")
            continue
        out.append(textwrap.fill(
            para, width=WRAP, initial_indent=indent, subsequent_indent=indent,
            break_long_words=False, break_on_hyphens=False,
        ))
    return "\n".join(out)


def render_md(records: list[dict]) -> str:
    lines: list[str] = ["# hw1-conversations.jsonl — readable view", ""]
    lines.append(f"{len(records)} records. Generated from `hw1-conversations.jsonl`; edit the .jsonl, not this file.")
    lines.append("")

    # summary table
    lines += ["| # | phase | role (user) | requirement | met | problem_source |",
              "|---|---|---|---|---|---|"]
    for i, r in enumerate(records, 1):
        met = "✅" if r.get("met_requirement") else "❌"
        lines.append(
            f"| {i} | {r.get('phase','—')} | {r.get('role','?')} ({r.get('user_id','?')}) "
            f"| {r.get('requirement') or '—'} | {met} | {r.get('problem_source') or '—'} |"
        )
    lines.append("")

    for i, r in enumerate(records, 1):
        met = "met" if r.get("met_requirement") else "NOT met"
        head = f"## {i}. {r.get('role','?')} (user {r.get('user_id','?')})"
        if r.get("store_id") is not None:
            head += f", store {r['store_id']}"
        head += f" — {r.get('requirement') or 'no single requirement'} — {met}"
        lines += [head, ""]
        if r.get("phase"):
            lines += [f"*phase: {r['phase']}*", ""]

        lines += ["**Request**", "", "> " + str(r.get("request", "")).replace("\n", "\n> "), ""]

        calls = r.get("tool_calls") or []
        if calls:
            lines += ["**Tool calls**", ""]
            for n, c in enumerate(calls, 1):
                args = json.dumps(c.get("arguments", {}), ensure_ascii=False)
                lines.append(f"{n}. `{c.get('name','?')}({args})`")
                res = c.get("result", {})
                lines += ["", "   ```json", textwrap.indent(json.dumps(res, indent=2, ensure_ascii=False), "   "), "   ```", ""]
        else:
            lines += ["**Tool calls** — none", ""]

        lines += ["**Response**", "", "> " + str(r.get("response", "")).replace("\n", "\n> "), ""]
        lines += ["**Expected**", "", wrap(r.get("expected", "")), ""]
        lines += [f"**problem_source:** {r.get('problem_source') or '—'}", "", "---", ""]

    return "\n".join(lines)


def render_txt(records: list[dict]) -> str:
    blocks: list[str] = []
    for i, r in enumerate(records, 1):
        met = "MET" if r.get("met_requirement") else "NOT MET"
        b = [f"{'='*WRAP}",
             f"RECORD {i}   {r.get('role','?')} (user {r.get('user_id','?')})   "
             f"{r.get('requirement') or '-'}   {met}"]
        if r.get("phase"):
            b.append(f"phase: {r['phase']}")
        b += ["", "REQUEST", wrap(r.get("request", ""), "  "), "", "TOOL CALLS"]
        calls = r.get("tool_calls") or []
        if not calls:
            b.append("  (none)")
        for n, c in enumerate(calls, 1):
            b.append(f"  {n}. {c.get('name','?')}  " + json.dumps(c.get("arguments", {}), ensure_ascii=False))
            b.append(textwrap.indent(json.dumps(c.get("result", {}), indent=2, ensure_ascii=False), "     "))
        b += ["", "RESPONSE", wrap(r.get("response", ""), "  "),
              "", "EXPECTED", wrap(r.get("expected", ""), "  "),
              "", f"problem_source: {r.get('problem_source') or '-'}", ""]
        blocks.append("\n".join(b))
    return "\n".join(blocks)


def main() -> None:
    records = [json.loads(ln) for ln in SRC.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if "--text" in sys.argv:
        out = Path("hw1-conversations.pretty.txt")
        out.write_text(render_txt(records), encoding="utf-8")
    else:
        out = Path("hw1-conversations.pretty.md")
        out.write_text(render_md(records), encoding="utf-8")
    print(f"wrote {out}  ({len(records)} records)")


if __name__ == "__main__":
    main()
