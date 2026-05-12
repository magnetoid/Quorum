from typing import List, Dict, Any, Tuple
from collections import Counter

class VotingEngine:
    def aggregate(self, responses: Dict[str, str], domain: str) -> Dict[str, Any]:
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

        agents = []
        answers = []
        
        for model, response in responses.items():
            # In a real implementation, we would extract the core claim or vote
            # Here we just use the raw response or first sentence as a proxy
            vote = response.split(".")[0] if response else ""
            agents.append({
                "model": model,
                "response": response,
                "vote": vote
            })
            if not response.startswith("Error"):
                answers.append(response)

        if not answers:
            return {
                "consensus": "All models failed",
                "confidence": 0.0,
                "disputed": "",
                "disputed_flag": False,
                "agents": agents
            }

        # Simple exact match consensus for demonstration
        # In reality, this should use an LLM to evaluate semantic similarity
        counter = Counter(answers)
        most_common, count = counter.most_common(1)[0]
        
        confidence = count / len(answers)
        disputed_flag = confidence < 0.66
        
        if disputed_flag:
            consensus = "Models disagreed."
            disputed = "Disputed zone: " + " | ".join(set(answers[:3]))
        else:
            consensus = most_common
            disputed = ""

        return {
            "consensus": consensus,
            "confidence": confidence,
            "disputed": disputed,
            "disputed_flag": disputed_flag,
            "agents": agents
        }
