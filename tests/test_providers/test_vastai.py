"""Tests for Vast.ai provider."""

from __future__ import annotations

from ai_usage.providers.vastai import VastAIProvider


class TestVastAIProvider:
    def test_no_key_returns_empty(self, mock_http, credentials):
        credentials.vastai_api_key = ""
        provider = VastAIProvider(credentials, mock_http)
        data = provider.fetch()
        assert data.balance is None

    def test_balance_success(self, mock_http, credentials):
        mock_http.get_json.side_effect = [
            {"credit": 4.01},  # balance
            {"results": []},   # charges (empty)
        ]
        provider = VastAIProvider(credentials, mock_http)
        data = provider.fetch()
        assert data.balance == 4.01

    def test_spend_success(self, mock_http, credentials):
        mock_http.get_json.side_effect = [
            {"credit": 10.0},
            {"results": [{"amount": 5.0}, {"amount": 3.5}, {"amount": 1.0}]},
        ]
        provider = VastAIProvider(credentials, mock_http)
        data = provider.fetch()
        assert data.balance == 10.0
        assert data.spent == 9.5

    def test_balance_error_graceful(self, mock_http, credentials):
        mock_http.get_json.side_effect = [
            Exception("balance API down"),
            {"results": []},
        ]
        provider = VastAIProvider(credentials, mock_http)
        data = provider.fetch()
        assert data.meta.get("balance_error") is True
