"""Voting and consensus detection.

V1 consensus is token-Jaccard clustering, reputation-weighted. Each response
is tokenised, pairs above `cluster_threshold` are grouped, and the largest
cluster (by summed reputation weight) wins. Confidence is the cluster's
weighted share of the total; disputed_flag fires when confidence is below
`dispute_confidence` and any responses fall outside the cluster.

Known limitation — lexical, not semantic. "X is true" and "X is false" share
most tokens but contradict; Jaccard can't tell them apart. Replace this
module with embedding-based or peer-review aggregation when semantic
accuracy matters (see dev order step 2 follow-up)."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


_TOKEN_RE = re.compile(r"\w+")


def _tokens(text: str) -> set:
    return {t.lower() for t in _TOKEN_RE.findall(text or "")}


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    return len(a & b) / len(union) if union else 0.0


class VotingEngine:
    def __init__(self, cluster_threshold: float = 0.25, dispute_confidence: float = 0.66):
        self.cluster_threshold = cluster_threshold
        self.dispute_confidence = dispute_confidence

    def aggregate(
        self,
        responses: Dict[str, str],
        domain: str,
        reputation_weights: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        if not responses:
            return {
                "consensus": "No responses received",
                "confidence": 0.0,
                "disputed": "",
                "disputed_flag": False,
                "agents": [],
            }

        reputation_weights = reputation_weights or {}

        valid_items: List[tuple[str, str]] = []
        error_agents: List[Dict[str, Any]] = []
        for m, t in responses.items():
            if t and not t.startswith("Error"):
                valid_items.append((m, t))
            else:
                error_agents.append({"model": m, "response": t, "vote": "Error"})

        if not valid_items:
            return {
                "consensus": "All models failed",
                "confidence": 0.0,
                "disputed": "",
                "disputed_flag": False,
                "agents": error_agents,
            }

        def weight(m: str) -> float:
            return max(reputation_weights.get(m, 1.0), 0.1)

        if len(valid_items) == 1:
            m, t = valid_items[0]
            return {
                "consensus": t,
                "confidence": 0.5,
                "disputed": "",
                "disputed_flag": False,
                "agents": [{"model": m, "response": t, "vote": "sole"}] + error_agents,
            }

        token_sets = {m: _tokens(t) for m, t in valid_items}

        # Greedy single-link clustering at cluster_threshold.
        clusters: List[List[str]] = []
        for m, _ in valid_items:
            placed = False
            for cluster in clusters:
                if any(_jaccard(token_sets[m], token_sets[c]) >= self.cluster_threshold for c in cluster):
                    cluster.append(m)
                    placed = True
                    break
            if not placed:
                clusters.append([m])

        def cluster_weight(cluster: List[str]) -> float:
            return sum(weight(m) for m in cluster)

        total_weight = sum(weight(m) for m, _ in valid_items)
        consensus_cluster = max(clusters, key=cluster_weight)
        confidence = cluster_weight(consensus_cluster) / total_weight if total_weight else 0.0

        # Anchor = highest-weight, longest-response member of the consensus cluster.
        anchor = max(consensus_cluster, key=lambda m: (weight(m), len(responses[m])))
        out_cluster = [m for m, _ in valid_items if m not in consensus_cluster]

        disputed_flag = bool(out_cluster) and confidence < self.dispute_confidence
        if disputed_flag:
            consensus_text = "Models disagreed."
            disputed = "\n\n---\n\n".join(f"{m}: {responses[m]}" for m, _ in valid_items)
        else:
            consensus_text = responses[anchor]
            disputed = "\n\n---\n\n".join(f"{m}: {responses[m]}" for m in out_cluster) if out_cluster else ""

        agents: List[Dict[str, Any]] = []
        for m, t in valid_items:
            if disputed_flag:
                vote = "minority" if m in consensus_cluster else "dissent"
            else:
                if m == anchor:
                    vote = "anchor"
                elif m in consensus_cluster:
                    vote = "consensus"
                else:
                    vote = "dissent"
            agents.append({"model": m, "response": t, "vote": vote})
        agents.extend(error_agents)

        return {
            "consensus": consensus_text,
            "confidence": round(confidence, 3),
            "disputed": disputed,
            "disputed_flag": disputed_flag,
            "agents": agents,
        }
