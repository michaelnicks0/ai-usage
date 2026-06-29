"""Pytest fixtures for ai-usage tests."""

from __future__ import annotations

import json
import os
import tempfile
from collections import OrderedDict
from unittest.mock import MagicMock, patch

import pytest

from ai_usage.config import Credentials
from ai_usage.http import HttpClient
from ai_usage.models import ProviderData, TokenData


@pytest.fixture
def credentials() -> Credentials:
    """Provide credentials with test values."""
    return Credentials(
        deepseek_api_key="sk-test-ds-key",
        deepseek_auth_token="ds-auth-token-test",
        xai_management_key="xai-mgmt-test",
        xai_team_id="team-123",
        openrouter_api_key="openrouter-test-key",
        vastai_api_key="vast-test-key",
        exa_service_key="exa-svc-test",
        exa_session_token="exa-session-test",
        x_api_auth_token="x-auth-test",
        x_api_ct0="x-ct0-test",
        x_api_account_id="12345",
        nous_access_token="nous-token-test",
        google_oauth_client_id="google-client-id-test",
        google_oauth_client_secret="test-secret",
    )


@pytest.fixture
def http_client() -> HttpClient:
    """HTTP client with short timeouts for tests."""
    return HttpClient(timeout=1, max_retries=1)


@pytest.fixture
def mock_http() -> MagicMock:
    """Mock HTTP client."""
    mock = MagicMock(spec=HttpClient)
    mock.get_json.return_value = {}
    return mock


@pytest.fixture
def temp_env_file():
    """Create a temporary .env-style file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write("TEST_KEY=test_value\n")
        f.write("ANOTHER_KEY=another_value\n")
        f.write("# This is a comment\n")
        f.write("\n")
        f.write('QUOTED_KEY="quoted value"\n')
    yield f.name
    os.unlink(f.name)


@pytest.fixture
def temp_db_path():
    """Create a temporary SQLite database path."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        pass
    yield f.name
    os.unlink(f.name)
