import asyncio
import uuid
from typing import List, Dict, Any, Tuple

from quorum.config import AppConfig
from quorum.core.router import Router
from quorum.core.voting import VotingEngine
from quorum.adapters.base import BaseAdapter
from quorum.adapters.ollama import OllamaAdapter
from quorum.adapters.anthropic import AnthropicAdapter
from quorum.adapters.openai import OpenAIAdapter
from quorum.adapters.openrouter import OpenRouterAdapter

class Engine:
    def __init__(self, config: AppConfig):
        self.config = config
        self.router = Router(config)
        self.voting = VotingEngine()
        
        # Initialize adapters
        self.adapters: Dict[str, BaseAdapter] = {
            "ollama": OllamaAdapter(),
            "anthropic": AnthropicAdapter(),
            "openai": OpenAIAdapter(),
            "openrouter": OpenRouterAdapter()
        }

    def _get_adapter(self, model: str) -> BaseAdapter:
        if model.startswith("ollama/"):
            return self.adapters["ollama"]
        if "claude" in model:
            return self.adapters["anthropic"]
        if "gpt" in model or "o3" in model:
            return self.adapters["openai"]
        if "gemini" in model or "mistral" in model:
            return self.adapters["openrouter"]
        return self.adapters["ollama"]  # Default fallback

    async def _ask_model(self, model: str, system: str, prompt: str) -> Tuple[str, str]:
        adapter = self._get_adapter(model)
        res = await adapter.generate(model, system, prompt)
        return model, res

    async def run(self, prompt: str, domain: str = "default", budget: float = 0.05, override_models: List[str] = None) -> Dict[str, Any]:
        query_id = str(uuid.uuid4())
        
        if domain == "default":
            domain = self.router.classify_domain(prompt)
            
        council = self.router.select_council(domain, budget, override_models)
        system_prompt = self.config.personas.get(domain, self.config.personas.get("default", ""))
        
        # Execute in parallel
        tasks = [self._ask_model(model, system_prompt, prompt) for model in council]
        results = await asyncio.gather(*tasks)
        
        responses = {model: res for model, res in results}
        
        # Aggregate
        output = self.voting.aggregate(responses, domain)
        
        # Add metadata
        output["domain"] = domain
        output["query_id"] = query_id
        output["cost"] = "$0.000"  # Placeholder, should calculate actual cost
        
        return output
