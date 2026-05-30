import aiosqlite
from typing import Any, Dict, List, Tuple


class DB:
    def __init__(self, db_path: str = "quorum.db"):
        self.db_path = db_path

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA synchronous=NORMAL")
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
            await db.execute("""
                CREATE TABLE IF NOT EXISTS pending_outcomes (
                    query_id TEXT,
                    model TEXT,
                    domain TEXT,
                    delta REAL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_pending_query ON pending_outcomes(query_id)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_reputation_domain ON reputation(domain)"
            )
            await db.commit()

    async def get_reputation(self, domain: str) -> Dict[str, float]:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            async with db.execute(
                "SELECT model, score FROM reputation WHERE domain = ?", (domain,)
            ) as cursor:
                return {row[0]: row[1] async for row in cursor}

    async def update_reputation(self, model: str, domain: str, delta: float):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute(
                """
                INSERT INTO reputation (model, domain, score)
                VALUES (?, ?, ?)
                ON CONFLICT(model, domain) DO UPDATE SET score = score + ?
                """,
                (model, domain, delta, delta),
            )
            await db.commit()

    async def save_history(self, query_id: str, prompt: str, domain: str, consensus: str, disputed_flag: bool, cost: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute(
                """
                INSERT INTO history (query_id, prompt, domain, consensus, disputed_flag, cost)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (query_id, prompt, domain, consensus, disputed_flag, cost),
            )
            await db.commit()

    async def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            async with db.execute(
                "SELECT query_id, prompt, domain, consensus, disputed_flag, cost "
                "FROM history ORDER BY rowid DESC LIMIT ?",
                (limit,),
            ) as cursor:
                return [
                    {
                        "query_id": row[0],
                        "prompt": row[1],
                        "domain": row[2],
                        "consensus": row[3],
                        "disputed_flag": bool(row[4]),
                        "cost": row[5],
                    }
                    async for row in cursor
                ]

    async def save_pending_outcomes(
        self, query_id: str, deltas: List[Tuple[str, str, float]]
    ) -> None:
        if not deltas:
            return
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.executemany(
                "INSERT INTO pending_outcomes (query_id, model, domain, delta) VALUES (?, ?, ?, ?)",
                [(query_id, model, domain, delta) for model, domain, delta in deltas],
            )
            await db.commit()

    async def get_pending_outcomes(self, query_id: str) -> List[Tuple[str, str, float]]:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            async with db.execute(
                "SELECT model, domain, delta FROM pending_outcomes WHERE query_id = ?",
                (query_id,),
            ) as cursor:
                return [(row[0], row[1], row[2]) async for row in cursor]

    async def apply_feedback(self, query_id: str, score: float) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            async with db.execute(
                "SELECT model, domain, delta FROM pending_outcomes WHERE query_id = ?",
                (query_id,),
            ) as cursor:
                pending = [(row[0], row[1], row[2]) async for row in cursor]
            if not pending:
                return False
            if score != 0.0:
                for model, domain, delta in pending:
                    scaled = delta * score
                    await db.execute(
                        """
                        INSERT INTO reputation (model, domain, score)
                        VALUES (?, ?, ?)
                        ON CONFLICT(model, domain) DO UPDATE SET score = score + ?
                        """,
                        (model, domain, scaled, scaled),
                    )
            await db.execute(
                "DELETE FROM pending_outcomes WHERE query_id = ?", (query_id,)
            )
            await db.commit()
            return True
