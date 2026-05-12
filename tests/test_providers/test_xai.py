"""Tests for xAI provider."""

from __future__ import annotations

from ai_usage.providers.xai import XAIProvider


class TestXAIProvider:
    def test_no_credentials_returns_empty(self, mock_http, credentials):
        credentials.xai_management_key = ""
        provider = XAIProvider(credentials, mock_http)
        data = provider.fetch()
        assert data.balance is None
        assert data.tokens.total == 0

    def test_balance_success(self, mock_http, credentials):
        mock_http.get_json.side_effect = [
            {"total": {"val": "2500"}},  # balance: 2500/100 = 25.00
            {"coreInvoice": {"lines": [], "totalWithCorr": {"val": "0"}}},
        ]
        provider = XAIProvider(credentials, mock_http)
        data = provider.fetch()
        assert data.balance == 25.0

    def test_balance_negative_becomes_positive(self, mock_http, credentials):
        mock_http.get_json.side_effect = [
            {"total": {"val": "-500"}},  # abs(-500)/100 = 5.00
            {"coreInvoice": {"lines": [], "totalWithCorr": {"val": "0"}}},
        ]
        provider = XAIProvider(credentials, mock_http)
        data = provider.fetch()
        assert data.balance == 5.0

    def test_token_and_spend(self, mock_http, credentials):
        mock_http.get_json.side_effect = [
            {"total": {"val": "10000"}},
            {
                "coreInvoice": {
                    "lines": [
                        {"description": "grok", "unitType": "Cached prompt text tokens", "numUnits": "500000"},
                        {"description": "grok", "unitType": "Prompt text tokens", "numUnits": "200000"},
                        {"description": "grok", "unitType": "Completion text tokens", "numUnits": "100000"},
                    ],
                    "totalWithCorr": {"val": "150"},
                },
            },
        ]
        provider = XAIProvider(credentials, mock_http)
        data = provider.fetch()
        assert data.balance == 100.0
        assert data.tokens.cached == 500000
        assert data.tokens.input == 200000
        assert data.tokens.output == 100000
        assert data.spent == 1.50

    def test_api_error_graceful(self, mock_http, credentials):
        mock_http.get_json.side_effect = Exception("API down")
        provider = XAIProvider(credentials, mock_http)
        data = provider.fetch()
        assert data.meta.get("balance_error") is True
