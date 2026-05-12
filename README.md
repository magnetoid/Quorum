# Quorum

A consensus reasoning engine that orchestrates multiple LLMs in parallel, aggregates their answers through voting and critique, and surfaces both consensus and disagreement as structured output. Quorum learns over time which models perform best per domain.

## Install

```bash
cd ~/projects/quorum
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env  # then fill in keys
```

## Use

```bash
quorum ask "your question here"
quorum ask "question" --domain finance --budget 0.05
quorum ask "question" --models ollama/llama3.2,claude-sonnet
quorum serve  # REST + MCP
```

## Status

Foundation only — parallel execution via Ollama + Anthropic, basic voting, CLI `ask`. Storage, reputation, REST, MCP, and router land next per `Development Order` in the project spec.
