import httpx
import os
from .base import BaseAdapter, AdapterResponse
from config import AppConfig

class OpenAIAdapter(BaseAdapter):
    def __init__(self, config: AppConfig):
        self.config = config
        self.api_key = os.getenv("OPENAI_API_KEY")

    async def generate(self, model: str, system_prompt: str, prompt: str) -> AdapterResponse:
        if not self.api_key:
            return AdapterResponse(content="", error="Error: OPENAI_API_KEY not set")
            
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
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
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                usage = data.get("usage", {})
                input_tokens = usage.get("prompt_tokens", 0)
                output_tokens = usage.get("completion_tokens", 0)
                
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
                return AdapterResponse(content="", error=f"Error from OpenAI ({model}): {str(e)}")
