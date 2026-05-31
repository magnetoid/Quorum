from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()


class TierConfig(BaseModel):
    models: List[str]
    confidence_threshold: float


class BudgetConfig(BaseModel):
    default_per_query: float = 0.05


class PricingConfig(BaseModel):
    input: float
    output: float


class ProviderConfig(BaseModel):
    enabled: bool = False
    api_key_env: Optional[str] = None
    base_url: Optional[str] = None


class VotingConfig(BaseModel):
    cluster_threshold: float = 0.25
    dispute_confidence: float = 0.66
    # Selective prediction: if a result is still disputed AND its confidence is
    # below this threshold, the engine abstains ("insufficient consensus")
    # instead of returning a disagreement dump. 0.0 disables abstention (the
    # default). Override per-deployment or via QUORUM_ABSTAIN_CONFIDENCE.
    abstain_confidence: float = 0.0


class AppConfig(BaseModel):
    tiers: Dict[str, TierConfig] = Field(default_factory=dict)
    budget: BudgetConfig = Field(default_factory=BudgetConfig)
    domains: Dict[str, List[str]] = Field(default_factory=dict)
    personas: Dict[str, str] = Field(default_factory=dict)
    pricing: Dict[str, PricingConfig] = Field(default_factory=dict)
    providers: Dict[str, ProviderConfig] = Field(default_factory=dict)
    voting: VotingConfig = Field(default_factory=VotingConfig)
    default_council: List[str] = Field(default_factory=list)

    def enabled_providers(self) -> List[str]:
        return [name for name, p in self.providers.items() if p.enabled]

    def provider(self, name: str) -> Optional[ProviderConfig]:
        return self.providers.get(name)


def load_config() -> AppConfig:
    config_path = Path(os.environ.get("QUORUM_CONFIG", "config.yaml"))
    if not config_path.exists():
        raise FileNotFoundError(f"config.yaml not found at {config_path}")

    with open(config_path, "r") as f:
        data = yaml.safe_load(f) or {}

    return AppConfig(**data)
