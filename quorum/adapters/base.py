from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class BaseAdapter(ABC):
    """Abstract adapter interface for LLM models."""
    
    @abstractmethod
    async def generate(self, model: str, system_prompt: str, prompt: str) -> str:
        """Generate response from the model."""
        pass
        
    @abstractmethod
    def get_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost for the query."""
        pass
