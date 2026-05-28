import asyncio
import logging
import uuid
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

    async def _ask_model(self, model: str, system: str, prompt: str) -> Tuple[str, AdapterResponse]:
        """Ask one model without letting provider failures crash the council."""
        try:
            adapter = self._get_adapter(model)
            res = await adapter.generate(model, system, prompt)
            return model, res
        except Exception as e:
            logger.warning(
                "model %s failed before returning AdapterResponse: %s: %s",
                model,
                type(e).__name__,
                e,
            )
            return model, AdapterResponse(
                content="",
                error=f"Error from {model}: {type(e).__name__}: {e}",
            )

    async def _ask_models(
        self,
        models: List[str],
        system_prompt: str,
        prompt: str,
    ) -> Dict[str, AdapterResponse]:
        if not models:
            return {}
        tasks = [self._ask_model(model, system_prompt, prompt) for model in models]
        results = await asyncio.gather(*tasks)
        return {model: res for model, res in results}

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

        if override_models:
            # Bypass tiering if models are explicitly requested.
            all_responses = await self._ask_models(override_models, system_prompt, prompt)
            total_cost = sum(res.cost for res in all_responses.values())
        else:
            # Tiered execution.
            tiers = ["local", "cheap", "premium"]
            domain_allowed_models = set(self.config.domains.get(domain, []))

            for tier_name in tiers:
                tier_config = self.config.tiers.get(tier_name)
                if not tier_config:
                    continue

                # Filter tier models to only those allowed in this domain.
                tier_models = [m for m in tier_config.models if m in domain_allowed_models]
                if not tier_models:
                    continue

                tier_responses = await self._ask_models(tier_models, system_prompt, prompt)

                for model, res in tier_responses.items():
                    all_responses[model] = res
                    total_cost += res.cost

                # Check consensus. Include failed models so outages stay visible
                # as Error agents in intermediate/final outputs.
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
        if not output.get("disputed_flag"):
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
                    logger.warning(
                        "save_pending_outcomes failed for query %s: %s: %s",
                        query_id,
                        type(e).__name__,
                        e,
                    )

        return output
