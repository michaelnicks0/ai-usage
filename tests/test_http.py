"""Tests for HTTP client."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ai_usage.http import HttpClient


class TestHttpClient:
    def test_get_json_success(self, mock_http):
        mock_http.get_json.return_value = {"status": "ok"}
        result = mock_http.get_json("https://api.example.com/data")
        assert result == {"status": "ok"}

    def test_custom_headers(self, mock_http):
        mock_http.get_json.return_value = {}
        mock_http.get_json("https://api.example.com", {"Authorization": "Bearer x"})
        mock_http.get_json.assert_called_with(
            "https://api.example.com",
            {"Authorization": "Bearer x"},
        )

    def test_default_user_agent(self):
        client = HttpClient()
        assert "ai-usage" in client.user_agent

    def test_retry_config(self):
        client = HttpClient(max_retries=5, retry_backoff=1.0)
        assert client.max_retries == 5
        assert client.retry_backoff == 1.0
