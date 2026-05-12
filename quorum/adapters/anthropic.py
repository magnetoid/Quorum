import httpx
import os
from .base import BaseAdapter

class AnthropicAdapter(BaseAdapter):
    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY")

    async def generate(self, model: str, system_prompt: str, prompt: str) -> str:
        if not self.api_key:
            return "Error: ANTHROPIC_API_KEY not set"
        
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
                return response.json().get("content", [{}])[0].get("text", "").strip()
            except Exception as e:
                return f"Error from Anthropic ({model}): {str(e)}"

    def get_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        # Simplified cost mapping, could be dynamic from config
        return (input_tokens * 0.003 + output_tokens * 0.015) / 1000
