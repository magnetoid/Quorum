from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pydantic import BaseModel

class AdapterResponse(BaseModel):
    content: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    error: Optional[str] = None

class BaseAdapter(ABC):
    """Abstract adapter interface for LLM models."""
    
    @abstractmethod
    async def generate(self, model: str, system_prompt: str, prompt: str) -> AdapterResponse:
        """Generate response from the model."""
        pass
