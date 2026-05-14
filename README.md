<div align="center">

<img src="assets/quorum.png" alt="Quorum logo — a council of models, voting" width="320" />

# Quorum

### A consensus reasoning engine for LLMs.

*One question. A council of models. A single answer, with disagreement made visible.*

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Status: alpha](https://img.shields.io/badge/status-alpha-yellow.svg)]()
[![Tests](https://img.shields.io/badge/tests-87%20passing-brightgreen.svg)]()
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![Sponsor](https://img.shields.io/badge/Sponsor-%E2%9D%A4-ff69b4.svg)](https://github.com/sponsors/YOUR_USERNAME)

</div>

---

## The problem

A single LLM's answer is a guess. Ask GPT, Claude, Llama, and Mixtral the same question and you'll get four different answers — and no native way to know which to trust.

The mainstream agent frameworks (CrewAI, AutoGen, LangGraph) orchestrate agents but **don't vote**.
Routing tools (OpenRouter, LiteLLM) switch between models but **don't aggregate**.
Research approaches (Mixture-of-Agents, Self-Consistency, Multi-Agent Debate) are powerful but **not packaged for production**.

## What Quorum does

Quorum treats your LLM stack as a **council**:

1. **Runs every member in parallel** across 17 supported providers.
2. **Clusters their answers** using token-similarity voting, weighted by each model's track record per domain.
3. **Surfaces consensus *and* disputed zones** — so you trust the council when they agree, and audit the gap when they don't.
4. **Learns over time** — a feedback loop adjusts per-model reputation in each domain after every query.

It exposes itself via **CLI, REST, an OpenAI-compatible router, and MCP** — drop it into any existing app that already speaks one of those.

---

## 30-second demo

```
$ quorum ask "Is REST or gRPC better for streaming workloads?" --domain architecture

Domain:     architecture     Confidence: 0.83     Cost: $0.0041
Consensus:  gRPC, with HTTP/2 streaming and bidirectional channels, is
            better-suited for high-throughput streaming workloads.
Disputed:   (none)
Council:
    ✓  ollama/qwen2.5-coder    consensus
    ✓  claude-sonnet-4-6       anchor
    ✓  gpt-4o                  consensus
    ·  groq/llama-3.3-70b      consensus

Query ID: 7a3f...c91
```

When the council disagrees, you see it:

```
$ quorum ask "Should we shard this Postgres database?" --domain architecture

Domain:     architecture     Confidence: 0.42     Cost: $0.0089
Consensus:  Models disagreed.
Disputed:
  ─ claude-sonnet-4-6:  Shard once the working set exceeds RAM (typical
    around 100GB). Above that, sharding outperforms vertical scaling.
  ─ gpt-4o:             Avoid sharding until you've exhausted read replicas,
    connection pooling, and partitioning. Sharding adds operational cost
    that often dwarfs its benefit until ~1TB.
  ─ ollama/llama3.2:    Consider Postgres logical replication first.
Council:
    ✗  claude-sonnet-4-6   dissent
    ✗  gpt-4o              dissent
    ✗  ollama/llama3.2     dissent
```

You don't get a confidently-wrong middle ground. You get the real picture.

---

## Where Quorum helps

Different domains, same pattern: ask the council, see where they line up, see where they don't.

### 🛠 Software engineering
*"Is this race condition real or am I seeing things?"* — three models agreeing on the diagnosis is much stronger evidence than one. Disagreement on a fix means it's worth a second look before merging.
```bash
quorum ask "Review this auth middleware change: <paste>" --domain code
```

### 🏗 Architecture & system design
*"Should we use Kafka or SQS?"* — when the council clusters around "depends on X" you've found the actual decision criterion; when they split cleanly you've found the unsolved trade-off in your situation.
```bash
quorum ask "Kafka vs SQS for our event volume" --domain architecture
```

### 💰 Financial analysis
*"What's the typical valuation multiple for SaaS at $20M ARR with 80% NRR?"* — quantitative answers benefit most from consensus because outliers are obvious. The disputed zone tells you when a number is uncertain.
```bash
quorum ask "Q3 burn rate sensitivity to a 15% revenue dip" --domain finance
```

### ⚖️ Legal & compliance research
*"Does GDPR Article 17 apply if the data is in backups?"* — surfacing jurisdictional disagreements is the entire point. Each model carries different training emphasis; a council exposes the gaps.
```bash
quorum ask "Does CCPA require deletion from cold backups?" --domain legal
```

### 📚 Research & fact-checking
*"What's the current best estimate of [obscure scientific quantity]?"* — when multiple models agree on a number you have weak corroboration; when they disagree you've found something that needs a primary source.
```bash
quorum ask "Average Atlantic hurricane intensity trend, last decade" --domain factual
```

### ✍️ Creative work
*"Three openings for a noir short story about a tax accountant."* — here you *want* the dissent. The disputed zone is the brainstorming buffet.
```bash
quorum ask "Three openings for a noir story about a tax accountant" --domain creative
```

### 🎓 Education & tutoring
A single model that hallucinates an explanation passes off as authoritative. A council that *disagrees* about an explanation is the moment a student learns to evaluate sources.

### 🧪 Product decisions
*"Should we add this feature?"* — when the council all comes back with the same reason it's a strong signal. When they all hedge differently, that's the signal too.

---

## How Quorum compares

|  | Quorum | CrewAI | AutoGen | Mixture of Agents | Self-Consistency | OpenRouter / LiteLLM |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| Parallel multi-model **voting** | ✅ | ⚠️ orchestrate, don't vote | ⚠️ debate, no formal vote | ✅ via aggregation layer | ❌ single model | ❌ routing only |
| Per-domain **reputation learning** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Disputed zone** surfaced | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **MCP server** out of the box | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **OpenAI-compatible** drop-in | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ |
| One-line install | ✅ | ⚠️ | ⚠️ | ❌ | ❌ | ⚠️ |

The big agent frameworks own *orchestration*. Mixture-of-Agents owns *layered synthesis*. **Quorum owns consensus.**

---

## Install

```bash
git clone https://github.com/magnetoid/quorum
cd quorum
bash install.sh
```

`install.sh` checks Python ≥3.11, creates `.venv`, installs the package, copies `.env.example → .env`, and drops you into the interactive setup wizard:

```
Step 1 · Local Ollama (free tier)
  ✓ Ollama reachable — 2 model(s):
      llama3.2
      qwen2.5-coder

Step 2 · Pick providers and paste keys
  ┌────┬──────────────┬───────┬────────────────────────────────┐
  │ #  │ Provider     │ State │ API key                        │
  ├────┼──────────────┼───────┼────────────────────────────────┤
  │ 1  │ ollama       │  ON   │ (free / local — no key needed) │
  │ 2  │ anthropic    │  off  │ ANTHROPIC_API_KEY (missing)    │
  │ 3  │ openai       │  off  │ OPENAI_API_KEY (missing)       │
  │ 4  │ openrouter   │  off  │ OPENROUTER_API_KEY (missing)   │
  │ 5  │ gemini       │  off  │ GEMINI_API_KEY (missing)       │
  ...
  └────┴──────────────┴───────┴────────────────────────────────┘

  Action  [#=toggle | k <#>=set key | a=enable defaults | done]:  k 2
  Get a key: https://console.anthropic.com/settings/keys
  Paste ANTHROPIC_API_KEY: ****
  ✓ Saved ANTHROPIC_API_KEY and enabled anthropic
```

Number-toggle for on/off. `k <num>` for paste-a-key. `a` for "enable my four common defaults" (Ollama + Anthropic + OpenAI + OpenRouter). `done` to move on.

After setup, `quorum doctor` runs to verify everything is reachable.

---

## Quick start

Once installed, these commands cover the basics:

```bash
quorum ask "your question here"                      # default council
quorum ask "Q" --domain finance --budget 0.05        # domain + budget
quorum ask "Q" --models ollama/llama3.2,claude-sonnet-4-6,groq/llama-3.3-70b
quorum feedback <query_id> --score 1.0               # the council was right
quorum feedback <query_id> --score -1.0              # the council was wrong
quorum models --stats                                # reputation per (model, domain)
quorum history --limit 10                            # recent queries
```

---

## 17 LLM providers, one council

Quorum talks to 17 providers out of the box. Mix and match in any council; toggle on/off with `quorum config`.

| Direct adapters | OpenAI-compatible (shared adapter) |
|---|---|
| Ollama *(local, free)* | Groq |
| Anthropic *(Claude family)* | Together AI |
| OpenAI *(GPT, o-series)* | DeepSeek |
| OpenRouter *(gateway to 100+ more)* | Fireworks |
| Google Gemini | Mistral |
| Cohere | xAI *(Grok)* |
|  | Perplexity |
|  | Anyscale |
|  | Cerebras |
|  | HuggingFace Inference |
|  | Azure OpenAI |

AWS Bedrock and Vertex AI are reachable via [LiteLLM](https://github.com/BerriAI/litellm) as an OpenAI-compatible proxy. Native adapters are on the roadmap.

Adding a new provider is usually one entry in [`adapters/__init__.py`](adapters/__init__.py) — see [`CONTRIBUTING.md`](CONTRIBUTING.md).

---

## Four ways to call Quorum

### 1. CLI

```bash
quorum ask "Is sourdough actually healthier than yeast bread?" --domain factual
```

### 2. REST — Quorum-native shape

```bash
quorum serve   # FastAPI on :8000, MCP mounted at /mcp

curl -X POST http://localhost:8000/api/ask \
     -H "content-type: application/json" \
     -d '{"prompt":"Is REST or gRPC better?","domain":"architecture"}'
```

Returns the full consensus result: `consensus`, `confidence`, `disputed`, `disputed_flag`, per-`agents`, `domain`, `cost`, `query_id`.

### 3. REST — OpenAI-compatible router

Point any OpenAI-compatible client at `http://localhost:8000/v1` and select a council via the `model` field:

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
     -H "content-type: application/json" \
     -d '{
       "model": "quorum",
       "messages": [{"role": "user", "content": "Explain entropy in one paragraph"}]
     }'
```

| `model` value | Behavior |
|---|---|
| `quorum` | Full tier escalation across the default council |
| `quorum:code` | Council scoped to the `code` domain |
| `quorum:claude-sonnet-4-6,gpt-4o,groq/llama-3.3-70b` | Explicit council |
| `quorum:legal:claude-opus,gpt-4o` | Domain + explicit council |
| `claude-sonnet-4-6` | Single-model passthrough (no consensus) |

The response keeps the standard OpenAI shape (drop-in for LangChain, llm CLI, Open WebUI, etc.), with an extra `quorum` field carrying the full consensus result:

```json
{
  "id": "chatcmpl-7a3f...",
  "object": "chat.completion",
  "model": "quorum",
  "choices": [{"index": 0, "message": {"role": "assistant", "content": "..."}, "finish_reason": "stop"}],
  "usage": {"prompt_tokens": 412, "completion_tokens": 380, "total_tokens": 792},
  "quorum": {
    "consensus": "...",
    "disputed": "...",
    "disputed_flag": false,
    "confidence": 0.83,
    "agents": [...],
    "domain": "architecture",
    "query_id": "7a3f...",
    "cost": "$0.0041"
  }
}
```

### 4. MCP — drop into Claude Code, Claude Desktop, Cursor

```json
{
  "mcpServers": {
    "quorum": {
      "command": "/abs/path/to/.venv/bin/quorum",
      "args": ["mcp"]
    }
  }
}
```

Exposes four tools:

| Tool | Purpose |
|---|---|
| `quorum_ask` | Submit a question, get the aggregated consensus result |
| `quorum_council` | Submit a question, get raw per-model responses (no aggregation) |
| `quorum_history` | List recent queries from the local SQLite store |
| `quorum_models_stats` | Reputation scores per `(model, domain)` |

---

## Architecture

```
                       ┌──────────┐
   query ─────────────▶│  Router  │── domain classification
                       └────┬─────┘
                            ▼
                     ┌────────────┐         parallel
                     │   Engine   │──┬──┬──┬──┬──────▶ adapters
                     └─────┬──────┘  ▼  ▼  ▼  ▼       (17 providers)
                           │       Ollama Claude GPT Groq …
                           ▼
                   ┌───────────────┐
                   │ Voting v1     │── consensus + disputed cluster
                   │ (token-       │
                   │  Jaccard)     │
                   └───────┬───────┘
                           ▼
                   ┌───────────────┐
                   │ Reputation    │── (model, domain) → weight
                   │ (SQLite)      │      ↑
                   └───────┬───────┘      │
                           ▼              │
                   ┌───────────────┐      │
                   │  Output       │      │
                   │  (JSON)       │─── CLI / REST / MCP / OpenAI router
                   │               │      │
                   └───────────────┘      │
                                          │
                   ┌──────────────────────┴────────────┐
                   │  quorum feedback <id> --score N   │
                   │  ↳ confirms or flips reputation   │
                   └───────────────────────────────────┘
```

---

## Self-improving, self-healing — honest status

Quorum's pitch is that the council gets smarter with use. Here's what's real today vs. on the roadmap:

| Capability | Status |
|---|---|
| Per-`(model, domain)` reputation table (SQLite) | ✅ |
| Reputation **weights consensus voting** | ✅ |
| Reputation **updates from consensus participation** | ✅ tentative deltas saved per query |
| `quorum feedback {id} --score N` | ✅ scaled apply, sign-flip on negative, drop on zero |
| `quorum history` and `quorum models --stats` | ✅ |
| `quorum doctor` health checks | ✅ |
| `quorum repair` detect & fix common issues | ✅ |
| `quorum clean` history / pending / reputation / caches | ✅ |
| `quorum config` interactive feature toggles | ✅ |
| Semantic voting (embeddings / peer review) — catches "42 vs 43" | 🟡 design only |
| Auto-disable adapters that error >50% over a window | 🔴 roadmap |
| Distributed multi-host council | 🔴 roadmap |

Every "self-improving" claim above maps to a working command or a clearly-flagged roadmap item. **No vapor.**

---

## Configuration

`quorum config` is the interactive editor. Five submenus:

```
QUORUM CONFIG
  [1] Providers         toggle on/off, edit API keys
  [2] Default council   models that run when no domain is given
  [3] Domain councils   per-domain model selection
  [4] Budget            per-query USD cap
  [5] Confidence        cluster + dispute thresholds
  [s] Save & exit
  [q] Quit without saving
```

All settings live in [`config.yaml`](config.yaml) (which `quorum config` reads/writes) and API keys live in `.env` (also auto-managed). You can hand-edit either if you prefer.

---

## Maintenance commands

When something goes wrong, three commands cover the diagnostic + repair surface:

| Command | What it does |
|---|---|
| `quorum doctor` | Health check: Python version, Ollama reachability, API-key presence, configured tiers / domains / personas, per-provider ping with token + cost |
| `quorum repair [-y]` | Detects & offers to fix: missing or corrupted SQLite DB, legacy env keys (`OLLAMA_HOST` → `OLLAMA_BASE_URL`), missing `config.yaml` sections, providers in the registry that aren't in `config.yaml` yet. Non-destructive — corrupted files are *renamed*, never deleted. |
| `quorum clean --history --pending --reputation --pycache --all [-y]` | Clear past query records, unconfirmed reputation deltas, reputation scores, or Python tool caches. Confirms before acting. |

---

## Full command reference

```
quorum ask <prompt>             # ask the council
  --domain <name>               # code | finance | architecture | legal | creative | factual
  --models <m1,m2,...>          # explicit council, comma-separated
  --budget <usd>                # per-query USD cap (default 0.05)

quorum feedback <query_id>      # apply outcome to reputation
  --score <-1.0 .. 1.0>         # positive confirms, negative flips, 0 drops

quorum history --limit N        # recent queries from SQLite
quorum models                   # list configured providers
quorum models --stats           # per-(model, domain) reputation

quorum setup                    # interactive first-run wizard (re-runnable)
quorum config                   # interactive editor (providers, councils, ...)
quorum doctor                   # health check + per-adapter ping
quorum repair [-y]              # detect & fix common issues
quorum clean [flags]            # clear DB tables and/or Python caches

quorum serve                    # FastAPI on :8000 + MCP at /mcp
quorum mcp                      # MCP server over stdio (for local agents)
```

---

## REST endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET`  | `/healthz` | Liveness probe + provider summary |
| `POST` | `/api/ask` | Quorum-native consensus query |
| `POST` | `/v1/chat/completions` | OpenAI-compatible router |
| (SSE)  | `/mcp/*` | MCP server-sent-events transport |

---

## Roadmap

- [x] Parallel multi-model execution (`core/engine.py`)
- [x] Voting v1 — Jaccard cluster consensus + dispute surfacing (`core/voting.py`)
- [x] 17 provider adapters (4 direct + 11 OpenAI-compatible + 2 outliers)
- [x] CLI: `ask`, `setup`, `doctor`, `config`, `repair`, `clean`, `models`, `history`, `feedback`, `serve`, `mcp`
- [x] FastAPI REST endpoint (`POST /api/ask`)
- [x] **OpenAI-compatible router endpoint (`POST /v1/chat/completions`)** — drop-in for any OpenAI client
- [x] MCP server (HTTP/SSE + stdio transports)
- [x] SQLite reputation table + history
- [x] Reputation update loop (consensus participation + `quorum feedback`)
- [x] Word-boundary domain classifier (replaces brittle substring matching)
- [x] Interactive `quorum config` for feature toggles
- [x] CORS + `/healthz` endpoint
- [x] Strict static typing, `mypy` enforcement, and `pytest` coverage
- [x] Optimized SQLite concurrent access (`WAL` mode)
- [x] API Key security for REST endpoints (`X-Quorum-Key` and `Bearer`)
- [ ] **Voting v2** — semantic consensus (embeddings or peer review) to catch numeric / semantic disputes
- [ ] **Retries + circuit breakers + per-provider timeouts** — production-grade resilience
- [ ] **OpenTelemetry GenAI conventions** — Datadog/Honeycomb/Grafana out of the box
- [ ] **Dockerfile + GitHub Actions CI + PyPI release**
- [ ] Cost-based budget enforcement during tier escalation (currently informational)
- [ ] Auto-disable flapping adapters (the last self-healing piece)
- [ ] GraphQL endpoint
- [ ] Web research adapter (citations from live web)
- [ ] AWS Bedrock + Vertex AI native adapters
- [ ] Streaming chat completions on the OpenAI router
- [ ] Hosted demo + benchmark dashboard

---

## Sponsors & funding

Quorum is built and maintained by an independent developer in their spare time. If your team uses it — or wants to — please consider sponsoring. Funding directly unlocks the top roadmap items above:

- **Voting v2** (semantic consensus via embeddings) — biggest open quality issue
- **Hosted demo** so non-developers can try the council without installing
- **Security audit** before recommending Quorum for production internal-tool use
- **Contributor stipends** for tested PRs

[![Sponsor on GitHub](https://img.shields.io/badge/GitHub-Sponsor-ea4aaa?logo=github)](https://github.com/magnetoid)
[![Buy Me a Coffee](https://img.shields.io/badge/Ko--fi-Buy%20me%20a%20coffee-29abe0?logo=ko-fi&logoColor=white)](https://ko-fi.com/magnetoid)

Early backers will be listed here — get in touch if you want a logo placement.

---

## Contributing

PRs welcome — see [`CONTRIBUTING.md`](CONTRIBUTING.md). The smallest valuable contribution is **adding a new adapter** (~5 lines for OpenAI-compatible providers, ~50 for custom shapes — see [`adapters/cohere.py`](adapters/cohere.py) as a template). The biggest valuable one is **a peer-review or embedding-based aggregator** in `core/voting.py` v2.

If you find a bug, run `quorum doctor` and attach the output to your issue — it captures Python version, Ollama state, configured providers, and per-adapter ping in one shot.

---

## Citation

If you use Quorum in research, please cite:

```bibtex
@software{quorum2026,
  title  = {Quorum: A consensus reasoning engine for LLMs},
  author = {Tiosavljevic, Marko},
  year   = {2026},
  url    = {https://github.com/magnetoid/Quorum},
}
```

---

## License

Apache License 2.0 — see [LICENSE](LICENSE).
