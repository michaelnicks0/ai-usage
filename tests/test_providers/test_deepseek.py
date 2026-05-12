"""Tests for DeepSeek provider."""

from __future__ import annotations

from ai_usage.providers.deepseek import DeepSeekProvider


class TestDeepSeekProvider:
    def test_no_credentials_returns_empty(self, mock_http, credentials):
        credentials.deepseek_api_key = ""
        credentials.deepseek_auth_token = ""
        provider = DeepSeekProvider(credentials, mock_http)
        data = provider.fetch()
        assert data.balance is None
        assert data.spent is None
        assert data.tokens.total == 0

    def test_balance_success(self, mock_http, credentials):
        mock_http.get_json.return_value = {
            "balance_infos": [{"currency": "USD", "total_balance": "12.50"}],
        }
        provider = DeepSeekProvider(credentials, mock_http)
        data = provider.fetch()
        assert data.balance == 12.50

    def test_balance_api_error_graceful(self, mock_http, credentials):
        mock_http.get_json.side_effect = Exception("API down")
        provider = DeepSeekProvider(credentials, mock_http)
        data = provider.fetch()
        assert data.balance is None
        assert data.meta.get("balance_error") is True

    def test_token_usage_success(self, mock_http, credentials):
        mock_http.get_json.side_effect = [
            # Balance call
            {"balance_infos": [{"currency": "USD", "total_balance": "50.00"}]},
            # Usage call
            {
                "data": {
                    "biz_data": {
                        "total": [{
                            "model": "deepseek-chat",
                            "usage": [
                                {"type": "PROMPT_CACHE_HIT_TOKEN", "amount": "1000000"},
                                {"type": "PROMPT_CACHE_MISS_TOKEN", "amount": "500000"},
                                {"type": "RESPONSE_TOKEN", "amount": "200000"},
                            ],
                        }],
                    },
                },
            },
        ]
        provider = DeepSeekProvider(credentials, mock_http)
        data = provider.fetch()
        assert data.balance == 50.00
        assert data.tokens.cached == 1000000
        assert data.tokens.input == 500000
        assert data.tokens.output == 200000
        # Spend = cached/1M * 0.003625 + input/1M * 0.435 + output/1M * 0.87
        expected_spend = (1.0 * 0.003625) + (0.5 * 0.435) + (0.2 * 0.87)
        assert abs(data.spent - expected_spend) < 0.001

    def test_usage_error_graceful(self, mock_http, credentials):
        def side_effect(url, headers=None, timeout=None):
            if "balance" in url:
                return {"balance_infos": [{"currency": "USD", "total_balance": "10.00"}]}
            raise Exception("Usage API down")
        mock_http.get_json.side_effect = side_effect
        provider = DeepSeekProvider(credentials, mock_http)
        data = provider.fetch()
        assert data.balance == 10.00
        assert data.meta.get("usage_error") is True

    def test_models_parsed(self, mock_http, credentials):
        mock_http.get_json.side_effect = [
            {"balance_infos": []},
            {
                "data": {
                    "biz_data": {
                        "total": [
                            {
                                "model": "deepseek-chat",
                                "usage": [
                                    {"type": "PROMPT_CACHE_HIT_TOKEN", "amount": "1000"},
                                    {"type": "PROMPT_CACHE_MISS_TOKEN", "amount": "500"},
                                    {"type": "RESPONSE_TOKEN", "amount": "300"},
                                ],
                            },
                            {
                                "model": "deepseek-reasoner",
                                "usage": [
                                    {"type": "PROMPT_CACHE_HIT_TOKEN", "amount": "200"},
                                    {"type": "PROMPT_CACHE_MISS_TOKEN", "amount": "100"},
                                    {"type": "RESPONSE_TOKEN", "amount": "50"},
                                ],
                            },
                        ],
                    },
                },
            },
        ]
        provider = DeepSeekProvider(credentials, mock_http)
        data = provider.fetch()
        assert len(data.models) == 2
        assert "deepseek-chat" in data.models
        assert data.models["deepseek-chat"].cached == 1000
        assert data.models["deepseek-reasoner"].output == 50
        assert data.tokens.cached == 1200  # aggregate
