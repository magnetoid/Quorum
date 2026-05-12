from typing import List
from quorum.config import AppConfig

class Router:
    def __init__(self, config: AppConfig):
        self.config = config

    def classify_domain(self, prompt: str) -> str:
        # Placeholder for actual classification logic
        prompt_lower = prompt.lower()
        if any(w in prompt_lower for w in ["def ", "class ", "code", "function", "bug", "python"]):
            return "code"
        if any(w in prompt_lower for w in ["stock", "finance", "price", "budget", "market"]):
            return "finance"
        if any(w in prompt_lower for w in ["law", "legal", "court", "sue", "attorney"]):
            return "legal"
        if any(w in prompt_lower for w in ["system", "architecture", "design", "scale"]):
            return "architecture"
        if any(w in prompt_lower for w in ["write", "story", "creative", "poem", "imagine"]):
            return "creative"
        return "factual"

    def select_council(self, domain: str, budget: float, override_models: List[str] = None) -> List[str]:
        if override_models:
            return override_models
            
        # Select models for domain based on budget
        domain_models = self.config.domains.get(domain, self.config.domains.get("factual", []))
        
        # Simple tiering logic based on budget
        if budget < 0.01:
            # Use local models only
            return [m for m in domain_models if "ollama" in m]
        
        return domain_models
