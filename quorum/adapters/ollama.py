import httpx
import os
from .base import BaseAdapter, AdapterResponse
from quorum.config import AppConfig

class OllamaAdapter(BaseAdapter):
    def __init__(self, config: AppConfig):
        self.config = config
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    async def generate(self, model: str, system_prompt: str, prompt: str) -> AdapterResponse:
        model_name = model.split("/", 1)[1] if "/" in model else model
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": model_name,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt}
                        ],
                        "stream": False
                    },
                    timeout=60.0
                )
                response.raise_for_status()
                data = response.json()
                content = data.get("message", {}).get("content", "").strip()
                input_tokens = data.get("prompt_eval_count", 0)
                output_tokens = data.get("eval_count", 0)
                return AdapterResponse(
                    content=content,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost=0.0
                )
            except Exception as e:
                return AdapterResponse(content="", error=f"Error from Ollama ({model_name}): {str(e)}")
