import pytest
from core.voting import VotingEngine

def test_voting_engine_consensus():
    engine = VotingEngine()
    responses = {
        "model1": "The answer is 42.",
        "model2": "The answer is 42.",
        "model3": "I think it is 42."
    }
    
    result = engine.aggregate(responses, "factual")
    assert result["confidence"] > 0.6
    assert not result["disputed_flag"]
    assert "42" in result["consensus"]

def test_voting_engine_dispute():
    engine = VotingEngine()
    responses = {
        "model1": "The answer is 42.",
        "model2": "The answer is 43.",
        "model3": "I have no idea."
    }
    
    result = engine.aggregate(responses, "factual")
    assert result["confidence"] < 0.66
    assert result["disputed_flag"]
    assert "Models disagreed" in result["consensus"]
    assert "42" in result["disputed"]

def test_voting_engine_reputation_weights():
    engine = VotingEngine()
    responses = {
        "model1": "A",
        "model2": "B",
        "model3": "B"
    }
    # model1 has a massive reputation score
    weights = {"model1": 10.0, "model2": 1.0, "model3": 1.0}
    
    result = engine.aggregate(responses, "factual", weights)
    assert result["consensus"] == "A"
    assert not result["disputed_flag"]
