import asyncio
import logging
import uuid
from typing import List, Dict, Any, Tuple

from config import AppConfig
from core.router import Router
from core.voting import VotingEngine
from adapters import build_adapter, provider_for_model
from adapters.base import BaseAdapter, AdapterResponse

from storage.db import DB

logger = logging.getLogger(__name__)

class Engine:
    def __init__(self, config: AppConfig, db: DB):
        self.config = config
        self.db = db
        self.router = Router(config)
        self.voting = VotingEngine()
        # Adapters are built lazily on first use so importing the engine doesn't
        # require every provider's SDK / key to be present.
        self.adapters: Dict[str, BaseAdapter] = {}

    def _get_adapter(self, model: str) -> BaseAdapter:
        provider = provider_for_model(model) or "ollama"  # last-ditch fallback
        if provider not in self.adapters:
            self.adapters[provider] = build_adapter(provider, self.config)
        return self.adapters[provider]

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
        
        # Attach token + cost telemetry to each agent so downstream consumers
        # (router API, CLI rendering, MCP responses) can report usage.
        for agent in output.get("agents", []):
            model = agent["model"]
            resp = all_responses.get(model)
            if resp is not None:
                agent["input_tokens"] = resp.input_tokens
                agent["output_tokens"] = resp.output_tokens
                agent["cost"] = float(resp.cost)
                if resp.error:
                    agent["response"] = resp.error
                    agent["vote"] = "Error"

        # Record tentative reputation deltas for the feedback loop. Consensus
        # members tentatively +1, dissenters -1; minority/sole/Error votes
        # contribute 0. Confirmed (or flipped) by `quorum feedback`.
        deltas = []
        for agent in output.get("agents", []):
            vote = agent.get("vote", "")
            if vote in ("anchor", "consensus"):
                deltas.append((agent["model"], domain, 1.0))
            elif vote == "dissent":
                deltas.append((agent["model"], domain, -1.0))
        if deltas:
            try:
                await self.db.save_pending_outcomes(query_id, deltas)
            except Exception as e:
                # Never fail the user query if pending-outcome write fails,
                # but surface it so operators can see the loop is broken.
                logger.warning(
                    "save_pending_outcomes failed for query %s: %s: %s",
                    query_id, type(e).__name__, e,
                )

        return output
