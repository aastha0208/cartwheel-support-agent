"""Build a 2D projection of the reviewed sample for the review app's Map tab.

Purely additive and read-only against everything already reviewed: reads
analysis/state/samples.json, writes only analysis/state/graph.json (a new
file). Does not touch annotations.json, patterns.json, suggestions.json, or
any label file.

Reuses the same numeric feature vector as analysis/helpers/selection.py's
clustering (turn_count, tool_call_count, distinct_tools, has_retrieval,
tokens) -- the same axis batch 1's cluster-representative sampling already
used -- then projects to 2D with PCA and assigns a cluster id with k-means,
both via scikit-learn.

Scoped to the 108 reviewed traces (not the full 250-scenario corpus), since
that's what the review app already has loaded and lets this run without an
extra Langfuse fetch.

Usage:
    uv run python scripts/build_trace_graph.py
"""

from __future__ import annotations

import json
from pathlib import Path

from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / "analysis" / "state"
FEATURES = ("turn_count", "tool_call_count", "distinct_tools", "has_retrieval", "tokens")
N_CLUSTERS = 6


def _describe_cluster(avg: dict[str, float]) -> str:
    """One-line, rule-based description of a cluster from its own feature
    averages -- regenerated from the data every run, not hand-labeled, so it
    can't drift out of sync with what k-means actually grouped."""
    turns, calls, retrieval = avg["turn_count"], avg["tool_call_count"], avg["has_retrieval"]

    length = "short" if turns < 4 else ("long" if turns > 5.5 else "moderate-length")
    if calls < 2:
        tool_use = "minimal tool use"
    elif calls > 3.5:
        tool_use = "tool-heavy"
    else:
        tool_use = "moderate tool use"
    topic = "policy/retrieval lookups" if retrieval >= 0.5 else "no policy lookups"

    return f"{length.capitalize()} conversations, {tool_use}, {topic}"


def main() -> None:
    samples = json.loads((STATE_DIR / "samples.json").read_text(encoding="utf-8"))
    if not samples:
        raise SystemExit("samples.json is empty -- nothing to project")

    vectors = [[float(s.get("features", {}).get(f, 0)) for f in FEATURES] for s in samples]

    scaled = StandardScaler().fit_transform(vectors)
    coords = PCA(n_components=2, random_state=7).fit_transform(scaled)
    k = min(N_CLUSTERS, len(samples))
    labels = KMeans(n_clusters=k, random_state=7, n_init=10).fit_predict(scaled)

    nodes = []
    for s, (x, y), cluster in zip(samples, coords, labels):
        nodes.append({
            "trace_id": s["trace_id"],
            "x": float(x),
            "y": float(y),
            "cluster": int(cluster),
            "scenario_id": s.get("meta", {}).get("scenario_id"),
        })

    clusters = []
    for c in range(k):
        members = [v for v, lab in zip(vectors, labels) if lab == c]
        avg = {f: sum(v[i] for v in members) / len(members) for i, f in enumerate(FEATURES)}
        clusters.append({
            "id": c,
            "n": len(members),
            "avg_features": {f: round(avg[f], 2) for f in FEATURES},
            "description": _describe_cluster(avg),
        })

    graph = {"nodes": nodes, "clusters": clusters}
    (STATE_DIR / "graph.json").write_text(json.dumps(graph, indent=2), encoding="utf-8")
    print(f"wrote {len(nodes)} nodes across {k} clusters to {STATE_DIR / 'graph.json'}")
    for c in clusters:
        print(f"  cluster {c['id']} (n={c['n']}): {c['description']}")


if __name__ == "__main__":
    main()
