import asyncio
import logging
import uuid
import time
import os
from typing import Any, Dict, List, Optional, Tuple, AsyncGenerator

from config import AppConfig
from core.router import Router
from core.voting import VotingEngine, get_semantic_embeddings
from adapters import build_adapter, provider_for_model
from adapters.base import AdapterResponse, BaseAdapter

from storage.db import DB
from storage.cache import SemanticCache
from observability import metrics

logger = logging.getLogger(__name__)


class Engine:
    def __init__(self, config: AppConfig, db: DB):
        self.config = config
        self.db = db
        self.router = Router(config)
        self.voting = VotingEngine()
        self.cache = SemanticCache()
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
        provider = provider_for_model(model) or "unknown"
        metrics.PROVIDER_REQUESTS.labels(provider=provider).inc()
        try:
            adapter = self._get_adapter(model)
            res = await adapter.generate(model, system, prompt)
            latency = time.perf_counter() - start_time
            metrics.PROVIDER_LATENCY.labels(provider=provider).observe(latency)
            metrics.TOKENS_INPUT_TOTAL.labels(provider=provider).inc(res.input_tokens)
            metrics.TOKENS_OUTPUT_TOTAL.labels(provider=provider).inc(res.output_tokens)
            metrics.COST_USD_TOTAL.labels(provider=provider).inc(float(res.cost))
            return model, res, latency
        except Exception as e:
            latency = time.perf_counter() - start_time
            metrics.PROVIDER_FAILURES.labels(provider=provider).inc()
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

    async def _deliberate(
        self,
        prompt: str,
        domain: str,
        system_prompt: str,
        previous_output: Dict[str, Any],
        all_responses: Dict[str, AdapterResponse],
        latencies: Dict[str, float],
    ) -> Tuple[Dict[str, Any], float]:
        """Perform a second round where models critique the dissenting opinions."""
        models_to_reask = [agent["model"] for agent in previous_output["agents"] if agent["vote"] != "Error"]
        if not models_to_reask:
            return previous_output, 0.0

        # Construct the deliberation prompt
        disputed_summary = previous_output.get("disputed", "No dissent summary available.")
        delib_prompt = (
            f"Original Question: {prompt}\n\n"
            f"The council disagreed. Here are the dissenting viewpoints:\n"
            f"{disputed_summary}\n\n"
            f"Please review the other models' responses. If you see a more accurate path, "
            f"update your answer. If you stand by your original response, restate it briefly. "
            f"Finalize your best answer now."
        )

        delib_results = await self._ask_models(models_to_reask, system_prompt, delib_prompt)
        
        delib_cost = 0.0
        for model, (res, latency) in delib_results.items():
            # Update the main response pool with the new "deliberated" answers
            all_responses[model] = res
            latencies[model] = latency
            delib_cost += res.cost

        # Re-aggregate
        reputation_weights = await self.db.get_reputation(domain)
        new_output = self.voting.aggregate(
            self._voting_inputs(all_responses),
            domain,
            reputation_weights,
        )
        new_output["similarity_method"] += "+deliberation"
        
        return new_output, delib_cost

    async def _execute_tiers(
        self,
        prompt: str,
        domain: str,
        system_prompt: str,
        budget: float,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute model tiers and yield intermediate consensus results."""
        total_cost = 0.0
        all_responses: Dict[str, AdapterResponse] = {}
        latencies: Dict[str, float] = {}

        tiers = ["local", "cheap", "premium"]
        domain_allowed_models = set(self.config.domains.get(domain, []))
        stagger_timeout = float(os.getenv("QUORUM_TIER_STAGGER_SECONDS", "2.5"))
        running_tasks: List[asyncio.Task] = []

        for tier_name in tiers:
            tier_config = self.config.tiers.get(tier_name)
            if not tier_config:
                continue

            tier_models = [m for m in tier_config.models if m in domain_allowed_models]
            if not tier_models:
                continue

            task = asyncio.create_task(self._ask_models(tier_models, system_prompt, prompt))
            running_tasks.append(task)

            try:
                await asyncio.wait(running_tasks, timeout=stagger_timeout, return_when=asyncio.FIRST_COMPLETED)
            except asyncio.TimeoutError:
                pass

            # Harvest completed tasks
            for t in running_tasks[:]:
                if t.done():
                    tier_results = t.result()
                    for model, (res, latency) in tier_results.items():
                        if model not in all_responses:
                            all_responses[model] = res
                            latencies[model] = latency
                            total_cost += res.cost
                    running_tasks.remove(t)

            if all_responses:
                reputation_weights = await self.db.get_reputation(domain)
                output = self.voting.aggregate(
                    self._voting_inputs(all_responses),
                    domain,
                    reputation_weights,
                )
                output["all_responses"] = all_responses
                output["latencies"] = latencies
                output["total_cost"] = total_cost
                yield output

                if output["confidence"] >= tier_config.confidence_threshold:
                    break

            if total_cost >= budget:
                break
        
        # Final harvest
        if running_tasks:
            results_list = await asyncio.gather(*running_tasks)
            for tier_results in results_list:
                for model, (res, latency) in tier_results.items():
                    if model not in all_responses:
                        all_responses[model] = res
                        latencies[model] = latency
                        total_cost += res.cost
            
            reputation_weights = await self.db.get_reputation(domain)
            output = self.voting.aggregate(
                self._voting_inputs(all_responses),
                domain,
                reputation_weights,
            )
            output["all_responses"] = all_responses
            output["latencies"] = latencies
            output["total_cost"] = total_cost
            yield output

    async def run(
        self,
        prompt: str,
        domain: str = "default",
        budget: float = 0.05,
        override_models: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        start_time = time.perf_counter()
        query_id = str(uuid.uuid4())

        if domain == "default":
            domain = self.router.classify_domain(prompt)

        metrics.REQUESTS_TOTAL.labels(domain=domain).inc()
        metrics.ACTIVE_REQUESTS.inc()

        try:
            # ⚡ Cache Check
            embeddings = get_semantic_embeddings([prompt])
            prompt_vector = embeddings[0] if embeddings else []
            cached_result = self.cache.get(prompt, domain, prompt_vector)
            if cached_result:
                metrics.CACHE_HITS_TOTAL.inc()
                cached_result["query_id"] = query_id
                return cached_result

            metrics.CACHE_MISSES_TOTAL.inc()

            system_prompt = self.config.personas.get(domain, self.config.personas.get("default", ""))

            total_cost = 0.0
            all_responses: Dict[str, AdapterResponse] = {}
            latencies: Dict[str, float] = {}
            output: Dict[str, Any] = {}

            if override_models:
                # Bypass tiering if models are explicitly requested.
                results = await self._ask_models(override_models, system_prompt, prompt)
                for model, (res, latency) in results.items():
                    all_responses[model] = res
                    latencies[model] = latency
                    total_cost += res.cost

                reputation_weights = await self.db.get_reputation(domain)
                output = self.voting.aggregate(
                    self._voting_inputs(all_responses),
                    domain,
                    reputation_weights,
                )
            else:
                # Consume tiered execution generator
                async for intermediate_output in self._execute_tiers(prompt, domain, system_prompt, budget):
                    output = intermediate_output

                all_responses = output.pop("all_responses", {})
                latencies = output.pop("latencies", {})
                total_cost = output.pop("total_cost", 0.0)

            # 🧠 Deliberation Round: If disputed, ask models to critique each other.
            if output.get("disputed_flag") and os.getenv("QUORUM_DELIBERATION", "on") == "on":
                deliberation_budget = budget * 0.5
                if total_cost < deliberation_budget:
                    logger.info("Dispute detected. Triggering deliberation round for query %s", query_id)
                    delib_output, delib_cost = await self._deliberate(
                        prompt=prompt,
                        domain=domain,
                        system_prompt=system_prompt,
                        previous_output=output,
                        all_responses=all_responses,
                        latencies=latencies,
                    )
                    output = delib_output
                    total_cost += delib_cost

            metrics.CONSENSUS_CONFIDENCE.observe(output.get("confidence", 0.0))

        finally:
            metrics.ACTIVE_REQUESTS.dec()
            duration = time.perf_counter() - start_time
            metrics.REQUEST_DURATION.labels(domain=domain).observe(duration)

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
        if output.get("disputed_flag"):
            metrics.DISPUTED_TOTAL.labels(domain=domain).inc()
        else:
            # ⚡ Store in cache
            self.cache.set(prompt, domain, prompt_vector, output)
            
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

    async def run_stream(
        self,
        prompt: str,
        domain: str = "default",
        budget: float = 0.05,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream intermediate consensus results."""
        if domain == "default":
            domain = self.router.classify_domain(prompt)

        system_prompt = self.config.personas.get(domain, self.config.personas.get("default", ""))

        async for output in self._execute_tiers(prompt, domain, system_prompt, budget):
            # Clean up internal fields for streaming
            output.pop("all_responses", None)
            output.pop("latencies", None)
            output.pop("total_cost", None)
            output["domain"] = domain
            yield output
