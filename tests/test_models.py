"""Tests for data models."""

from __future__ import annotations

import pytest

from ai_usage.models import ProviderData, TokenData


class TestTokenData:
    def test_defaults(self):
        td = TokenData()
        assert td.input == 0
        assert td.cached == 0
        assert td.output == 0
        assert td.total == 0

    def test_total(self):
        td = TokenData(input=100, cached=50, output=30)
        assert td.total == 180

    def test_hit_pct(self):
        td = TokenData(input=400, cached=600)
        assert td.hit_pct == 60.0

    def test_miss_pct(self):
        td = TokenData(input=400, cached=600)
        assert td.miss_pct == 40.0

    def test_hit_pct_zero_division(self):
        td = TokenData(input=0, cached=0)
        assert td.hit_pct == 0.0
        assert td.miss_pct == 0.0

    def test_to_dict(self):
        td = TokenData(input=400, cached=600, output=200)
        d = td.to_dict()
        assert d["tokens_in_hit"] == 600
        assert d["tokens_in_hit_percentage"] == 60.0
        assert d["tokens_in_miss"] == 400
        assert d["tokens_in_miss_percentage"] == 40.0
        assert d["tokens_out"] == 200
        assert d["tokens_total"] == 1200


class TestProviderData:
    def test_defaults(self):
        pd = ProviderData()
        assert pd.balance is None
        assert pd.spent is None
        assert isinstance(pd.tokens, TokenData)

    def test_with_values(self):
        td = TokenData(input=500, cached=300, output=100)
        pd = ProviderData(balance=25.0, spent=5.0, tokens=td)
        assert pd.balance == 25.0
        assert pd.spent == 5.0
        assert pd.tokens.total == 900
