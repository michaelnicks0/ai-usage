"""Data models for provider results."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TokenData:
    """Per-model token breakdown."""

    input: int = 0
    cached: int = 0
    output: int = 0

    @property
    def total(self) -> int:
        return self.input + self.cached + self.output

    @property
    def hit_pct(self) -> float:
        """Percentage of input tokens that were cache hits."""
        total_in = self.cached + self.input
        return round(self.cached / total_in * 100, 1) if total_in > 0 else 0.0

    @property
    def miss_pct(self) -> float:
        """Percentage of input tokens that were cache misses."""
        total_in = self.cached + self.input
        return round(self.input / total_in * 100, 1) if total_in > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        hit, miss = self.hit_pct, self.miss_pct
        return OrderedDict(
            tokens_in_hit=self.cached,
            tokens_in_hit_percentage=hit,
            tokens_in_miss=self.input,
            tokens_in_miss_percentage=miss,
            tokens_out=self.output,
            tokens_total=self.total,
        )


@dataclass
class ProviderData:
    """Normalized provider result."""

    balance: float | None = None
    spent: float | None = None
    tokens: TokenData = field(default_factory=TokenData)
    models: OrderedDict[str, TokenData] = field(default_factory=OrderedDict)
    extra: dict[str, Any] | None = None
    meta: dict[str, Any] = field(default_factory=dict)
