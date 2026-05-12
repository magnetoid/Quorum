import asyncio
import httpx
import os
from typing import List, Dict, Any, Tuple
from collections import Counter
from quorum.config import AppConfig

class ConsensusEngine:
    def __init__(self, config: AppConfig):
        self.config = config
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    async def _ask_ollama(self, model: str, system: str, prompt: str) -> str:
        model_name = model.split("/", 1)[1] if "/" in model else model
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.ollama_base_url}/api/chat",
                    json={
                        "model": model_name,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": prompt}
                        ],
                        "stream": False
                    },
                    timeout=60.0
                )
                response.raise_for_status()
                return response.json().get("message", {}).get("content", "").strip()
            except Exception as e:
                return f"Error from Ollama ({model_name}): {str(e)}"

    async def _ask_anthropic(self, model: str, system: str, prompt: str) -> str:
        if not self.anthropic_api_key:
            return "Error: ANTHROPIC_API_KEY not set"
        
        # map claude-sonnet to full model names if needed
        model_map = {
            "claude-sonnet": "claude-3-5-sonnet-20241022",
            "claude-opus": "claude-3-opus-20240229",
            "claude-opus-4": "claude-3-opus-20240229" # fallback
        }
        actual_model = model_map.get(model, model)
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.anthropic_api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json"
                    },
                    json={
                        "model": actual_model,
                        "system": system,
                        "max_tokens": 1024,
                        "messages": [
                            {"role": "user", "content": prompt}
                        ]
                    },
                    timeout=60.0
                )
                response.raise_for_status()
                return response.json().get("content", [{}])[0].get("text", "").strip()
            except Exception as e:
                return f"Error from Anthropic ({model}): {str(e)}"

    async def _ask_openai(self, model: str, system: str, prompt: str) -> str:
        if not self.openai_api_key:
            return "Error: OPENAI_API_KEY not set"
            
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.openai_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": prompt}
                        ]
                    },
                    timeout=60.0
                )
                response.raise_for_status()
                return response.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            except Exception as e:
                return f"Error from OpenAI ({model}): {str(e)}"

    async def _ask_model(self, model: str, system: str, prompt: str) -> Tuple[str, str]:
        if model.startswith("ollama/"):
            res = await self._ask_ollama(model, system, prompt)
        elif "claude" in model:
            res = await self._ask_anthropic(model, system, prompt)
        elif "gpt" in model or "o3" in model:
            res = await self._ask_openai(model, system, prompt)
        else:
            # Fallback to ollama for unknown models
            res = await self._ask_ollama(model, system, prompt)
            
        return model, res

    async def ask_parallel(self, models: List[str], domain: str, prompt: str) -> Dict[str, Any]:
        system_prompt = self.config.personas.get(domain, self.config.personas.get("default", ""))
        
        tasks = [self._ask_model(model, system_prompt, prompt) for model in models]
        results = await asyncio.gather(*tasks)
        
        # Simple exact match consensus for demonstration
        answers = [res for model, res in results if not res.startswith("Error")]
        
        consensus = "No clear consensus"
        if answers:
            # Just taking the most common response as a basic consensus mechanic
            # In a real scenario, this would use an LLM to evaluate semantic similarity
            counter = Counter(answers)
            most_common, count = counter.most_common(1)[0]
            if count > len(answers) / 2:
                consensus = most_common
            else:
                # If no strict majority, we just summarize or pick the first
                consensus = "Disagreement among models. Example answer: " + answers[0]
                
        return {
            "responses": {model: res for model, res in results},
            "consensus": consensus
        }
