"""Domain classification for incoming queries.

V1 strategy: regex word-boundary matching against a small per-domain keyword
list. Word boundaries (`\\b`) prevent false positives like `encode → code` or
`scope → code`. This is still a heuristic — embedding-based or LLM-based
routing is on the roadmap.

If domain is explicitly passed by the caller (CLI `--domain`, MCP arg, REST
`domain` field), the router is bypassed entirely.

Optional embedding-kNN fallback: when no keyword matches, instead of blindly
defaulting to `factual`, the router can classify by nearest labeled exemplar in
embedding space (reusing the same embeddings as voting). A non-parametric
embedding-kNN matches trained routers without any training data or drift risk.
It is opt-in via `QUORUM_SEMANTIC_ROUTING=on` and degrades to the `factual`
default when embeddings are unavailable or no exemplar clears the floor."""
from __future__ import annotations

import os
import re
from functools import lru_cache
from typing import Iterable, List, Optional, Tuple

from config import AppConfig


# Per-domain keyword lists. Each entry must appear as a whole word in the
# query (case-insensitive) to count. Order matters only for tie-breaking —
# the first domain with a hit wins.
_DOMAIN_KEYWORDS = {
    "code":         ["code", "function", "class", "bug", "python", "javascript",
                     "typescript", "rust", "java", "compile", "refactor", "api"],
    "finance":      ["stock", "stocks", "finance", "price", "budget", "market",
                     "invest", "earnings", "revenue", "profit", "tax"],
    "legal":        ["law", "legal", "court", "sue", "attorney", "lawyer",
                     "contract", "lawsuit", "jurisdiction", "compliance"],
    "architecture": ["architecture", "design", "scale", "scaling", "microservice",
                     "monolith", "system", "infrastructure", "tradeoff"],
    "creative":     ["write", "story", "creative", "poem", "imagine", "fiction",
                     "narrative", "character", "plot"],
}


def _contains_any(text: str, words: Iterable[str]) -> bool:
    return any(re.search(rf"\b{re.escape(w)}\b", text) for w in words)


# A few labeled exemplars per domain for the embedding-kNN fallback. These are
# deliberately phrased WITHOUT the regex keywords above, so they cover the
# wording the keyword matcher misses. `factual` exemplars are general-knowledge
# questions so that genuinely generic prompts land on the catch-all.
_DOMAIN_EXEMPLARS = {
    "code": [
        "Reverse a linked list in place and return the new head.",
        "Why does my async handler resolve before the database write finishes?",
        "Refactor this duplicated logic into a reusable helper.",
    ],
    "finance": [
        "Should I put my savings into an index fund or pick individual shares?",
        "How did the company's latest quarterly results compare to estimates?",
        "Explain how compounding affects long-term returns.",
    ],
    "legal": [
        "Is this rental agreement enforceable if it was never signed?",
        "What obligations does GDPR impose on a small SaaS company?",
        "Can I be held liable for a contractor's mistake on my property?",
    ],
    "architecture": [
        "How would you split this monolith to handle ten times the traffic?",
        "Design a fault-tolerant pipeline that survives a region outage.",
        "What are the trade-offs of an event-driven versus a request-response design?",
    ],
    "creative": [
        "Compose a haiku about the rain on a tin roof.",
        "Invent a sympathetic villain for my fantasy novel.",
        "Give me an opening paragraph for a noir mystery.",
    ],
    "factual": [
        "What is the capital of France?",
        "Who wrote War and Peace?",
        "What is the boiling point of water at sea level?",
        "When did the Second World War end?",
    ],
}

# Minimum normalized cosine similarity (get_cosine_similarity maps to [0, 1])
# for an exemplar to claim a keyword-less prompt. Below this we keep `factual`.
_KNN_FLOOR = float(os.getenv("QUORUM_SEMANTIC_ROUTING_FLOOR", "0.6"))


def _semantic_routing_enabled() -> bool:
    return os.getenv("QUORUM_SEMANTIC_ROUTING", "off").lower().strip() in {
        "1", "true", "on", "auto",
    }


@lru_cache(maxsize=1)
def _exemplar_matrix() -> Optional[Tuple[List[str], List[List[float]]]]:
    """Embed the labeled exemplars once. Returns (domains, embeddings) aligned,
    or None when embeddings are unavailable. Cached for the process lifetime;
    call `_exemplar_matrix.cache_clear()` if the embedding backend changes."""
    from core.voting import get_semantic_embeddings

    pairs = [(d, ex) for d, exs in _DOMAIN_EXEMPLARS.items() for ex in exs]
    embeddings = get_semantic_embeddings([ex for _, ex in pairs])
    if not embeddings or len(embeddings) != len(pairs):
        return None
    return [d for d, _ in pairs], embeddings


def _knn_classify(prompt: str) -> Optional[str]:
    """Nearest-exemplar domain for `prompt`, or None if unavailable / below floor."""
    from core.voting import get_semantic_embeddings, get_cosine_similarity

    matrix = _exemplar_matrix()
    if matrix is None:
        return None
    domains, embeddings = matrix

    query = get_semantic_embeddings([prompt])
    if not query:
        return None
    qv = query[0]

    best_domain: Optional[str] = None
    best_sim = -1.0
    for domain, ev in zip(domains, embeddings):
        sim = get_cosine_similarity(qv, ev)
        if sim > best_sim:
            best_sim, best_domain = sim, domain
    return best_domain if best_sim >= _KNN_FLOOR else None


class Router:
    def __init__(self, config: AppConfig):
        self.config = config

    def classify_domain(self, prompt: str) -> str:
        prompt_lower = prompt.lower()
        for domain, words in _DOMAIN_KEYWORDS.items():
            if _contains_any(prompt_lower, words):
                return domain
        # No keyword hit. Optionally fall back to embedding-kNN before defaulting
        # to the `factual` catch-all.
        if _semantic_routing_enabled():
            knn = _knn_classify(prompt)
            if knn:
                return knn
        return "factual"
