"""Voting and consensus detection.

V1.5 consensus is token-Jaccard clustering with parallel similarity calculation,
reputation-weighted. Each response is tokenised, pairs above `cluster_threshold`
are grouped, and the largest cluster (by summed reputation weight) wins.
Confidence is the cluster's weighted share of the total; disputed_flag fires
when confidence is below `dispute_confidence` and any responses fall outside
the cluster.

Enhancements:
- Parallel pairwise similarity computation for large model counts
- Negation penalty to avoid false consensus on contradictions
- Cohesion pruning to prevent bridge responses from merging unrelated clusters
- Canonical label extraction for structured response types (yes/no, A/B/C/D, numeric)
"""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional


_TOKEN_RE = re.compile(r"\w+")

_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "because",
    "but",
    "by",
    "can",
    "could",
    "does",
    "for",
    "from",
    "have",
    "how",
    "i",
    "if",
    "in",
    "is",
    "it",
    "its",
    "may",
    "might",
    "of",
    "on",
    "or",
    "our",
    "should",
    "so",
    "that",
    "the",
    "their",
    "then",
    "there",
    "these",
    "this",
    "to",
    "we",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
    "would",
    "you",
    "your",
    "use",
    "using",
}

_NEGATIONS = {"no", "not", "never", "none", "cannot", "can't", "won't"}

_YES = {"yes", "y", "true", "correct"}


def _tokens(text: str) -> set[str]:
    raw = [t.lower() for t in _TOKEN_RE.findall(text or "")]
    has_neg = any(t in _NEGATIONS for t in raw)
    tokens = {t for t in raw if t and t not in _STOPWORDS}
    if has_neg:
        tokens.add("__neg__")
    return tokens


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    a0 = set(a)
    b0 = set(b)
    neg_a = "__neg__" in a0
    neg_b = "__neg__" in b0
    a0.discard("__neg__")
    b0.discard("__neg__")

    if not a0 and not b0:
        base = 1.0
    else:
        union0 = a0 | b0
        base = (len(a0 & b0) / len(union0)) if union0 else 0.0

    if neg_a ^ neg_b:
        return base * 0.1
    return base


def _canonical_label(text: str) -> Optional[str]:
    t = (text or "").strip()
    if not t:
        return None
    first = t.splitlines()[0].strip().lower()

    m = re.match(r"^(yes|no|true|false)\b", first)
    if m:
        val = m.group(1)
        return "yes" if val in _YES else "no"

    m = re.match(r"^(a|b|c|d)\b", first)
    if m:
        return f"choice:{m.group(1)}"

    if len(first) <= 48:
        m = re.search(r"\b-?\d+(?:\.\d+)?\b", first)
        if m:
            return f"num:{m.group(0)}"

    m = re.search(r"\b(answer|result|final)\b[^\d\n]{0,20}(-?\d+(?:\.\d+)?)\b", first)
    if m:
        return f"num:{m.group(2)}"

    return None


class VotingEngine:
    def __init__(self, cluster_threshold: float = 0.25, dispute_confidence: float = 0.66, max_workers: int = 8, parallel_threshold: int = 20):
        self.cluster_threshold = cluster_threshold
        self.dispute_confidence = dispute_confidence
        self.max_workers = max_workers  # Max threads for parallel similarity calculation
        self.parallel_threshold = parallel_threshold  # Use parallel only when models >= this

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

        def cluster_weight(cluster: List[str]) -> float:
            return sum(weight(m) for m in cluster)

        canon: Dict[str, str] = {}
        for m, t in valid_items:
            lab = _canonical_label(t)
            if lab:
                canon[m] = lab
        if canon:
            label_to_models: Dict[str, List[str]] = {}
            for m, lab in canon.items():
                label_to_models.setdefault(lab, []).append(m)
            total_weight = sum(weight(m) for m, _ in valid_items)
            best_label = max(label_to_models.items(), key=lambda kv: cluster_weight(kv[1]))[0]
            best_models = label_to_models[best_label]
            label_conf = cluster_weight(best_models) / total_weight if total_weight else 0.0
            if len(label_to_models) >= 2 and len(canon) >= 2:
                consensus_cluster = best_models
                anchor = max(consensus_cluster, key=lambda m: (weight(m), len(responses[m])))
                out_cluster = [m for m, _ in valid_items if m not in consensus_cluster]
                disputed_flag = label_conf < self.dispute_confidence

                if disputed_flag:
                    consensus_text = "Models disagreed."
                    disputed = "\n\n---\n\n".join(f"{m}: {responses[m]}" for m, _ in valid_items)
                else:
                    consensus_text = responses[anchor]
                    disputed = "\n\n---\n\n".join(f"{m}: {responses[m]}" for m in out_cluster) if out_cluster else ""

                agents_out_canon: List[Dict[str, Any]] = []
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
                    agents_out_canon.append({"model": m, "response": t, "vote": vote})
                agents_out_canon.extend(error_agents)
                return {
                    "consensus": consensus_text,
                    "confidence": round(label_conf, 3),
                    "disputed": disputed,
                    "disputed_flag": disputed_flag,
                    "agents": agents_out_canon,
                }

        token_sets = {m: _tokens(t) for m, t in valid_items}

        sims: Dict[str, Dict[str, float]] = {m: {} for m, _ in valid_items}
        models = [m for m, _ in valid_items]
        
        # Use parallel processing for large model counts, sequential for small sets
        if len(models) >= self.parallel_threshold:
            # Generate all pairs to compute
            pairs = []
            for i, a in enumerate(models):
                for b in models[i + 1 :]:
                    pairs.append((a, b, token_sets[a], token_sets[b]))
            
            # Compute similarities in parallel
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_pair = {
                    executor.submit(_jaccard, ts_a, ts_b): (a, b) 
                    for a, b, ts_a, ts_b in pairs
                }
                for future in as_completed(future_to_pair):
                    a, b = future_to_pair[future]
                    s = future.result()
                    sims[a][b] = s
                    sims[b][a] = s
        else:
            # Sequential for small model counts (avoids thread overhead)
            for i, a in enumerate(models):
                for b in models[i + 1 :]:
                    s = _jaccard(token_sets[a], token_sets[b])
                    sims[a][b] = s
                    sims[b][a] = s

        def sim(a: str, b: str) -> float:
            if a == b:
                return 1.0
            return sims.get(a, {}).get(b, 0.0)

        def cohesion(ms: List[str]) -> float:
            if len(ms) < 2:
                return 1.0
            total = 0.0
            pairs = 0
            for i, a in enumerate(ms):
                for b in ms[i + 1 :]:
                    total += sim(a, b)
                    pairs += 1
            return total / pairs if pairs else 0.0

        unassigned = set(models)
        clusters: List[List[str]] = []
        while unassigned:
            def anchor_key(m: str) -> tuple[float, float, int]:
                others = [o for o in unassigned if o != m]
                if not others:
                    return (weight(m), 0.0, len(responses[m]))
                wsum = sum(weight(o) for o in others)
                avg = sum(sim(m, o) * weight(o) for o in others) / wsum if wsum else 0.0
                return (weight(m), avg, len(responses[m]))

            anchor = max(unassigned, key=anchor_key)
            cluster = [anchor] + [m for m in unassigned if m != anchor and sim(anchor, m) >= self.cluster_threshold]
            if len(cluster) >= 3:
                pruned = [anchor]
                for m in cluster:
                    if m == anchor:
                        continue
                    if any(sim(m, o) >= self.cluster_threshold for o in cluster if o not in (m, anchor)):
                        pruned.append(m)
                if len(pruned) >= 2 and cohesion(pruned) >= self.cluster_threshold:
                    cluster = pruned
                elif cohesion(cluster) < self.cluster_threshold:
                    cluster = [anchor]
            clusters.append(cluster)
            for m in cluster:
                unassigned.discard(m)

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

        agents_out_text: List[Dict[str, Any]] = []
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
            agents_out_text.append({"model": m, "response": t, "vote": vote})
        agents_out_text.extend(error_agents)

        return {
            "consensus": consensus_text,
            "confidence": round(confidence, 3),
            "disputed": disputed,
            "disputed_flag": disputed_flag,
            "agents": agents_out_text,
        }
