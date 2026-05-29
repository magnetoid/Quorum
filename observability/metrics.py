"""Prometheus metrics for Quorum."""
from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

REQUESTS_TOTAL = Counter(
    "quorum_requests_total",
    "Total Quorum engine requests",
    ["domain"],
)

REQUEST_DURATION = Histogram(
    "quorum_request_duration_seconds",
    "Quorum engine request duration in seconds",
    ["domain"],
)

ACTIVE_REQUESTS = Gauge(
    "quorum_active_requests",
    "Currently active Quorum engine requests",
)

PROVIDER_REQUESTS = Counter(
    "quorum_provider_requests_total",
    "Total provider calls",
    ["provider"],
)

PROVIDER_FAILURES = Counter(
    "quorum_provider_failures_total",
    "Total provider failures",
    ["provider"],
)

PROVIDER_LATENCY = Histogram(
    "quorum_provider_latency_seconds",
    "Provider request latency in seconds",
    ["provider"],
)

CONSENSUS_CONFIDENCE = Histogram(
    "quorum_consensus_confidence",
    "Consensus confidence scores",
    buckets=(0.0, 0.25, 0.5, 0.66, 0.75, 0.9, 1.0),
)

DISPUTED_TOTAL = Counter(
    "quorum_disputed_total",
    "Total disputed Quorum results",
    ["domain"],
)

TOKENS_INPUT_TOTAL = Counter(
    "quorum_tokens_input_total",
    "Total input tokens reported by providers",
    ["provider"],
)

TOKENS_OUTPUT_TOTAL = Counter(
    "quorum_tokens_output_total",
    "Total output tokens reported by providers",
    ["provider"],
)

COST_USD_TOTAL = Counter(
    "quorum_cost_usd_total",
    "Total estimated provider cost in USD",
    ["provider"],
)

CACHE_HITS_TOTAL = Counter(
    "quorum_cache_hits_total",
    "Total cache hits",
)

CACHE_MISSES_TOTAL = Counter(
    "quorum_cache_misses_total",
    "Total cache misses",
)
