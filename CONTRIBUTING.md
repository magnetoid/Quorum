# Contributing to Quorum 🏛️

Thank you for your interest in improving Quorum! We are building the world's most reliable AI decision layer, and we can't do it without you.

## 🚀 Ways to Contribute

### 1. Add a New Provider
Quorum is designed to be provider-agnostic. If your favorite LLM provider isn't supported yet:
- Create a new adapter in `adapters/`.
- Register the provider in `adapters/__init__.py`.
- Add a health check ping in `cli/doctor.py`.

### 2. Improve Consensus Algorithms
The core logic lives in `core/voting.py`. We are always looking for better ways to:
- Detect semantic negations.
- Cluster diverse paraphrases.
- Optimize the O(n²) similarity matrix for massive councils.

### 3. Build Integrations
Help us expand the **MCP** ecosystem or build plugins for:
- IDEs (VS Code, JetBrains).
- Messaging apps (Slack, Discord).
- Data pipelines (LangChain, LlamaIndex).

---

## 🛠️ Development Setup

1. **Install with Dev Extras**:
   ```bash
   pip install -e ".[dev,semantic]"
   ```
2. **Run Tests**:
   ```bash
   pytest
   ```
3. **Linting & Type Checking**:
   We use `ruff` and `mypy` to keep the codebase clean.
   ```bash
   ruff check .
   mypy .
   ```

---

## 🏛️ Code of Conduct
We are committed to fostering an open, welcoming, and safe environment. Please be respectful and professional in all interactions.

## 📄 License
By contributing, you agree that your contributions will be licensed under the project's **Apache-2.0 License**.
