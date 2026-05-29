# Quorum 🛡️

> **Disagreement made visible. Consensus made reliable.**

Quorum is a professional-grade **consensus reasoning platform** that orchestrates councils of Large Language Models (LLMs) to solve the "hallucination problem." Instead of trusting a single AI, Quorum asks a council, measures agreement, detects contradictions, and learns which models are experts in specific domains.

---

## 🚀 Why Quorum?

Most AI frameworks orchestrate agents. **Quorum evaluates them.**

- **The Problem:** Single LLMs often provide confident but incorrect answers (hallucinations).
- **The Solution:** Quorum uses a multi-tier, multi-model approach with a weighted voting engine. It surfaces disagreement as a "Disputed Zone," ensuring you never unknowingly rely on a minority opinion.

### Who is this for?
- **Enterprise decision-makers** who need reliable AI-generated reports.
- **Developers** building safety-critical AI applications (Legal, Finance, Healthcare).
- **Researchers** evaluating model performance across different domains.
- **Power users** who want the "best possible answer" by combining the strengths of GPT-4, Claude, Gemini, and local models.

---

## ✨ Core Features

### 🏛️ Advanced Consensus Engine
- **Speculative Tiered Execution:** Automatically starts higher-tier models (Premium) if lower tiers (Local/Cheap) are too slow or fail to reach consensus.
- **Domain-Aware Adaptive Thresholds:** Stricter agreement requirements for `code` and `logic`; higher tolerance for `creative` and `prose`.
- **Hybrid Semantic Voting:** Combines lexical (Jaccard) similarity with high-dimensional semantic embeddings.
- **Remote Embedding Fallbacks:** Automatically uses OpenAI embeddings if local hardware acceleration isn't available.

### 📈 Intelligence & Reliability
- **Non-Linear Reputation Learning:** Models gain or lose reputation based on performance. Premium models are penalized more heavily for "confident hallucinations."
- **Latency Tracking:** Measures and reports execution time per agent to identify bottlenecks.
- **Disputed Zone Detection:** Explicitly flags when models disagree, providing a "Dissenting Opinion" summary.
- **Budget-Aware Routing:** Stops execution once a specified cost limit is reached or consensus is met.

### 🔌 Enterprise Infrastructure
- **OpenAI-Compatible API:** Drop-in replacement for any OpenAI-compatible client.
- **REST & GraphQL APIs:** Fully typed interfaces for modern web applications.
- **MCP Server (Model Context Protocol):** Native support for Claude Desktop and other MCP-enabled tools.
- **Interactive CLI:** A powerful command-line tool for local reasoning and system management.

---

## 🛠️ Installation

### 1. Requirements
- Python 3.11+
- (Optional) Redis for caching.
- (Optional) `sentence-transformers` for local semantic voting.

### 2. Basic Setup
```bash
git clone https://github.com/magnetoid/Quorum.git
cd Quorum
pip install -e .
```

### 3. Full Installation (Recommended)
Includes semantic voting and development tools:
```bash
pip install -e ".[dev,semantic]"
```

---

## ⚙️ Configuration

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```
2. Add your API keys:
   - `OPENAI_API_KEY`
   - `ANTHROPIC_API_KEY`
   - `GEMINI_API_KEY`
   - ... (see `.env.example` for all supported providers)

3. Configure your council in `config.yaml`:
   ```yaml
   tiers:
     local:
       models: ["ollama/llama3.2", "ollama/mistral"]
       confidence_threshold: 0.7
     premium:
       models: ["gpt-4o", "claude-3-5-sonnet-20241022"]
       confidence_threshold: 0.8
   ```

---

## 📖 How to Use

### Command Line Interface (CLI)
Ask a question and see the council's reasoning:
```bash
# Basic usage
quorum ask "Is it safe to use Python's multiprocessing with SQLite?"

# Specify a domain for specialized thresholds
quorum ask "Optimize this SQL query: SELECT * FROM users..." --domain code

# Set a strict budget
quorum ask "Explain quantum entanglement." --budget 0.02
```

### REST API
```bash
curl -X POST http://localhost:8000/api/ask \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is the capital of France?", "domain": "factual"}'
```

### OpenAI-Compatible API (with custom budget)
Quorum supports an extra header to control the consensus budget:
```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer $QUORUM_API_KEY" \
  -H "X-Quorum-Budget: 0.10" \
  -d '{
    "model": "quorum",
    "messages": [{"role": "user", "content": "How do I fix a race condition?"}]
  }'
```

---

## 🔍 Problems Quorum Solves

| Problem | Quorum's Solution |
| :--- | :--- |
| **Hallucinations** | Cross-references multiple models and flags disagreements. |
| **Inconsistency** | Uses reputation-weighted voting to favor historically accurate models. |
| **High Costs** | Uses a "Local First" tiered strategy, only hitting expensive APIs if needed. |
| **Vendor Lock-in** | Orchestrates OpenAI, Anthropic, Gemini, Ollama, and more in one unified layer. |
| **Lack of Transparency** | Provides full telemetry (cost, latency, token usage) for every council member. |

---

## 🛣️ Roadmap

- [x] Speculative Tiered Execution
- [x] Remote Embedding Fallbacks
- [x] Domain-Aware Adaptive Thresholds
- [ ] Redis-backed Semantic Cache
- [ ] Real-time "Deliberation Round" (Models critiquing each other)
- [ ] Prometheus/Grafana Dashboard

---

## 📄 License
Quorum is released under the **Apache-2.0 License**. See [LICENSE](LICENSE) for details.

---

## 🤝 Contributing
We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to help improve Quorum.
