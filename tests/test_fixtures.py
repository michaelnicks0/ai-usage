"""Tests for the conftest fixtures (ensuring they work)."""

import pytest


def test_credentials_fixture(credentials):
    """Credentials fixture provides test values."""
    from ai_usage.config import Credentials
    assert isinstance(credentials, Credentials)
    assert credentials.deepseek_api_key == "sk-test-ds-key"
    assert credentials.http_timeout == 10


def test_http_client_fixture(http_client):
    """HTTP client fixture has short timeouts."""
    from ai_usage.http import HttpClient
    assert isinstance(http_client, HttpClient)
    assert http_client.timeout == 1
    assert http_client.max_retries == 1


def test_mock_http(mock_http):
    """Mock HTTP client works."""
    from ai_usage.http import HttpClient
    mock_http.get_json.return_value = {"key": "value"}
    assert mock_http.get_json("http://test") == {"key": "value"}
