"""Estimates the cost of an AI call from the versioned price table."""

from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.core.config import Settings

PRICING_FILE = Path(__file__).with_name("pricing.yaml")
MILLION = Decimal(1_000_000)

Rate = tuple[Decimal, Decimal]


@lru_cache
def _load(path: Path) -> dict[str, list[dict[str, Any]]]:
    data = yaml.safe_load(path.read_text()) or {}
    return {provider: list(entries or []) for provider, entries in data.items()}


class Pricing:
    def __init__(self, settings: Settings, path: Path = PRICING_FILE) -> None:
        self._table = _load(path)
        self._override: Rate | None = None
        if (
            settings.ai_price_input_per_mtok is not None
            and settings.ai_price_output_per_mtok is not None
        ):
            self._override = (
                Decimal(str(settings.ai_price_input_per_mtok)),
                Decimal(str(settings.ai_price_output_per_mtok)),
            )
        self._override_models = {settings.ai_model, settings.ai_fast_model} - {""}
        self._override_provider = settings.ai_provider

    def rate(self, provider: str, model: str) -> Rate | None:
        if (
            self._override is not None
            and provider == self._override_provider
            and model in self._override_models
        ):
            return self._override
        matches = [
            entry
            for entry in self._table.get(provider, [])
            if model.startswith(str(entry["prefix"]))
        ]
        if not matches:
            return None
        best = max(matches, key=lambda entry: len(str(entry["prefix"])))
        return Decimal(str(best["input"])), Decimal(str(best["output"]))

    def cost(
        self, provider: str, model: str, input_tokens: int, output_tokens: int
    ) -> Decimal | None:
        rate = self.rate(provider, model)
        if rate is None:
            return None
        total = (rate[0] * input_tokens + rate[1] * output_tokens) / MILLION
        return total.quantize(Decimal("0.000001"))
