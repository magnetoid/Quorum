import os
import yaml
from pathlib import Path
from pydantic import BaseModel
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Load environment variables centrally
load_dotenv()

class TierConfig(BaseModel):
    models: List[str]
    confidence_threshold: float

class BudgetConfig(BaseModel):
    default_per_query: float

class PricingConfig(BaseModel):
    input: float
    output: float

class AppConfig(BaseModel):
    tiers: Dict[str, TierConfig]
    budget: BudgetConfig
    domains: Dict[str, List[str]]
    personas: Dict[str, str]
    pricing: Dict[str, PricingConfig]

def load_config() -> AppConfig:
    config_path = Path("config.yaml")
    if not config_path.exists():
        # fallback to default or raise
        raise FileNotFoundError("config.yaml not found")
    
    with open(config_path, "r") as f:
        data = yaml.safe_load(f)
    
    return AppConfig(**data)
