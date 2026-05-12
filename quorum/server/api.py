from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Any, Dict
from quorum.config import load_config
from quorum.core.engine import Engine
from quorum.storage.db import DB

app = FastAPI(title="Quorum API")
config = load_config()
engine = Engine(config)
db = DB()

class AskRequest(BaseModel):
    prompt: str
    domain: str = "default"
    budget: float = 0.05
    models: Optional[List[str]] = None

@app.on_event("startup")
async def startup_event():
    await db.init_db()

@app.post("/api/ask")
async def ask(req: AskRequest) -> Dict[str, Any]:
    try:
        result = await engine.run(
            prompt=req.prompt,
            domain=req.domain,
            budget=req.budget,
            override_models=req.models
        )
        # Save to history
        await db.save_history(
            query_id=result["query_id"],
            prompt=req.prompt,
            domain=result["domain"],
            consensus=result["consensus"],
            disputed_flag=result["disputed_flag"],
            cost=result["cost"]
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
