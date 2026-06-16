"""Tests for OpenRouter provider."""

from __future__ import annotations

from ai_usage.providers.openrouter import OpenRouterProvider


class TestOpenRouterProvider:
    def test_no_key_returns_empty(self, mock_http, credentials):
        credentials.openrouter_api_key = ""
        provider = OpenRouterProvider(credentials, mock_http)
        data = provider.fetch()
        assert data.balance is None
        assert data.spent is None

    def test_balance_and_monthly_usage_success(self, mock_http, credentials):
        mock_http.get_json.side_effect = [
            {"data": {"total_credits": 60, "total_usage": 4.798257769}},
            {"data": {"usage_monthly": 0.722571, "usage": 0.9}},
        ]
        provider = OpenRouterProvider(credentials, mock_http)
        data = provider.fetch()
        assert data.balance == 55.201742231
        assert data.spent == 0.722571
        assert data.extra is not None
        assert data.extra["total_credits"] == 60.0
        assert data.extra["total_usage"] == 4.798257769
        assert data.extra["key_usage"] == 0.9

    def test_balance_error_still_fetches_usage(self, mock_http, credentials):
        mock_http.get_json.side_effect = [
            Exception("credits API down"),
            {"data": {"usage_monthly": 1.25}},
        ]
        provider = OpenRouterProvider(credentials, mock_http)
        data = provider.fetch()
        assert data.balance is None
        assert data.spent == 1.25
        assert data.meta.get("balance_error") is True

    def test_usage_error_keeps_balance(self, mock_http, credentials):
        mock_http.get_json.side_effect = [
            {"data": {"total_credits": 10, "total_usage": 2.5}},
            Exception("key API down"),
        ]
        provider = OpenRouterProvider(credentials, mock_http)
        data = provider.fetch()
        assert data.balance == 7.5
        assert data.spent is None
        assert data.meta.get("usage_error") is True
