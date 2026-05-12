# Quorum 🏛️

> **A consensus reasoning engine that orchestrates multiple LLMs in parallel, aggregates their answers through voting and critique, and surfaces both consensus and disagreement as structured output.**

Quorum doesn't just ask one model; it asks a **council**. It dynamically routes queries based on domain, manages a strict execution budget through tiered fallbacks (Local → Cheap → Premium), and learns over time which models perform best in specific domains using a built-in reputation system.

---

## ✨ Core Features

*   **Tiered Execution:** Always attempts local models (e.g., Ollama) first. Escalates to cheap APIs (e.g., `gpt-4o-mini`, `gemini-flash`), and only invokes premium models (`claude-3.5-sonnet`, `o3`) if the council's confidence remains below a defined threshold. Never exceeds the configured per-query budget.
*   **Disagreement is First-Class:** When models diverge, Quorum doesn't silently hallucinate a middle ground. It explicitly surfaces the "Disputed Zone" and flags the response, allowing users to see exactly where the frontier models disagree.
*   **Domain-Aware Council:** Automatically classifies incoming queries (e.g., `code`, `finance`, `legal`, `architecture`, `creative`, `factual`) and selects the optimal combination of models for that specific domain.
*   **Reputation-Weighted Voting:** Tracks win/loss ratios per model, per domain, stored locally in SQLite. A model's vote carries more weight if it has a proven track record in that domain.
*   **Persona Injection:** Each adapter receives a domain-specific system prompt to frame the model's perspective before it answers (e.g., framing a model as a "meticulous legal analyst" vs. a "careful quantitative analyst").
*   **Multi-Interface:** Interact via a beautiful CLI (`typer`), integrate via REST API (`FastAPI`), or connect to IDEs via the upcoming MCP (Model Context Protocol) server.

---

## 🚀 Installation

### Prerequisites
*   Python 3.11+
*   [Ollama](https://ollama.com/) (Optional, but highly recommended for the free local tier)

### Setup

```bash
# Clone the repository
git clone https://github.com/magnetoid/Quorum.git
cd Quorum

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install the package and dependencies
pip install -e ".[dev]"

# Set up environment variables
cp .env.example .env
```

Edit your `.env` file to add your API keys:
```env
ANTHROPIC_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
OPENROUTER_API_KEY=your_key_here
OLLAMA_BASE_URL=http://localhost:11434
```

---

## 💻 CLI Usage

Quorum provides a rich terminal interface for interacting with the engine.

```bash
# Basic query (auto-routes domain and uses default budget)
quorum ask "What are the trade-offs of microservices vs monoliths?"

# Specify domain and strict budget
quorum ask "Evaluate AAPL Q3 earnings strategy" --domain finance --budget 0.05

# Bypass tiering and force specific models
quorum ask "Write a Python script for a websocket server" --models ollama/qwen2.5-coder,claude-sonnet

# View model reputation and statistics
quorum models --stats

# Provide feedback on a query to update model reputation weights (-1.0 to 1.0)
quorum feedback {query_id} --score 1.0

# Start the REST + MCP server
quorum serve
```

---

## 🔌 REST API

When running `quorum serve`, the FastAPI server exposes endpoints for integration.

**POST `/api/ask`**

```json
// Request
{
  "prompt": "Explain quantum entanglement.",
  "domain": "factual",
  "budget": 0.02
}

// Response (Consensus Output Schema)
{
  "consensus": "Quantum entanglement is a physical phenomenon where particles become interconnected such that the state of one instantly influences the state of the other, regardless of distance.",
  "confidence": 0.95,
  "disputed": "",
  "disputed_flag": false,
  "agents": [
    {
      "model": "ollama/llama3.2",
      "response": "Quantum entanglement is a physical phenomenon...",
      "vote": "Quantum entanglement is a physical phenomenon"
    },
    {
      "model": "gpt-4o-mini",
      "response": "It is a quantum mechanical phenomenon...",
      "vote": "It is a quantum mechanical phenomenon"
    }
  ],
  "domain": "factual",
  "cost": "$0.0004",
  "query_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

## ⚙️ Configuration

Quorum's behavior is entirely driven by `config.yaml`. 

You can define your tiers, domain mappings, confidence thresholds, and pricing.

```yaml
tiers:
  local:
    models: [ollama/llama3.2, ollama/qwen2.5-coder]
    confidence_threshold: 0.75
  cheap:
    models: [gemini-flash, gpt-4o-mini]
    confidence_threshold: 0.85
  premium:
    models: [claude-opus-4, o3]
    confidence_threshold: 0.95

budget:
  default_per_query: 0.05

domains:
  code:        [ollama/qwen2.5-coder, claude-sonnet, gpt-4o]
  finance:     [claude-opus, o3, gemini-pro]
  architecture:[claude-sonnet, gpt-4o, ollama/llama3.2]
```

---

## 🏗️ Architecture

```text
quorum/
├── core/
│   ├── router.py       # Domain classifier, dynamic council selection
│   ├── engine.py       # Tiered parallel model execution
│   ├── voting.py       # Weighted aggregation, dispute detection
│   └── reputation.py   # Per-model score tracking via SQLite
├── adapters/
│   ├── base.py         # Abstract interface & AdapterResponse schema
│   ├── ollama.py       # Local Ollama adapter
│   ├── anthropic.py    # Claude via Anthropic API
│   ├── openai.py       # GPT/o3 via OpenAI API
│   └── openrouter.py   # OpenRouter (Gemini, Mistral, etc.)
├── server/
│   ├── api.py          # FastAPI REST endpoints
│   └── mcp.py          # MCP server integration (Pending)
├── cli/
│   └── main.py         # Typer CLI interface
└── storage/
    └── db.py           # SQLite query history & reputation
```

---

## 📄 License

MIT License. See `LICENSE` for more details.
