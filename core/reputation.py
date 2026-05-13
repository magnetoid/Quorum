from typing import Dict

from storage.db import DB


class ReputationManager:
    """Thin wrapper over DB for reputation reads/writes.

    The actual update-by-feedback flow is implemented in storage.db via
    `apply_feedback(query_id, score)`. This class exists so the engine and
    CLI can talk to reputation without coupling to SQLite directly."""

    def __init__(self, db: DB):
        self.db = db

    async def get_scores(self, domain: str) -> Dict[str, float]:
        return await self.db.get_reputation(domain)

    async def update_score(self, model: str, domain: str, score: float):
        await self.db.update_reputation(model, domain, score)

    async def apply_outcome(self, query_id: str, score: float) -> bool:
        """Confirm or flip the tentative reputation deltas for a past query."""
        return await self.db.apply_feedback(query_id, score)
