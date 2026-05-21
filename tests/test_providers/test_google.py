"""Tests for Google AI Studio / Antigravity provider."""

from __future__ import annotations

import json
import os
from unittest.mock import patch, mock_open, MagicMock
import pytest

from ai_usage.providers.google import GoogleProvider


class TestGoogleProvider:
    @patch("ai_usage.providers.google.os.path.exists")
    def test_no_auth_file_returns_empty(self, mock_exists, mock_http, credentials):
        mock_exists.return_value = False
        provider = GoogleProvider(credentials, mock_http)
        data = provider.fetch()
        assert data.meta.get("auth_error") is True

    @patch("ai_usage.providers.google.os.path.exists")
    @patch("ai_usage.providers.google.open", new_callable=mock_open)
    @patch("urllib.request.urlopen")
    def test_refresh_token_needed_and_success(self, mock_urlopen, mock_file_open, mock_exists, mock_http, credentials):
        mock_exists.return_value = True
        
        # Simulated auth.json content
        auth_data = {
            "access": "old_ya29",
            "expires": 1000,  # long expired
            "refresh": "raw_refresh|project_id|managed_id"
        }
        mock_file_open.return_value.read.return_value = json.dumps(auth_data)
        
        # 1. Response for OAuth Token Refresh
        mock_token_resp = MagicMock()
        mock_token_resp.read.return_value = json.dumps({
            "access_token": "new_ya29",
            "expires_in": 3600
        }).encode()
        
        # 2. Response for fetchAvailableModels
        mock_models_resp = MagicMock()
        mock_models_resp.read.return_value = json.dumps({
            "models": {
                "gemini-3.1-pro-high": {
                    "displayName": "Gemini 3.1 Pro (High)",
                    "quotaInfo": {
                        "remainingFraction": 0.85,
                        "resetTime": "2026-05-21T02:25:50Z"
                    }
                }
            }
        }).encode()
        
        # Configure context managers for urlopen
        mock_token_cm = MagicMock()
        mock_token_cm.__enter__.return_value = mock_token_resp
        
        mock_models_cm = MagicMock()
        mock_models_cm.__enter__.return_value = mock_models_resp
        
        mock_urlopen.side_effect = [mock_token_cm, mock_models_cm]
        
        provider = GoogleProvider(credentials, mock_http)
        data = provider.fetch()
        
        # Assertions
        assert data.extra is not None
        assert data.extra["plan_type"] == "Ultra 20x"
        assert "gemini-3.1-pro-high" in data.extra["models"]
        
        model_info = data.extra["models"]["gemini-3.1-pro-high"]
        assert model_info["display_name"] == "Gemini 3.1 Pro (High)"
        assert model_info["remaining_pct"] == 85
        assert model_info["resets_at"] == 1779330350  # 2026-05-21T02:25:50Z in epoch

    @patch("ai_usage.providers.google.os.path.exists")
    @patch("ai_usage.providers.google.open", new_callable=mock_open)
    @patch("urllib.request.urlopen")
    def test_missing_remaining_fraction_is_zero(self, mock_urlopen, mock_file_open, mock_exists, mock_http, credentials):
        """When remainingFraction is absent from quotaInfo, quota is exhausted (0%)."""
        mock_exists.return_value = True
        
        # Not expired
        auth_data = {
            "access": "valid_ya29",
            "expires": 9999999999999,
            "refresh": "raw_refresh|project_id"
        }
        mock_file_open.return_value.read.return_value = json.dumps(auth_data)
        
        # API response with NO remainingFraction — only resetTime
        mock_models_resp = MagicMock()
        mock_models_resp.read.return_value = json.dumps({
            "models": {
                "gemini-3-flash-agent": {
                    "displayName": "Gemini 3.5 Flash (High)",
                    "quotaInfo": {
                        "resetTime": "2026-05-21T01:10:58Z"
                    }
                }
            }
        }).encode()
        
        mock_models_cm = MagicMock()
        mock_models_cm.__enter__.return_value = mock_models_resp
        mock_urlopen.return_value = mock_models_cm
        
        provider = GoogleProvider(credentials, mock_http)
        data = provider.fetch()
        
        model_info = data.extra["models"]["gemini-3-flash-agent"]
        assert model_info["remaining_pct"] == 0  # exhausted, not 100
        assert model_info["resets_at"] is not None  # reset time still parsed

    @patch("ai_usage.providers.google.os.path.exists")
    @patch("ai_usage.providers.google.open", new_callable=mock_open)
    @patch("urllib.request.urlopen")
    def test_api_error_graceful(self, mock_urlopen, mock_file_open, mock_exists, mock_http, credentials):
        mock_exists.return_value = True
        
        # Simulated auth.json content (not expired)
        auth_data = {
            "access": "valid_ya29",
            "expires": 9999999999999,  # far future
            "refresh": "raw_refresh|project_id"
        }
        mock_file_open.return_value.read.return_value = json.dumps(auth_data)
        
        # urlopen context manager raises an error
        mock_urlopen.side_effect = Exception("API connection timeout")
        
        provider = GoogleProvider(credentials, mock_http)
        data = provider.fetch()
        
        assert data.meta.get("api_error") == "API connection timeout"
