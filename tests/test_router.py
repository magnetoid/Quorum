"""Tests for the domain classifier's word-boundary matching.

Word boundaries prevent the false positive where 'encode' or 'scope' or
'decoder' would route to the `code` domain."""
from __future__ import annotations

import pytest

from config import AppConfig
from core.router import Router


@pytest.fixture
def router():
    return Router(AppConfig())


def test_explicit_code_keyword(router):
    assert router.classify_domain("Help me debug this Python code") == "code"


def test_word_boundary_blocks_encode(router):
    """'encode' should NOT trigger the code domain — that was the placeholder bug."""
    assert router.classify_domain("How does base64 encode work?") != "code"


def test_word_boundary_blocks_decode(router):
    assert router.classify_domain("Decode this base64 string") != "code"


def test_word_boundary_blocks_scope(router):
    assert router.classify_domain("What's the scope of this project?") != "code"


def test_finance_keyword(router):
    assert router.classify_domain("What's the AAPL stock price today?") == "finance"


def test_legal_keyword(router):
    assert router.classify_domain("Is this contract enforceable in California?") == "legal"


def test_architecture_keyword(router):
    assert router.classify_domain("Should we use microservices or a monolith?") == "architecture"


def test_creative_keyword(router):
    assert router.classify_domain("Write a poem about the ocean") == "creative"


def test_default_to_factual(router):
    assert router.classify_domain("What is the capital of France?") == "factual"


def test_case_insensitive(router):
    assert router.classify_domain("CODE review please") == "code"
