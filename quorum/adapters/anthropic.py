import httpx
import os
from .base import BaseAdapter, AdapterResponse
from quorum.config import AppConfig

class AnthropicAdapter(BaseAdapter):
    def __init__(self, config: AppConfig):
        self.config = config
        self.api_key = os.getenv("ANTHROPIC_API_KEY")

    async def generate(self, model: str, system_prompt: str, prompt: str) -> AdapterResponse:
        if not self.api_key:
            return AdapterResponse(content="", error="Error: ANTHROPIC_API_KEY not set")
        
        # map shorthand to full model names
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
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json"
                    },
                    json={
                        "model": actual_model,
                        "system": system_prompt,
                        "max_tokens": 1024,
                        "messages": [
                            {"role": "user", "content": prompt}
                        ]
                    },
                    timeout=60.0
                )
                response.raise_for_status()
                data = response.json()
                content = data.get("content", [{}])[0].get("text", "").strip()
                usage = data.get("usage", {})
                input_tokens = usage.get("input_tokens", 0)
                output_tokens = usage.get("output_tokens", 0)
                
                pricing = self.config.pricing.get(model)
                cost = 0.0
                if pricing:
                    cost = (input_tokens * pricing.input + output_tokens * pricing.output) / 1000.0

                return AdapterResponse(
                    content=content,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost=cost
                )
            except Exception as e:
                return AdapterResponse(content="", error=f"Error from Anthropic ({model}): {str(e)}")
