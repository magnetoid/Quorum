import asyncio
import uuid
from typing import List, Dict, Any, Tuple

from config import AppConfig
from core.router import Router
from core.voting import VotingEngine
from adapters.base import BaseAdapter
from adapters.ollama import OllamaAdapter
from adapters.anthropic import AnthropicAdapter
from adapters.openai import OpenAIAdapter
from adapters.openrouter import OpenRouterAdapter
from adapters.base import BaseAdapter, AdapterResponse

from storage.db import DB

class Engine:
    def __init__(self, config: AppConfig, db: DB):
        self.config = config
        self.db = db
        self.router = Router(config)
        self.voting = VotingEngine()
        
        # Initialize adapters
        self.adapters: Dict[str, BaseAdapter] = {
            "ollama": OllamaAdapter(config),
            "anthropic": AnthropicAdapter(config),
            "openai": OpenAIAdapter(config),
            "openrouter": OpenRouterAdapter(config)
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

    async def _ask_model(self, model: str, system: str, prompt: str) -> Tuple[str, AdapterResponse]:
        adapter = self._get_adapter(model)
        res = await adapter.generate(model, system, prompt)
        return model, res

    async def run(self, prompt: str, domain: str = "default", budget: float = 0.05, override_models: List[str] = None) -> Dict[str, Any]:
        query_id = str(uuid.uuid4())
        
        if domain == "default":
            domain = self.router.classify_domain(prompt)
            
        system_prompt = self.config.personas.get(domain, self.config.personas.get("default", ""))
        
        total_cost = 0.0
        all_responses: Dict[str, AdapterResponse] = {}
        
        if override_models:
            # Bypass tiering if models are explicitly requested
            tasks = [self._ask_model(model, system_prompt, prompt) for model in override_models]
            results = await asyncio.gather(*tasks)
            all_responses = {model: res for model, res in results}
            total_cost = sum(res.cost for res in all_responses.values())
        else:
            # Tiered execution
            tiers = ["local", "cheap", "premium"]
            domain_allowed_models = set(self.config.domains.get(domain, []))
            
            for tier_name in tiers:
                tier_config = self.config.tiers.get(tier_name)
                if not tier_config:
                    continue
                    
                # Filter tier models to only those allowed in this domain
                tier_models = [m for m in tier_config.models if m in domain_allowed_models]
                if not tier_models:
                    continue
                    
                tasks = [self._ask_model(model, system_prompt, prompt) for model in tier_models]
                results = await asyncio.gather(*tasks)
                
                for model, res in results:
                    all_responses[model] = res
                    total_cost += res.cost
                
                # Check consensus
                # Voting engine expects dict of string responses
                reputation_weights = await self.db.get_reputation(domain)
                str_responses = {m: r.content for m, r in all_responses.items() if not r.error}
                output = self.voting.aggregate(str_responses, domain, reputation_weights)
                
                if output["confidence"] >= tier_config.confidence_threshold:
                    break
                    
                if total_cost >= budget:
                    break
        
        # Final aggregation
        reputation_weights = await self.db.get_reputation(domain)
        str_responses = {m: r.content for m, r in all_responses.items() if not r.error}
        output = self.voting.aggregate(str_responses, domain, reputation_weights)
        
        # Add metadata
        output["domain"] = domain
        output["query_id"] = query_id
        output["cost"] = f"${total_cost:.4f}"
        
        # Add errors to agents metadata if any
        for agent in output.get("agents", []):
            model = agent["model"]
            if all_responses.get(model) and all_responses[model].error:
                agent["response"] = all_responses[model].error
                agent["vote"] = "Error"
        
        return output
