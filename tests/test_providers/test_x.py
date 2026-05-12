"""Tests for X (Twitter) API provider."""

from __future__ import annotations

from ai_usage.providers.x import XProvider


class TestXProvider:
    def test_no_credentials_returns_empty(self, mock_http, credentials):
        credentials.x_api_auth_token = ""
        provider = XProvider(credentials, mock_http)
        data = provider.fetch()
        assert data.balance is None

    def test_balance_success(self, mock_http, credentials):
        mock_http.get_json.side_effect = [
            {"credits": {"balance": "24.99"}},
            {"eventTypePricing": {}},
            {"usage": {}},
        ]
        provider = XProvider(credentials, mock_http)
        data = provider.fetch()
        assert data.balance == 24.99

    def test_spend_with_pricing(self, mock_http, credentials):
        mock_http.get_json.side_effect = [
            {"credits": {"balance": "50.00"}},
            {"eventTypePricing": {"Post": 0.01, "Like": 0.005}},
            {
                "usage": {
                    "app1": {
                        "groups": {
                            "Post": {"usage": 100},
                            "Like": {"usage": 200},
                        },
                    },
                },
            },
        ]
        provider = XProvider(credentials, mock_http)
        data = provider.fetch()
        assert data.balance == 50.00
        assert data.spent == 2.00  # 100*0.01 + 200*0.005 = 1.00 + 1.00

    def test_skips_total_group(self, mock_http, credentials):
        mock_http.get_json.side_effect = [
            {"credits": {"balance": "10.00"}},
            {"eventTypePricing": {"Post": 0.01}},
            {
                "usage": {
                    "_total": {"groups": {}},  # should be skipped
                    "app1": {"groups": {"Post": {"usage": 50}}},
                },
            },
        ]
        provider = XProvider(credentials, mock_http)
        data = provider.fetch()
        assert data.spent == 0.50

    def test_api_error_graceful(self, mock_http, credentials):
        mock_http.get_json.side_effect = Exception("API down")
        provider = XProvider(credentials, mock_http)
        data = provider.fetch()
        assert data.meta.get("balance_error") is True
