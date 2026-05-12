"""Credential loading from environment and config files."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field


def _read_env_file(path: str) -> dict[str, str]:
    """Parse a KEY=VALUE env file, skipping comments and blank lines."""
    if not os.path.exists(path):
        return {}
    result: dict[str, str] = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                result[k.strip()] = v.strip().strip('"').strip("'")
    return result


@dataclass
class Credentials:
    """All provider credentials, loaded once at startup."""

    # DeepSeek
    deepseek_api_key: str = ""
    deepseek_auth_token: str = ""

    # xAI
    xai_management_key: str = ""
    xai_team_id: str = ""

    # Vast.ai
    vastai_api_key: str = ""

    # Exa
    exa_service_key: str = ""
    exa_session_token: str = ""

    # X (Twitter) API
    x_api_auth_token: str = ""
    x_api_ct0: str = ""
    x_api_account_id: str = ""

    # Nous
    nous_access_token: str = ""

    # Pricing (configurable per environment)
    ds_price_cache_hit: float = 0.003625
    ds_price_cache_miss: float = 0.435
    ds_price_output: float = 0.87

    # Timeouts
    http_timeout: int = 10
    total_timeout: int = 60  # max seconds for full fetch
    cache_ttl: int = 60     # seconds to cache results


def load_credentials(
    env_file: str | None = None,
    vast_file: str | None = None,
    nous_auth_file: str | None = None,
) -> Credentials:
    """Load all credentials from files and environment variables.

    Resolution order per credential: env var → env file → fallback file.

    Args:
        env_file: Path to .env-style file (default: ~/.hermes/.env)
        vast_file: Path to Vast.ai key file (default: ~/.config/vastai/vast_api_key)
        nous_auth_file: Path to Nous OAuth JSON (default: ~/.hermes/auth.json)
    """
    if env_file is None:
        env_file = os.path.expanduser("~/.hermes/.env")
    if vast_file is None:
        vast_file = os.path.expanduser("~/.config/vastai/vast_api_key")
    if nous_auth_file is None:
        nous_auth_file = os.path.expanduser("~/.hermes/auth.json")

    hermes_env = _read_env_file(env_file)

    def _get(key: str, fallback_file: str | None = None) -> str:
        """Resolve a credential: env → env_file → fallback_file."""
        val = os.environ.get(key, hermes_env.get(key, ""))
        if val:
            return val
        if fallback_file and os.path.exists(fallback_file):
            with open(fallback_file) as f:
                return f.read().strip()
        return ""

    # Nous OAuth token
    nous_token = ""
    if os.path.exists(nous_auth_file):
        try:
            with open(nous_auth_file) as f:
                auth = json.load(f)
            nous_token = (
                auth.get("providers", {}).get("nous", {}).get("access_token", "")
            )
        except (json.JSONDecodeError, OSError):
            pass

    return Credentials(
        deepseek_api_key=_get("DEEPSEEK_API_KEY"),
        deepseek_auth_token=_get("DEEPSEEK_AUTH_TOKEN"),
        xai_management_key=_get("XAI_MANAGEMENT_KEY"),
        xai_team_id=_get("XAI_TEAM_ID"),
        vastai_api_key=_get("VASTAI_API_KEY", vast_file),
        exa_service_key=_get("EXA_SERVICE_KEY"),
        exa_session_token=_get("EXA_SESSION_TOKEN"),
        x_api_auth_token=_get("X_API_AUTH_TOKEN"),
        x_api_ct0=_get("X_API_CT0"),
        x_api_account_id=_get("X_API_ACCOUNT_ID"),
        nous_access_token=nous_token,
    )
