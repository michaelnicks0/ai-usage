"""Tests for config module."""

from __future__ import annotations

import json
import os
import tempfile

import pytest

from ai_usage.config import Credentials, _read_env_file, load_credentials


class TestReadEnvFile:
    def test_reads_simple_file(self, temp_env_file):
        result = _read_env_file(temp_env_file)
        assert result["TEST_KEY"] == "test_value"
        assert result["ANOTHER_KEY"] == "another_value"
        assert result["QUOTED_KEY"] == "quoted value"

    def test_missing_file_returns_empty(self):
        result = _read_env_file("/nonexistent/path/.env")
        assert result == {}

    def test_ignores_comments_and_blanks(self, temp_env_file):
        result = _read_env_file(temp_env_file)
        assert "#" not in result
        assert "" not in result


class TestCredentials:
    def test_defaults(self):
        c = Credentials()
        assert c.deepseek_api_key == ""
        assert c.openrouter_api_key == ""
        assert c.exa_enabled is False
        assert c.http_timeout == 10
        assert c.total_timeout == 60
        assert c.ds_price_cache_hit == 0.003625

    def test_custom_values(self):
        c = Credentials(
            deepseek_api_key="sk-test",
            http_timeout=5,
            ds_price_cache_hit=0.01,
        )
        assert c.deepseek_api_key == "sk-test"
        assert c.http_timeout == 5
        assert c.ds_price_cache_hit == 0.01


class TestLoadCredentials:
    def test_loads_from_env_vars(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-env-test")
        creds = load_credentials(env_file="/nonexistent/.env")
        assert creds.deepseek_api_key == "sk-env-test"

    def test_loads_from_env_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write("DEEPSEEK_API_KEY=sk-file-test\n")
            f.write("OPENROUTER_API_KEY=or-file-test\n")
            f.write("EXA_ENABLED=true\n")
            env_path = f.name
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as nf:
                nf.write('{"providers":{"nous":{"access_token":"nous-file-token"}}}')
                nous_path = nf.name
            try:
                creds = load_credentials(
                    env_file=env_path,
                    vast_file="/nonexistent/vast_key",
                    nous_auth_file=nous_path,
                )
                assert creds.deepseek_api_key == "sk-file-test"
                assert creds.openrouter_api_key == "or-file-test"
                assert creds.exa_enabled is True
                assert creds.nous_access_token == "nous-file-token"
            finally:
                os.unlink(nous_path)
        finally:
            os.unlink(env_path)

    def test_missing_nous_auth_is_graceful(self):
        creds = load_credentials(nous_auth_file="/nonexistent/auth.json")
        assert creds.nous_access_token == ""

    def test_vast_file_fallback(self, monkeypatch):
        # Clear any real VASTAI_API_KEY env var so fallback file is used
        monkeypatch.delenv("VASTAI_API_KEY", raising=False)
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("vast-file-token\n")
            vast_path = f.name
        try:
            creds = load_credentials(vast_file=vast_path, env_file="/nonexistent/.env")
            assert creds.vastai_api_key == "vast-file-token"
        finally:
            os.unlink(vast_path)
