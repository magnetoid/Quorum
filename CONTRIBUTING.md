# Contributing to Quorum

Thanks for considering a contribution. Quorum is in early-stage development; rough edges are expected. The fastest way to land a change is to keep it small, testable, and aligned with the layout conventions below.

## Layout convention

Quorum uses **top-level packages, no namespace prefix**. Imports look like:

```python
from core.engine import Engine
from adapters.base import BaseAdapter
```

Not `from quorum.core.engine import Engine`. This is intentional — please don't refactor toward a `quorum/` namespace package without discussion.

## Adding a new adapter

The cheapest valuable contribution.

1. **For an OpenAI-compatible endpoint** (most new providers): just add an entry to `PROVIDERS` in [`adapters/__init__.py`](adapters/__init__.py) — no new file needed.

   ```python
   "myprovider": {
       "factory": "openai_compat",
       "model_prefix": "myprovider/",
       "api_key_env": "MYPROVIDER_API_KEY",
       "base_url": "https://api.myprovider.com/v1",
   },
   ```

2. **For a custom request/response shape** (Gemini, Cohere — anything non-OpenAI): create `adapters/<provider>.py` implementing `BaseAdapter.generate(model, system_prompt, prompt) -> AdapterResponse`. Use [`adapters/gemini.py`](adapters/gemini.py) or [`adapters/cohere.py`](adapters/cohere.py) as a template, then register in `PROVIDERS` with `factory: <provider>` and add a branch in `build_adapter()`.

3. Add the provider to [`config.yaml`](config.yaml) under `providers:` with `enabled: false` by default.

4. The parametrized smoke test in [`tests/test_adapters.py`](tests/test_adapters.py) will pick up the new provider automatically — no test changes needed.

## Running the tests

```bash
./.venv/bin/pytest -v
```

## Style

- Match the existing code. The codebase prefers small functions, explicit types, and avoids deep abstraction.
- Don't add dependencies without a clear reason.
- Write the smallest fix that addresses the issue. We can always expand later.

## Reporting issues

Open a GitHub issue with:

- Minimal repro
- What you expected
- What happened
- Output of `quorum doctor` (it captures Python version, Ollama state, configured providers, per-adapter ping — saves a round trip)

## Security

Please do not file public issues for security concerns. Email the maintainer directly (contact in `pyproject.toml`).
