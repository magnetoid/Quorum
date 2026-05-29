import asyncio
import logging
import uuid
import time
import os
from typing import Any, Dict, List, Optional, Tuple

from config import AppConfig
from core.router import Router
from core.voting import VotingEngine
from adapters import build_adapter, provider_for_model
from adapters.base import AdapterResponse, BaseAdapter

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

    async def _ask_model(self, model: str, system: str, prompt: str) -> Tuple[str, AdapterResponse, float]:
        """Ask one model without letting provider failures crash the council."""
        start_time = time.perf_counter()
        try:
            adapter = self._get_adapter(model)
            res = await adapter.generate(model, system, prompt)
            latency = time.perf_counter() - start_time
            return model, res, latency
        except Exception as e:
            latency = time.perf_counter() - start_time
            logger.warning(
                "model %s failed before returning AdapterResponse: %s: %s",
                model,
                type(e).__name__,
                e,
            )
            return model, AdapterResponse(
                content="",
                error=f"Error from {model}: {type(e).__name__}: {e}",
            ), latency

    async def _ask_models(
        self,
        models: List[str],
        system_prompt: str,
        prompt: str,
    ) -> Dict[str, Tuple[AdapterResponse, float]]:
        if not models:
            return {}
        tasks = [self._ask_model(model, system_prompt, prompt) for model in models]
        results = await asyncio.gather(*tasks)
        return {model: (res, latency) for model, res, latency in results}

    @staticmethod
    def _voting_inputs(responses: Dict[str, AdapterResponse]) -> Dict[str, str]:
        """Pass both successful and failed models into voting.

        VotingEngine already knows how to mark empty/Error-prefixed responses as
        Error agents. Keeping failures in this dict prevents provider outages
        from disappearing from CLI/API output.
        """
        return {
            model: (res.error if res.error else res.content)
            for model, res in responses.items()
        }

    async def run(
        self,
        prompt: str,
        domain: str = "default",
        budget: float = 0.05,
        override_models: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        query_id = str(uuid.uuid4())

        if domain == "default":
            domain = self.router.classify_domain(prompt)

        system_prompt = self.config.personas.get(domain, self.config.personas.get("default", ""))

        total_cost = 0.0
        all_responses: Dict[str, AdapterResponse] = {}
        latencies: Dict[str, float] = {}

        if override_models:
            # Bypass tiering if models are explicitly requested.
            results = await self._ask_models(override_models, system_prompt, prompt)
            for model, (res, latency) in results.items():
                all_responses[model] = res
                latencies[model] = latency
                total_cost += res.cost
        else:
            # Tiered execution.
            tiers = ["local", "cheap", "premium"]
            domain_allowed_models = set(self.config.domains.get(domain, []))
            
            # Speculative execution: if a tier takes too long, start the next one.
            # Default staggered timeout is 2.5 seconds.
            stagger_timeout = float(os.getenv("QUORUM_TIER_STAGGER_SECONDS", "2.5"))

            running_tasks: List[asyncio.Task] = []
            
            for i, tier_name in enumerate(tiers):
                tier_config = self.config.tiers.get(tier_name)
                if not tier_config:
                    continue

                tier_models = [m for m in tier_config.models if m in domain_allowed_models]
                if not tier_models:
                    continue

                # Start this tier's models as a background task
                task = asyncio.create_task(self._ask_models(tier_models, system_prompt, prompt))
                running_tasks.append(task)

                # Wait for the current tier or others to finish, but speculate if it takes too long
                try:
                    await asyncio.wait(running_tasks, timeout=stagger_timeout, return_when=asyncio.FIRST_COMPLETED)
                except asyncio.TimeoutError:
                    pass

                # Harvest any completed tasks
                for t in running_tasks[:]:
                    if t.done():
                        tier_results = t.result()
                        for model, (res, latency) in tier_results.items():
                            if model not in all_responses:
                                all_responses[model] = res
                                latencies[model] = latency
                                total_cost += res.cost
                        running_tasks.remove(t)

                # Check consensus after every harvest
                if all_responses:
                    reputation_weights = await self.db.get_reputation(domain)
                    output = self.voting.aggregate(
                        self._voting_inputs(all_responses),
                        domain,
                        reputation_weights,
                    )

                    if output["confidence"] >= tier_config.confidence_threshold:
                        break

                if total_cost >= budget:
                    break
            
            # Final harvest of remaining tasks if we haven't reached consensus
            if running_tasks:
                results_list = await asyncio.gather(*running_tasks)
                for tier_results in results_list:
                    for model, (res, latency) in tier_results.items():
                        if model not in all_responses:
                            all_responses[model] = res
                            latencies[model] = latency
                            total_cost += res.cost

        # Final aggregation.
        reputation_weights = await self.db.get_reputation(domain)
        output = self.voting.aggregate(
            self._voting_inputs(all_responses),
            domain,
            reputation_weights,
        )

        # Add metadata.
        output["domain"] = domain
        output["query_id"] = query_id
        output["cost"] = f"${total_cost:.4f}"

        # Attach token + cost + latency telemetry.
        for agent in output.get("agents", []):
            model = agent["model"]
            resp = all_responses.get(model)
            if resp is not None:
                agent["input_tokens"] = resp.input_tokens
                agent["output_tokens"] = resp.output_tokens
                agent["cost"] = float(resp.cost)
                agent["latency"] = latencies.get(model, 0.0)
                if resp.error:
                    agent["response"] = resp.error
                    agent["vote"] = "Error"

        # Record tentative reputation deltas for the feedback loop.
        # Non-linear learning: premium models are weighted more heavily.
        if not output.get("disputed_flag"):
            deltas = []
            for agent in output.get("agents", []):
                vote = agent.get("vote", "")
                model = agent["model"]
                
                # Weight delta by tier: premium=2.0, cheap=1.0, local=0.5
                weight = 1.0
                premium_tier = self.config.tiers.get("premium")
                local_tier = self.config.tiers.get("local")
                if premium_tier and model in premium_tier.models:
                    weight = 2.0
                elif local_tier and model in local_tier.models:
                    weight = 0.5

                if vote in ("anchor", "consensus"):
                    deltas.append((model, domain, 1.0 * weight))
                elif vote == "dissent":
                    deltas.append((model, domain, -1.0 * weight))
            if deltas:
                try:
                    await self.db.save_pending_outcomes(query_id, deltas)
                except Exception as e:
                    logger.warning(
                        "save_pending_outcomes failed for query %s: %s: %s",
                        query_id,
                        type(e).__name__,
                        e,
                    )

        return output
