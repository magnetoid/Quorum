"""Tests for the OpenAI-compatible router endpoint.

Currently focuses on the model-spec parser (pure logic, no I/O). End-to-end
HTTP tests are deferred since they'd construct the full Engine + DB at
import time."""
from __future__ import annotations

import pytest

from server.api import _parse_model_spec


def test_parse_quorum_default():
    assert _parse_model_spec("quorum") == ("default", None)


def test_parse_quorum_empty_suffix():
    """`quorum:` with empty spec should fall back to default."""
    assert _parse_model_spec("quorum:") == ("default", None)


def test_parse_quorum_domain_only():
    assert _parse_model_spec("quorum:code") == ("code", None)


def test_parse_quorum_explicit_models():
    domain, models = _parse_model_spec("quorum:claude-sonnet,gpt-4o")
    assert domain == "default"
    assert models == ["claude-sonnet", "gpt-4o"]


def test_parse_quorum_provider_prefixed_models():
    domain, models = _parse_model_spec("quorum:ollama/llama3.2,groq/llama-3.3-70b")
    assert domain == "default"
    assert models == ["ollama/llama3.2", "groq/llama-3.3-70b"]


def test_parse_quorum_domain_and_models():
    domain, models = _parse_model_spec("quorum:code:claude-sonnet,gpt-4o")
    assert domain == "code"
    assert models == ["claude-sonnet", "gpt-4o"]


def test_parse_quorum_domain_and_single_model():
    domain, models = _parse_model_spec("quorum:legal:claude-opus")
    assert domain == "legal"
    assert models == ["claude-opus"]


def test_parse_single_model_passthrough():
    domain, models = _parse_model_spec("claude-sonnet")
    assert domain == "default"
    assert models == ["claude-sonnet"]


def test_parse_ollama_passthrough():
    domain, models = _parse_model_spec("ollama/llama3.2")
    assert domain == "default"
    assert models == ["ollama/llama3.2"]


def test_parse_strips_whitespace():
    domain, models = _parse_model_spec("quorum: claude-sonnet , gpt-4o ")
    assert models == ["claude-sonnet", "gpt-4o"]
