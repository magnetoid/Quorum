from typing import Dict
from storage.db import DB

class ReputationManager:
    def __init__(self, db: DB):
        self.db = db

    async def get_scores(self, domain: str) -> Dict[str, float]:
        """Get reputation scores for a domain."""
        return await self.db.get_reputation(domain)

    async def update_score(self, model: str, domain: str, score: float):
        """Update reputation score (feedback)."""
        await self.db.update_reputation(model, domain, score)
