"""Plot the Homework 8 test-set frontier (score against cost) as an SVG.

Offline, no model calls. Reads optimize/results/frontier.csv and writes
optimize/results/frontier.svg. Cost uses a log scale because it spans about
two orders of magnitude.

    uv run python scripts/hw8_plot_frontier.py
"""

from __future__ import annotations

import csv
import math
from html import escape

from optimize.workflow import RESULTS_DIR

WIDTH, HEIGHT = 820, 500
DISPLAY_SCALE = 2  # display size only; the drawing scales through the viewBox
LEFT, RIGHT, TOP, BOTTOM = 76, 40, 92, 64
X_MIN, X_MAX = 0.03, 10.0  # USD per 100 conversations, log scale
SURFACE, INK, INK_2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8984", "#e6e5e1"
STARTING, FINAL = "#2a78d6", "#eb6834"  # categorical slots 1 and 2 (validated)

LABELS = {
    1: ("starting agent · gpt-5.5", 0, -32, "end"),
    2: ("starting agent · claude-opus-4-6 (dominated)", -12, 4, "end"),
    3: ("starting agent · gpt-4o-mini", 12, 18, "start"),
    4: ("final agent · gpt-4o-mini", -4, -32, "start"),
}


def x_pos(cost: float) -> float:
    span = math.log10(X_MAX) - math.log10(X_MIN)
    return LEFT + (math.log10(cost) - math.log10(X_MIN)) / span * (WIDTH - LEFT - RIGHT)


def y_pos(score: float) -> float:
    return TOP + (1 - score) * (HEIGHT - TOP - BOTTOM)


def main() -> None:
    with (RESULTS_DIR / "frontier.csv").open(newline="") as handle:
        rows = [
            {
                "n": int(row["configuration"]),
                "model": row["model"],
                "final": row["name"].startswith("final"),
                "score": float(row["score"]),
                "cost": float(row["cost_per_100_conversations_usd"]),
                "dominated": row["dominated"] == "True",
            }
            for row in csv.DictReader(handle)
        ]
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" '
        f'width="{WIDTH * DISPLAY_SCALE}" height="{HEIGHT * DISPLAY_SCALE}" font-family="system-ui, -apple-system, Segoe UI, sans-serif" '
        'role="img" aria-labelledby="t d">',
        '<title id="t">HW8 test-set frontier: score against cost</title>',
        '<desc id="d">'
        + escape("; ".join(
            f"configuration {r['n']} {'final' if r['final'] else 'starting'} agent on {r['model']}: "
            f"score {r['score']:.3f}, ${r['cost']:.3f} per 100 conversations"
            + (", dominated" if r["dominated"] else ", on the frontier")
            for r in rows
        ))
        + "</desc>",
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="{SURFACE}"/>',
        f'<text x="{LEFT}" y="34" font-size="19" font-weight="600" fill="{INK}">'
        "Score against cost on the held-out test set (6 cases)</text>",
        f'<text x="{LEFT}" y="58" font-size="13" fill="{INK_2}">'
        "Higher and further left is better. Cost is per 100 conversations (log scale). "
        "Dashed line: the frontier.</text>",
    ]
    # Recessive grid and axes.
    for score in (0, 0.25, 0.5, 0.75, 1.0):
        y = y_pos(score)
        out.append(f'<line x1="{LEFT}" x2="{WIDTH - RIGHT}" y1="{y:.1f}" y2="{y:.1f}" stroke="{GRID}" stroke-width="1"/>')
        out.append(f'<text x="{LEFT - 10}" y="{y + 4:.1f}" font-size="12" fill="{MUTED}" text-anchor="end">{score:.2f}</text>')
    for cost, label in ((0.05, "$0.05"), (0.1, "$0.10"), (0.5, "$0.50"), (1, "$1"), (5, "$5")):
        x = x_pos(cost)
        out.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{TOP}" y2="{HEIGHT - BOTTOM}" stroke="{GRID}" stroke-width="1"/>')
        out.append(f'<text x="{x:.1f}" y="{HEIGHT - BOTTOM + 20}" font-size="12" fill="{MUTED}" text-anchor="middle">{label}</text>')
    out.append(f'<text x="{(LEFT + WIDTH - RIGHT) / 2}" y="{HEIGHT - 18}" font-size="13" fill="{INK_2}" text-anchor="middle">'
               "Agent model cost per 100 conversations (USD, log scale)</text>")
    out.append(f'<text transform="translate(20 {(TOP + HEIGHT - BOTTOM) / 2}) rotate(-90)" font-size="13" '
               f'fill="{INK_2}" text-anchor="middle">Test score (mean pass rate)</text>')
    # Frontier: non-dominated configurations, in cost order.
    frontier = sorted((r for r in rows if not r["dominated"]), key=lambda r: r["cost"])
    points = " ".join(f"{x_pos(r['cost']):.1f},{y_pos(r['score']):.1f}" for r in frontier)
    out.append(f'<polyline points="{points}" fill="none" stroke="{MUTED}" stroke-width="2" stroke-dasharray="6 5"/>')
    # Effect of the agent changes: starting -> final on the same model.
    by_n = {r["n"]: r for r in rows}
    if 3 in by_n and 4 in by_n:
        x3, y3 = x_pos(by_n[3]["cost"]), y_pos(by_n[3]["score"])
        x4, y4 = x_pos(by_n[4]["cost"]), y_pos(by_n[4]["score"])
        out.append(f'<text x="{(x3 + x4) / 2 + 14:.1f}" y="{(y3 + y4) / 2 + 4:.1f}" font-size="12" fill="{INK_2}" '
                   f'text-anchor="start">agent changes, same model: +{by_n[4]["score"] - by_n[3]["score"]:.2f} score</text>')
    # Marks: filled = frontier, hollow = dominated; 2px surface ring on every mark.
    for r in rows:
        x, y = x_pos(r["cost"]), y_pos(r["score"])
        color = FINAL if r["final"] else STARTING
        fill = SURFACE if r["dominated"] else color
        tip = escape(f"{r['n']}: {'final' if r['final'] else 'starting'} agent on {r['model']} — "
                     f"score {r['score']:.3f}, ${r['cost']:.3f} per 100 conversations")
        out.append(f'<g><title>{tip}</title>'
                   f'<circle cx="{x:.1f}" cy="{y:.1f}" r="9" fill="{SURFACE}"/>'
                   f'<circle cx="{x:.1f}" cy="{y:.1f}" r="7" fill="{fill}" stroke="{color}" stroke-width="2.5"/></g>')
        text, dx, dy, anchor = LABELS[r["n"]]
        out.append(f'<text x="{x + dx:.1f}" y="{y + dy:.1f}" font-size="13" fill="{INK}" text-anchor="{anchor}">'
                   f'<tspan font-weight="600">{r["n"]}</tspan> {escape(text)}</text>')
        out.append(f'<text x="{x + dx:.1f}" y="{y + dy + 16:.1f}" font-size="12" fill="{INK_2}" text-anchor="{anchor}">'
                   f'score {r["score"]:.2f} · ${r["cost"]:.3f}</text>')
    # Legend (identity is never colour alone: labels sit beside every mark too).
    lx, ly = WIDTH - RIGHT - 300, 80
    for i, (label, color, filled) in enumerate((
        ("Starting agent", STARTING, True), ("Final agent", FINAL, True), ("Dominated", MUTED, False)
    )):
        x = lx + i * 108
        out.append(f'<circle cx="{x}" cy="{ly}" r="6" fill="{color if filled else SURFACE}" stroke="{color}" stroke-width="2"/>')
        out.append(f'<text x="{x + 12}" y="{ly + 4}" font-size="12" fill="{INK_2}">{label}</text>')
    out.append("</svg>")
    path = RESULTS_DIR / "frontier.svg"
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"Saved {path}")


if __name__ == "__main__":
    main()
