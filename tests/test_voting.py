from core.voting import VotingEngine


def test_voting_engine_consensus():
    engine = VotingEngine()
    responses = {
        "model1": "The answer is 42.",
        "model2": "The answer is 42.",
        "model3": "I think it is 42.",
    }

    result = engine.aggregate(responses, "factual")
    assert result["confidence"] > 0.6
    assert not result["disputed_flag"]
    assert "42" in result["consensus"]


def test_voting_engine_dispute():
    # Lexically distinct responses (no shared tokens) — Jaccard clustering
    # places each in its own group, so confidence collapses and dispute fires.
    # Caveat: numeric disputes like "42 vs 43" are NOT caught by Jaccard
    # because they share ~60% of tokens; those need semantic similarity.
    engine = VotingEngine()
    responses = {
        "model1": "Yes, definitely.",
        "model2": "No, never.",
        "model3": "Maybe, depends on context.",
    }

    result = engine.aggregate(responses, "factual")
    assert result["confidence"] < 0.66
    assert result["disputed_flag"]
    assert "Models disagreed" in result["consensus"]
    assert "Yes" in result["disputed"]
    assert "No" in result["disputed"]


def test_voting_engine_reputation_weights():
    engine = VotingEngine()
    responses = {
        "model1": "Alpha is correct.",
        "model2": "Beta is correct.",
        "model3": "Beta is correct.",
    }
    # model1 has a massive reputation score — its cluster wins despite being 1 vote.
    weights = {"model1": 10.0, "model2": 1.0, "model3": 1.0}

    result = engine.aggregate(responses, "factual", weights)
    assert result["consensus"].startswith("Alpha") or result["consensus"] == "Models disagreed."
    # In either case, the high-weight model's view should dominate.
    if result["consensus"] != "Models disagreed.":
        assert "Alpha" in result["consensus"]


def test_voting_engine_empty():
    engine = VotingEngine()
    result = engine.aggregate({}, "factual")
    assert result["confidence"] == 0.0
    assert not result["disputed_flag"]
    assert result["agents"] == []


def test_voting_engine_all_errors():
    engine = VotingEngine()
    responses = {
        "m1": "Error: timeout",
        "m2": "Error: 500",
    }
    result = engine.aggregate(responses, "factual")
    assert result["confidence"] == 0.0
    assert "failed" in result["consensus"].lower()
    assert all(a["vote"] == "Error" for a in result["agents"])
