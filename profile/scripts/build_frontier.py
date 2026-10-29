"""Build the Homework 9 Part E frontier: score against cost for every development run.

Offline, no model calls. Reads the saved optimize.runner results and writes
profile/results/frontier.csv and profile/results/frontier.svg.

The runs were priced with different tables: the HW8 final run and the Part B
runs billed every input token at the full price, because the cached input price
was added to optimize/config.json only in Part C. So every cost here is
recomputed from the run's saved token counts with the current price table
(cached input tokens at the cached price). The saved result files are unchanged.

    uv run python profile/scripts/build_frontier.py
"""

from __future__ import annotations

import csv
import json
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "optimize" / "results"
OUT_DIR = ROOT / "profile" / "results"
PRICES = json.loads((ROOT / "optimize" / "config.json").read_text())[
    "prices_per_million_tokens_usd"
]

# (candidate, result file, what changed), in the order they were run.
RUNS = [
    ("final", "development-final-gpt-4o-mini-20261023-141310.json", "HW8 final agent"),
    ("fewer-tokens", "development-fewer-tokens-gpt-4o-mini-20261026-094045.json", "B: compact JSON tool results (reverted)"),
    ("fewer-tokens-rerun", "development-fewer-tokens-rerun-gpt-4o-mini-20261026-101312.json", "B: same, rerun (reverted)"),
    ("fewer-tokens-a1", "development-fewer-tokens-a1-gpt-4o-mini-20261026-102420.json", "B: find_order without 2 fields (reverted)"),
    ("cache-before", "development-cache-before-gpt-4o-mini-20261026-104758.json", "C: HW8 final agent, rerun"),
    ("cache-after", "development-cache-after-gpt-4o-mini-20261026-112248.json", "C: Session context last (reverted)"),
]
# Two runs of the same, unchanged HW8 agent; their score gap is run-to-run spread.
SAME_AGENT = ("final", "cache-before")
COLUMNS = [
    "candidate",
    "model",
    "development_score",
    "write_pass_5",
    "cost_per_100_conversations_usd",
    "median_latency_seconds",
    "frontier_status",
]


def repriced_cost_per_100(result: dict) -> float:
    p = PRICES[result["model"]]
    cached = result["cached_input_tokens"]
    cost = (
        (result["input_tokens"] - cached) * p["input"]
        + cached * p.get("cached_input", p["input"])
        + result["output_tokens"] * p["output"]
    ) / 1_000_000
    return cost / result["evaluated_case_runs"] * 100


def dominated(row: dict, rows: list[dict]) -> bool:
    """Another row has an equal or higher score and an equal or lower cost, and is better on one."""
    return any(
        other is not row
        and other["score"] >= row["score"]
        and other["cost"] <= row["cost"]
        and (other["score"] > row["score"] or other["cost"] < row["cost"])
        for other in rows
    )


def load_rows() -> list[dict]:
    rows = []
    for candidate, filename, note in RUNS:
        result = json.loads((RESULTS / filename).read_text(encoding="utf-8"))
        assert result["candidate"] == candidate and result["split"] == "development", filename
        rows.append({
            "candidate": candidate,
            "note": note,
            "model": result["model"],
            "score": result["score"],
            "write_pass_5": result["write_pass_5"],
            "cost": round(repriced_cost_per_100(result), 6),
            "saved_cost": result["cost_per_100_conversations_usd"],
            "latency": result["median_latency_seconds"],
        })
    for row in rows:
        row["status"] = "dominated" if dominated(row, rows) else "frontier"
    return rows


def write_csv(rows: list[dict]) -> Path:
    path = OUT_DIR / "frontier.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(COLUMNS)
        for row in rows:
            writer.writerow([row["candidate"], row["model"], row["score"], row["write_pass_5"],
                             row["cost"], row["latency"], row["status"]])
    return path


# Chart, in the style of scripts/hw8_plot_frontier.py.
WIDTH, HEIGHT = 820, 520
LEFT, RIGHT, TOP, BOTTOM = 76, 40, 92, 64
SURFACE, INK, INK_2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8984", "#e6e5e1"
BAND = "#efe9de"
FRONTIER, OTHER = "#eb6834", "#2a78d6"


def write_svg(rows: list[dict]) -> Path:
    x_min, x_max = 0.055, 0.075
    y_min, y_max = 0.4, 1.0
    x_pos = lambda c: LEFT + (c - x_min) / (x_max - x_min) * (WIDTH - LEFT - RIGHT)  # noqa: E731
    y_pos = lambda s: TOP + (y_max - s) / (y_max - y_min) * (HEIGHT - TOP - BOTTOM)  # noqa: E731
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" width="{WIDTH * 2}" '
        f'height="{HEIGHT * 2}" font-family="system-ui, -apple-system, Segoe UI, sans-serif" role="img" aria-labelledby="t d">',
        '<title id="t">HW9 development frontier: score against cost</title>',
        '<desc id="d">' + escape("; ".join(
            f"{r['candidate']}: score {r['score']:.3f}, ${r['cost']:.4f} per 100 conversations, {r['status']}"
            for r in rows)) + "</desc>",
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="{SURFACE}"/>',
        f'<text x="{LEFT}" y="34" font-size="19" font-weight="600" fill="{INK}">'
        "Score against cost on the development cases (gpt-4o-mini, 21 runs each)</text>",
        f'<text x="{LEFT}" y="58" font-size="13" fill="{INK_2}">'
        "Higher and further left is better. All costs repriced with the same table (cached input at half price). "
        "Dashed line: the frontier.</text>",
    ]
    # Run-to-run spread of the unchanged HW8 agent, drawn under the grid.
    same = [r for r in rows if r["candidate"] in SAME_AGENT]
    low, high = min(r["score"] for r in same), max(r["score"] for r in same)
    out.append(f'<rect x="{LEFT}" y="{y_pos(high):.1f}" width="{WIDTH - LEFT - RIGHT}" '
               f'height="{y_pos(low) - y_pos(high):.1f}" fill="{BAND}"/>')
    # Caption in the empty top-left of the band, away from every point label.
    out.append(f'<text x="{LEFT + 10}" y="{y_pos(high) + 40:.1f}" font-size="12" fill="{INK_2}" text-anchor="start">'
               f'Shaded: the same HW8 agent, two runs, scored {low:.2f} to {high:.2f} (run-to-run spread)</text>')
    for score in (0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0):
        y = y_pos(score)
        out.append(f'<line x1="{LEFT}" x2="{WIDTH - RIGHT}" y1="{y:.1f}" y2="{y:.1f}" stroke="{GRID}"/>')
        out.append(f'<text x="{LEFT - 10}" y="{y + 4:.1f}" font-size="12" fill="{MUTED}" text-anchor="end">{score:.1f}</text>')
    for cost in (0.055, 0.06, 0.065, 0.07, 0.075):
        x = x_pos(cost)
        out.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{TOP}" y2="{HEIGHT - BOTTOM}" stroke="{GRID}"/>')
        out.append(f'<text x="{x:.1f}" y="{HEIGHT - BOTTOM + 20}" font-size="12" fill="{MUTED}" text-anchor="middle">${cost:.3f}</text>')
    out.append(f'<text x="{(LEFT + WIDTH - RIGHT) / 2}" y="{HEIGHT - 18}" font-size="13" fill="{INK_2}" '
               'text-anchor="middle">Agent model cost per 100 conversations (USD)</text>')
    out.append(f'<text transform="translate(20 {(TOP + HEIGHT - BOTTOM) / 2}) rotate(-90)" font-size="13" '
               f'fill="{INK_2}" text-anchor="middle">Development score (mean pass rate)</text>')
    frontier = sorted((r for r in rows if r["status"] == "frontier"), key=lambda r: r["cost"])
    points = " ".join(f"{x_pos(r['cost']):.1f},{y_pos(r['score']):.1f}" for r in frontier)
    out.append(f'<polyline points="{points}" fill="none" stroke="{MUTED}" stroke-width="2" stroke-dasharray="6 5"/>')
    for r in rows:
        x, y = x_pos(r["cost"]), y_pos(r["score"])
        on = r["status"] == "frontier"
        color = FRONTIER if on else OTHER
        out.append(f'<g><title>{escape(r["candidate"] + ": " + r["note"])}</title>'
                   f'<circle cx="{x:.1f}" cy="{y:.1f}" r="9" fill="{SURFACE}"/>'
                   f'<circle cx="{x:.1f}" cy="{y:.1f}" r="7" fill="{color if on else SURFACE}" stroke="{color}" stroke-width="2.5"/></g>')
        dx, anchor = (12, "start") if x < WIDTH - 340 else (-12, "end")
        out.append(f'<text x="{x + dx:.1f}" y="{y - 4:.1f}" font-size="13" fill="{INK}" text-anchor="{anchor}">'
                   f'<tspan font-weight="600">{escape(r["candidate"])}</tspan>'
                   + (" · HW8 agent" if r["candidate"] in SAME_AGENT else "") + "</text>")
        out.append(f'<text x="{x + dx:.1f}" y="{y + 12:.1f}" font-size="12" fill="{INK_2}" text-anchor="{anchor}">'
                   f'score {r["score"]:.2f} · ${r["cost"]:.4f} · {r["status"]}</text>')
    lx, ly = WIDTH - RIGHT - 220, 80
    for i, (label, color, filled) in enumerate((("Frontier", FRONTIER, True), ("Dominated", OTHER, False))):
        x = lx + i * 110
        out.append(f'<circle cx="{x}" cy="{ly}" r="6" fill="{color if filled else SURFACE}" stroke="{color}" stroke-width="2"/>')
        out.append(f'<text x="{x + 12}" y="{ly + 4}" font-size="12" fill="{INK_2}">{label}</text>')
    out.append("</svg>")
    path = OUT_DIR / "frontier.svg"
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return path


def main() -> None:
    rows = load_rows()
    print(f"{'candidate':20}{'score':>7}{'wp5':>7}{'saved $/100':>13}{'repriced $/100':>16}{'latency':>9}  status")
    for r in rows:
        print(f"{r['candidate']:20}{r['score']:>7.3f}{r['write_pass_5']:>7.3f}{r['saved_cost']:>13.4f}"
              f"{r['cost']:>16.4f}{r['latency']:>9.2f}  {r['status']}")
    print(f"Wrote {write_csv(rows).relative_to(ROOT)} and {write_svg(rows).relative_to(ROOT)}")


if __name__ == "__main__":
    main()
