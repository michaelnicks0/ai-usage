"""Tests for Exa provider."""

from __future__ import annotations

from ai_usage.providers.exa import ExaProvider


class TestExaProvider:
    def test_no_credentials_returns_empty(self, mock_http, credentials):
        credentials.exa_service_key = ""
        credentials.exa_session_token = ""
        provider = ExaProvider(credentials, mock_http)
        data = provider.fetch()
        assert data.balance is None

    def test_balance_via_session(self, mock_http, credentials):
        mock_http.get_json.return_value = {"orbCreditsInCents": 500}
        provider = ExaProvider(credentials, mock_http)
        data = provider.fetch()
        assert data.balance == 5.00

    def test_spend_via_service_key(self, mock_http, credentials):
        mock_http.get_json.side_effect = [
            {"orbCreditsInCents": 1000},  # balance
            {"apiKeys": [{"id": "key-123"}]},  # key discovery
            {"total_cost_usd": 3.50},  # usage
        ]
        provider = ExaProvider(credentials, mock_http)
        data = provider.fetch()
        assert data.balance == 10.00
        assert data.spent == 3.50

    def test_key_discovery_failure(self, mock_http, credentials):
        mock_http.get_json.side_effect = [
            {"orbCreditsInCents": 500},
            Exception("key discovery failed"),
        ]
        provider = ExaProvider(credentials, mock_http)
        data = provider.fetch()
        assert data.balance == 5.00  # balance still works
        assert data.spent is None     # spend failed gracefully
