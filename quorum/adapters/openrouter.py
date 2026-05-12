import httpx
import os
from .base import BaseAdapter

class OpenRouterAdapter(BaseAdapter):
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")

    async def generate(self, model: str, system_prompt: str, prompt: str) -> str:
        if not self.api_key:
            return "Error: OPENROUTER_API_KEY not set"
            
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt}
                        ]
                    },
                    timeout=60.0
                )
                response.raise_for_status()
                return response.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            except Exception as e:
                return f"Error from OpenRouter ({model}): {str(e)}"

    def get_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        return 0.001  # Placeholder
