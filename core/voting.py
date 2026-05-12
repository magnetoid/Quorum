from typing import List, Dict, Any, Tuple
from collections import defaultdict

class VotingEngine:
    def aggregate(self, responses: Dict[str, str], domain: str, reputation_weights: Dict[str, float] = None) -> Dict[str, Any]:
        """
        Aggregate responses, calculate confidence, detect disputes.
        Returns dict matching consensus output schema.
        """
        if not responses:
            return {
                "consensus": "No responses received",
                "confidence": 0.0,
                "disputed": "",
                "disputed_flag": False,
                "agents": []
            }

        reputation_weights = reputation_weights or {}
        agents = []
        answers = []
        vote_scores = defaultdict(float)
        
        for model, response in responses.items():
            # In a real implementation, we would extract the core claim or vote
            # Here we just use the raw response or first sentence as a proxy
            vote = response.split(".")[0] if response else ""
            
            weight = reputation_weights.get(model, 1.0)
            # Ensure base weight of 1.0, plus any reputation bonuses/penalties
            # Normalizing negative scores if any (for safety)
            weight = max(0.1, weight)
            
            agents.append({
                "model": model,
                "response": response,
                "vote": vote
            })
            if not response.startswith("Error"):
                answers.append(response)
                vote_scores[response] += weight

        if not answers:
            return {
                "consensus": "All models failed",
                "confidence": 0.0,
                "disputed": "",
                "disputed_flag": False,
                "agents": agents
            }

        # Weighted exact match consensus
        total_weight = sum(vote_scores.values())
        most_common_response = max(vote_scores.items(), key=lambda x: x[1])[0]
        max_score = vote_scores[most_common_response]
        
        confidence = max_score / total_weight if total_weight > 0 else 0.0
        disputed_flag = confidence < 0.66
        
        if disputed_flag:
            consensus = "Models disagreed."
            unique_answers = list(set(answers))
            disputed = "Disputed zone: " + " | ".join(unique_answers[:3])
        else:
            consensus = most_common_response
            disputed = ""

        return {
            "consensus": consensus,
            "confidence": confidence,
            "disputed": disputed,
            "disputed_flag": disputed_flag,
            "agents": agents
        }
