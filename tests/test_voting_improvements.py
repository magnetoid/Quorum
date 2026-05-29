from core.voting import VotingEngine


def test_voting_numeric_disagreement_triggers_dispute():
    engine = VotingEngine()
    responses = {
        "m1": "The answer is 42.",
        "m2": "The answer is 43.",
    }
    result = engine.aggregate(responses, "factual")
    assert result["disputed_flag"]
    assert result["consensus"] == "Models disagreed."
    assert "42" in result["disputed"]
    assert "43" in result["disputed"]


def test_voting_negation_reduces_false_consensus():
    engine = VotingEngine()
    responses = {
        "m1": "The feature is safe.",
        "m2": "The feature is not safe.",
    }
    result = engine.aggregate(responses, "factual")
    assert result["disputed_flag"]
    assert result["consensus"] == "Models disagreed."


def test_voting_bridge_response_does_not_merge_clusters():
    engine = VotingEngine()
    responses = {
        "m1": "Use Kafka.",
        "m2": "Use SQS.",
        "m3": "Use Kafka or SQS depending on throughput.",
    }
    result = engine.aggregate(responses, "architecture")
    assert result["disputed_flag"]
    assert result["consensus"] == "Models disagreed."

