<p align="center">
  <img src="assets/quorum.png" width="300" alt="Quorum Logo">
</p>

<h1 align="center">Quorum: The Council of Models</h1>

<p align="center">
  <strong>One Question. A Council of Models. A Single, Trusted Answer.</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue.svg" alt="Python Version">
  <img src="https://img.shields.io/badge/License-Apache--2.0-green.svg" alt="License">
  <img src="https://img.shields.io/badge/Status-Production--Ready-brightgreen.svg" alt="Status">
  <img src="https://img.shields.io/badge/Consensus-Adaptive-orange.svg" alt="Consensus">
</p>

---

## 🏛️ What is Quorum?

Quorum is a professional-grade **consensus reasoning engine** designed to eliminate AI hallucinations and vendor lock-in. Instead of trusting a single LLM, Quorum orchestrates a **council of models** (GPT-4, Claude, Gemini, Llama, etc.), clusters their responses semantically, measures agreement, and surfaces the most reliable answer.

### 🛡️ Solving the "Hallucination Problem"
Single LLMs are often "confidently wrong." Quorum makes **disagreement visible**. If models conflict, Quorum flags a **Disputed Zone**, allowing you to see dissenting opinions rather than blindly trusting a single, potentially incorrect output.

---

## ✨ Key Innovations (V2)

### ⚡ Speculative Tiered Execution
Don't wait for slow models. Quorum starts with local/cheap models and **speculatively launches** higher tiers if consensus isn't reached within seconds. You get the best of both worlds: extreme speed for easy questions and deep reasoning for hard ones.

### 🧠 Domain-Aware Adaptive Thresholds
Consensus isn't one-size-fits-all.
- **`code` & `logic`**: Stricter similarity checks (0.4) to ensure every semicolon counts.
- **`creative` & `prose`**: Higher semantic tolerance (0.15) to embrace diverse perspectives.

### 🛡️ Hybrid Semantic Voting
Lexical overlap isn't enough. Quorum uses **high-dimensional embeddings** to cluster responses by *meaning*, not just words. With **Remote Fallbacks**, it automatically uses OpenAI Embeddings if local hardware is unavailable.

### 📈 Non-Linear Reputation Learning
Quorum learns which models are experts. **Premium models** (GPT-4/Claude-3.5) are penalized more heavily for confident failures but rewarded more for leading a correct consensus.

---

## 🛠️ Guided Installation

Getting started is now a seamless, interactive experience.

```bash
# Clone the repository
git clone https://github.com/magnetoid/Quorum.git
cd Quorum

# Run the guided installer
chmod +x install.sh
./install.sh
```

### The Setup Wizard includes:
1.  **Ollama Discovery**: Automatically finds and pulls local models.
2.  **Provider Picker**: Paste your API keys (OpenAI, Anthropic, etc.) and enable them instantly.
3.  **Council Configurator**: Auto-sorts your models into `Local`, `Cheap`, and `Premium` tiers.
4.  **Health Check**: Verifies connectivity and model readiness.

---

## 🔌 Enterprise Integration

### 🤖 MCP Server (Model Context Protocol)
Quorum is fully compatible with MCP, allowing you to use it as a tool directly within **Claude Desktop**, **Cursor**, or **Claude Code**.

### 🔗 OpenAI-Compatible API
Drop-in replacement for any OpenAI client. Simply point your `BASE_URL` to Quorum.
```bash
# Control your budget per-request with custom headers
curl http://localhost:8000/v1/chat/completions \
  -H "X-Quorum-Budget: 0.15" \
  -d '{"model": "quorum", "messages": [{"role": "user", "content": "How do I scale a Redis cluster?"}]}'
```

---

## 🔍 Why Quorum?

| Feature | Quorum | Single LLM |
| :--- | :--- | :--- |
| **Hallucination Detection** | ✅ **Active** (via Consensus) | ❌ **None** |
| **Vendor Neutrality** | ✅ **Multi-Provider** | ❌ **Locked-in** |
| **Reliability** | ✅ **Tiered Fallbacks** | ❌ **Single Point of Failure** |
| **Expertise** | ✅ **Reputation-Weighted** | ❌ **Generic** |
| **Speed/Cost** | ✅ **Speculative Short-circuit** | ❌ **Linear** |

---

## 🛣️ Roadmap: The Future of Decision Layers

We are evolving from a consensus engine into a complete **AI Decision Backbone**.

### 🟢 Phase 1: Foundation (Current)
- [x] Speculative Tiered Execution
- [x] Adaptive Domain Thresholds
- [x] Hybrid Semantic Clustering
- [x] Guided Interactive Installation

### 🟡 Phase 2: Intelligence (Next 3 Months)
- **Deliberation Round (Multi-Agent Debate)**: If a dispute is detected, models will critique each other's reasoning to reach a deeper truth.
- **Redis-Backed Semantic Cache**: Instant answers for semantically identical queries across your entire organization.
- **Prometheus & OpenTelemetry**: Enterprise-grade monitoring for latency, cost, and consensus drift.

### 🔴 Phase 3: Autonomous Governance (Next 6-12 Months)
- **Automatic Council Optimization**: The Router will dynamically reconfigure councils based on real-time model performance.
- **RAG Memory Layer**: Infuse councils with your private data before they vote.
- **Decentralized Councils**: Support for multi-node councils across different geographic regions.

---

## 🤝 Contributing

We are an open-source project and welcome all contributors! Whether it's fixing a bug, adding a new provider adapter, or improving documentation, your help is appreciated.

See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

---

## 📄 License
Quorum is released under the **Apache-2.0 License**.

<p align="center">
  <br>
  <b>"In a council of many, there is wisdom."</b>
</p>
