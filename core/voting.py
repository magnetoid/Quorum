"""Voting and consensus detection.

The voting engine uses a layered strategy:

1. Canonical labels for structured answers: yes/no, choices, numeric answers.
2. Optional semantic embeddings when `sentence-transformers` is installed.
3. Token-Jaccard fallback when semantic voting is disabled or unavailable.

Semantic voting is intentionally optional. Install with:

    pip install "quorum[semantic]"

Environment controls:

    QUORUM_SEMANTIC_VOTING=auto|on|off   default: auto
    QUORUM_SEMANTIC_MODEL=all-MiniLM-L6-v2
    QUORUM_SEMANTIC_WEIGHT=0.7
"""
from __future__ import annotations

import logging
import math
import os
import re
import httpx
from functools import lru_cache
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"\w+")

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "because", "but", "by",
    "can", "could", "does", "for", "from", "have", "how", "i", "if", "in",
    "is", "it", "its", "may", "might", "of", "on", "or", "our", "should",
    "so", "that", "the", "their", "then", "there", "these", "this", "to",
    "we", "what", "when", "where", "which", "who", "why", "with", "would",
    "you", "your", "use", "using",
}

_NEGATIONS = {"no", "not", "never", "none", "cannot", "can't", "won't"}
_YES = {"yes", "y", "true", "correct"}


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        logger.warning("Invalid %s=%r; using default %.2f", name, raw, default)
        return default


def _tokens(text: str) -> set[str]:
    raw = [t.lower() for t in _TOKEN_RE.findall(text or "")]
    has_neg = any(t in _NEGATIONS for t in raw)
    tokens = {t for t in raw if t and t not in _STOPWORDS}
    if has_neg:
        tokens.add("__neg__")
    return tokens


def _jaccard(a: set[str], b: set[str]) -> float:
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


@lru_cache(maxsize=1)
def _semantic_model():
    model_name = os.getenv("QUORUM_SEMANTIC_MODEL", "all-MiniLM-L6-v2")
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
    except Exception as e:
        logger.info("Semantic voting unavailable: sentence-transformers import failed: %s", e)
        return None
    try:
        return SentenceTransformer(model_name)
    except Exception as e:
        logger.warning("Semantic voting unavailable: failed to load %s: %s", model_name, e)
        return None


def _normalized_entropy(weights: Sequence[float]) -> float:
    """Shannon entropy of a cluster-weight distribution, normalized to [0, 1].

    0.0 means all mass sits in one cluster (full agreement); 1.0 means mass is
    spread evenly across the maximum number of clusters (maximum disagreement).

    This turns the cluster distribution into a dispersion / uncertainty signal.
    Unlike the single dominant-cluster fraction (`confidence`), entropy
    distinguishes "one clear majority plus a couple of outliers" from "evenly
    split many ways" — the cheap, sample-free analogue of the semantic-entropy
    hallucination signal (Farquhar et al., Nature 2024), computed over clusters
    Quorum has already formed.
    """
    positive = [float(w) for w in weights if w > 0]
    n = len(positive)
    if n <= 1:
        return 0.0
    total = sum(positive)
    if total <= 0:
        return 0.0
    h = 0.0
    for w in positive:
        p = w / total
        h -= p * math.log(p)
    return max(0.0, min(1.0, h / math.log(n)))


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(float(x) * float(y) for x, y in zip(a, b))


def _norm(a: Sequence[float]) -> float:
    return math.sqrt(sum(float(x) * float(x) for x in a))


def get_cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    denom = _norm(a) * _norm(b)
    if denom <= 0:
        return 0.0
    # Normalize from [-1, 1] to [0, 1] to match Jaccard scale.
    return max(0.0, min(1.0, (_dot(a, b) / denom + 1.0) / 2.0))


def _remote_embeddings(texts: List[str]) -> Optional[List[List[float]]]:
    """Fallback to OpenAI embeddings if local model is unavailable."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        with httpx.Client() as client:
            response = client.post(
                "https://api.openai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "input": texts,
                    "model": os.getenv("QUORUM_REMOTE_EMBEDDING_MODEL", "text-embedding-3-small"),
                },
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()
            return [v["embedding"] for v in data["data"]]
    except Exception as e:
        logger.warning("Remote embedding fallback failed: %s", e)
        return None


def get_semantic_embeddings(texts: List[str]) -> Optional[List[List[float]]]:
    mode = os.getenv("QUORUM_SEMANTIC_VOTING", "auto").lower().strip()
    if mode in {"0", "false", "off", "disabled"}:
        return None
    
    # Try local first
    model = _semantic_model()
    if model is not None:
        try:
            vectors = model.encode(texts, normalize_embeddings=True)
            return [list(map(float, v)) for v in vectors]
        except Exception as e:
            logger.warning("Local semantic embedding failed, trying remote: %s", e)

    # Fallback to remote
    return _remote_embeddings(texts)


def _build_similarity_matrix(valid_items: List[tuple[str, str]]) -> tuple[Dict[str, Dict[str, float]], str]:
    models = [m for m, _ in valid_items]
    texts = [t for _, t in valid_items]
    token_sets = {m: _tokens(t) for m, t in valid_items}
    sims: Dict[str, Dict[str, float]] = {m: {} for m in models}

    embeddings = get_semantic_embeddings(texts)
    semantic_weight = max(0.0, min(1.0, _env_float("QUORUM_SEMANTIC_WEIGHT", 0.7)))
    method = "lexical"
    if embeddings is not None and len(embeddings) == len(models):
        method = "hybrid-semantic"

    for i, a in enumerate(models):
        for j, b in enumerate(models[i + 1 :], start=i + 1):
            lexical = _jaccard(token_sets[a], token_sets[b])
            if method == "hybrid-semantic":
                assert embeddings is not None
                semantic = get_cosine_similarity(embeddings[i], embeddings[j])
                score = semantic_weight * semantic + (1.0 - semantic_weight) * lexical
                # Preserve the existing negation safety: if one answer is negated
                # and the other is not, do not let embeddings alone create a false
                # consensus.
                if ("__neg__" in token_sets[a]) ^ ("__neg__" in token_sets[b]):
                    score = min(score, lexical)
            else:
                score = lexical
            sims[a][b] = score
            sims[b][a] = score
    return sims, method


class VotingEngine:
    def __init__(
        self,
        cluster_threshold: float = 0.25,
        dispute_confidence: float = 0.66,
        max_workers: int = 8,
        parallel_threshold: int = 20,
    ):
        self.cluster_threshold = cluster_threshold
        self.dispute_confidence = dispute_confidence
        self.max_workers = max_workers
        self.parallel_threshold = parallel_threshold

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
                "entropy": 0.0,
                "disputed": "",
                "disputed_flag": False,
                "agents": [],
                "similarity_method": "none",
            }

        reputation_weights = reputation_weights or {}
        
        # Domain-aware thresholds
        # Stricter for code/logic, more relaxed for creative/default.
        cluster_threshold = self.cluster_threshold
        dispute_confidence = self.dispute_confidence
        if domain == "code":
            cluster_threshold = 0.4  # Need higher lexical/semantic overlap
            dispute_confidence = 0.75 # Require more agreement to avoid dispute
        elif domain in ("creative", "prose"):
            cluster_threshold = 0.15 # Allow more variation
            dispute_confidence = 0.5  # Lower bar for consensus

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
                "entropy": 0.0,
                "disputed": "",
                "disputed_flag": False,
                "agents": error_agents,
                "similarity_method": "none",
            }

        def weight(m: str) -> float:
            return max(reputation_weights.get(m, 1.0), 0.1)

        def cluster_weight(cluster: List[str]) -> float:
            return sum(weight(m) for m in cluster)

        if len(valid_items) == 1:
            m, t = valid_items[0]
            return {
                "consensus": t,
                "confidence": 0.5,
                "entropy": 0.0,
                "disputed": "",
                "disputed_flag": False,
                "agents": [{"model": m, "response": t, "vote": "sole"}] + error_agents,
                "similarity_method": "sole",
            }

        canon: Dict[str, str] = {}
        for m, t in valid_items:
            lab = _canonical_label(t)
            if lab:
                canon[m] = lab
        if canon:
            label_to_models: Dict[str, List[str]] = {}
            for m, lab in canon.items():
                label_to_models.setdefault(lab, []).append(m)
            if len(label_to_models) >= 2 and len(canon) >= 2:
                total_weight = sum(weight(m) for m, _ in valid_items)
                best_label = max(label_to_models.items(), key=lambda kv: cluster_weight(kv[1]))[0]
                consensus_cluster = label_to_models[best_label]
                label_conf = cluster_weight(consensus_cluster) / total_weight if total_weight else 0.0
                anchor = max(consensus_cluster, key=lambda m: (weight(m), len(responses[m])))
                out_cluster = [m for m, _ in valid_items if m not in consensus_cluster]
                disputed_flag = bool(out_cluster) and label_conf < dispute_confidence

                if disputed_flag:
                    consensus_text = "Models disagreed."
                    disputed = "\n\n---\n\n".join(f"{m}: {responses[m]}" for m, _ in valid_items)
                else:
                    consensus_text = responses[anchor]
                    disputed = "\n\n---\n\n".join(f"{m}: {responses[m]}" for m in out_cluster) if out_cluster else ""

                agents_out: List[Dict[str, Any]] = []
                for m, t in valid_items:
                    if disputed_flag:
                        vote = "minority" if m in consensus_cluster else "dissent"
                    elif m == anchor:
                        vote = "anchor"
                    elif m in consensus_cluster:
                        vote = "consensus"
                    else:
                        vote = "dissent"
                    agents_out.append({"model": m, "response": t, "vote": vote})
                agents_out.extend(error_agents)
                label_entropy = _normalized_entropy(
                    [cluster_weight(ms) for ms in label_to_models.values()]
                )
                return {
                    "consensus": consensus_text,
                    "confidence": round(label_conf, 3),
                    "entropy": round(label_entropy, 3),
                    "disputed": disputed,
                    "disputed_flag": disputed_flag,
                    "agents": agents_out,
                    "similarity_method": "canonical-label",
                }

        sims, method = _build_similarity_matrix(valid_items)
        models = [m for m, _ in valid_items]

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
            cluster = [anchor] + [m for m in unassigned if m != anchor and sim(anchor, m) >= cluster_threshold]
            if len(cluster) >= 3:
                pruned = [anchor]
                for m in cluster:
                    if m == anchor:
                        continue
                    if any(sim(m, o) >= cluster_threshold for o in cluster if o not in (m, anchor)):
                        pruned.append(m)
                if len(pruned) >= 2 and cohesion(pruned) >= cluster_threshold:
                    cluster = pruned
                elif cohesion(cluster) < cluster_threshold:
                    cluster = [anchor]
            clusters.append(cluster)
            for m in cluster:
                unassigned.discard(m)

        total_weight = sum(weight(m) for m, _ in valid_items)
        consensus_cluster = max(clusters, key=cluster_weight)
        confidence = cluster_weight(consensus_cluster) / total_weight if total_weight else 0.0

        anchor = max(consensus_cluster, key=lambda m: (weight(m), len(responses[m])))
        out_cluster = [m for m, _ in valid_items if m not in consensus_cluster]

        disputed_flag = bool(out_cluster) and confidence < dispute_confidence
        if disputed_flag:
            consensus_text = "Models disagreed."
            disputed = "\n\n---\n\n".join(f"{m}: {responses[m]}" for m, _ in valid_items)
        else:
            consensus_text = responses[anchor]
            disputed = "\n\n---\n\n".join(f"{m}: {responses[m]}" for m in out_cluster) if out_cluster else ""

        agents_out_v: List[Dict[str, Any]] = []
        for m, t in valid_items:
            if disputed_flag:
                vote = "minority" if m in consensus_cluster else "dissent"
            elif m == anchor:
                vote = "anchor"
            elif m in consensus_cluster:
                vote = "consensus"
            else:
                vote = "dissent"
            agents_out_v.append({"model": m, "response": t, "vote": vote})
        agents_out_v.extend(error_agents)

        cluster_entropy = _normalized_entropy([cluster_weight(c) for c in clusters])

        return {
            "consensus": consensus_text,
            "confidence": round(confidence, 3),
            "entropy": round(cluster_entropy, 3),
            "disputed": disputed,
            "disputed_flag": disputed_flag,
            "agents": agents_out_v,
            "similarity_method": method,
        }
