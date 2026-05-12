import aiosqlite
from typing import Dict, List, Any

class DB:
    def __init__(self, db_path: str = "quorum.db"):
        self.db_path = db_path

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS reputation (
                    model TEXT,
                    domain TEXT,
                    score REAL,
                    PRIMARY KEY (model, domain)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    query_id TEXT PRIMARY KEY,
                    prompt TEXT,
                    domain TEXT,
                    consensus TEXT,
                    disputed_flag BOOLEAN,
                    cost TEXT
                )
            """)
            await db.commit()

    async def get_reputation(self, domain: str) -> Dict[str, float]:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT model, score FROM reputation WHERE domain = ?", (domain,)) as cursor:
                return {row[0]: row[1] async for row in cursor}

    async def update_reputation(self, model: str, domain: str, score: float):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO reputation (model, domain, score)
                VALUES (?, ?, ?)
                ON CONFLICT(model, domain) DO UPDATE SET
                score = score + ?
            """, (model, domain, score, score))
            await db.commit()

    async def save_history(self, query_id: str, prompt: str, domain: str, consensus: str, disputed_flag: bool, cost: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO history (query_id, prompt, domain, consensus, disputed_flag, cost)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (query_id, prompt, domain, consensus, disputed_flag, cost))
            await db.commit()
