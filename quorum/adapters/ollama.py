import httpx
import os
from .base import BaseAdapter

class OllamaAdapter(BaseAdapter):
    def __init__(self):
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    async def generate(self, model: str, system_prompt: str, prompt: str) -> str:
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
                return response.json().get("message", {}).get("content", "").strip()
            except Exception as e:
                return f"Error from Ollama ({model_name}): {str(e)}"

    def get_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        return 0.0  # Local models are free
