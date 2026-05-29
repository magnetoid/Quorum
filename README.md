# Quorum

> One question. A council of models. A single answer. Disagreement made visible.

Quorum is a consensus reasoning platform that orchestrates multiple LLMs, measures agreement, detects disagreement, learns from feedback, and exposes the result through REST, OpenAI-compatible APIs, GraphQL, MCP, CLI, and streaming interfaces.

## Why Quorum?

Most AI frameworks orchestrate agents.

Quorum evaluates them.

Instead of asking one model and hoping it's correct, Quorum asks a council of models, clusters responses, measures confidence, surfaces disagreement, and continuously improves model reputation by domain.

## Core Features

### Consensus Engine
- Multi-model parallel execution
- Reputation-weighted voting
- Canonical answer detection (Yes/No, A/B/C/D, numeric)
- Semantic consensus using embeddings
- Lexical fallback voting
- Disputed-zone detection
- Confidence scoring
- Domain-aware councils

### AI Infrastructure
- REST API
- OpenAI-compatible API
- GraphQL API
- MCP Server (SSE)
- MCP stdio transport
- CLI interface
- Streaming responses (SSE)

### Reliability
- Provider retries
- Exponential backoff
- Provider failure isolation
- Shared HTTP connection pools
- Budget-aware execution
- Graceful degradation

### Intelligence Layer
- Semantic voting
- Embedding clustering
- Contradiction protection
- Reputation learning
- Domain classification
- Tier escalation

### Performance
- Persistent Async HTTP clients
- Optional Redis cache
- Response caching
- Parallel execution
- Connection pooling

## Architecture

```text
                    Applications

      Open WebUI   LibreChat   LangChain   Custom Apps
             \         |          |          /
              \        |          |         /

                 REST / OpenAI / GraphQL
                            |
                            v
                     +-------------+
                     |   Quorum    |
                     +-------------+
                            |
        +-------------------+-------------------+
        |                   |                   |
        v                   v                   v
     Voting            Reputation          Router
     Engine             Engine             Engine
        |                   |                   |
        +-------------------+-------------------+
                            |
               +------------+------------+
               |                         |
               v                         v
          Redis Cache              SQLite History
               |                         |
               +------------+------------+
                            |
                            v
                     Provider Layer
                            |
      OpenAI  Claude  Gemini  Ollama  Groq  DeepSeek
```

## Supported Interfaces

### REST

```bash
POST /api/ask
```

### OpenAI Compatible

```bash
POST /v1/chat/completions
```

Supports:

```json
{
  "model": "quorum",
  "stream": true
}
```

### GraphQL

```graphql
mutation {
  ask(
    prompt: "Explain vector databases"
    domain: "architecture"
  ) {
    consensus
    confidence
    disputedFlag
  }
}
```

### MCP

Tools:

- quorum_ask
- quorum_council
- quorum_history
- quorum_model_stats

## Semantic Voting

Quorum now supports hybrid semantic consensus.

```bash
pip install "quorum[semantic]"
```

```bash
QUORUM_SEMANTIC_VOTING=auto
QUORUM_SEMANTIC_MODEL=all-MiniLM-L6-v2
QUORUM_SEMANTIC_WEIGHT=0.7
```

Voting pipeline:

1. Canonical answer detection
2. Semantic embeddings
3. Cosine similarity clustering
4. Lexical fallback
5. Consensus generation

## Redis Cache

```bash
REDIS_URL=redis://localhost:6379/0
QUORUM_CACHE_TTL_SECONDS=3600
```

Benefits:

- Faster responses
- Reduced API costs
- Lower latency
- Provider load reduction

## Production Features

### Security

```bash
QUORUM_API_KEY=secret
```

Supports:

- Authorization: Bearer
- X-Quorum-Key

### CORS

```bash
QUORUM_ALLOWED_ORIGINS=https://app.example.com
```

### Provider Resilience

```bash
QUORUM_PROVIDER_RETRIES=2
QUORUM_PROVIDER_TIMEOUT=60
QUORUM_PROVIDER_BACKOFF_BASE=0.5
```

## Current Platform Status

| Capability | Status |
|------------|---------|
| REST API | ✅ |
| OpenAI Compatible API | ✅ |
| GraphQL API | ✅ |
| MCP SSE | ✅ |
| MCP stdio | ✅ |
| Streaming | ✅ |
| Semantic Voting | ✅ |
| Reputation Learning | ✅ |
| Redis Cache Foundation | ✅ |
| Provider Retry Logic | ✅ |
| Connection Pooling | ✅ |
| Multi-Provider Councils | ✅ |

## Roadmap

### Near Term
- Redis integration into engine
- Semantic cache
- Contradiction detector
- Prometheus metrics
- OpenTelemetry tracing

### Advanced
- Tool-calling councils
- RAG memory layer
- Distributed execution
- Kubernetes deployment
- Multi-node councils

## Vision

Quorum is evolving from a consensus engine into a complete AI decision layer:

- AI Gateway
- Consensus Engine
- MCP Server
- GraphQL Service
- Multi-Agent Platform
- Model Evaluation Layer
- AI Infrastructure Backbone

Instead of choosing one model, Quorum lets organizations trust a council.
