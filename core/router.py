"""Domain classification for incoming queries.

V1 strategy: regex word-boundary matching against a small per-domain keyword
list. Word boundaries (`\\b`) prevent false positives like `encode → code` or
`scope → code`. This is still a heuristic — embedding-based or LLM-based
routing is on the roadmap.

If domain is explicitly passed by the caller (CLI `--domain`, MCP arg, REST
`domain` field), the router is bypassed entirely."""
from __future__ import annotations

import re
from typing import Iterable

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


class Router:
    def __init__(self, config: AppConfig):
        self.config = config

    def classify_domain(self, prompt: str) -> str:
        prompt_lower = prompt.lower()
        for domain, words in _DOMAIN_KEYWORDS.items():
            if _contains_any(prompt_lower, words):
                return domain
        return "factual"
