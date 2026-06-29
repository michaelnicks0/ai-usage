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
class CodexAccountCredential:
    """One Hermes-managed Codex OAuth credential.

    Token values are carried only in memory so the Codex provider can query
    subscription quota. Renderers must never expose them.
    """

    label: str
    access_token: str
    refresh_token: str = ""
    base_url: str = "https://chatgpt.com/backend-api/codex"
    source: str = ""
    last_refresh: str = ""
    last_status: str | None = None
    last_error_message: str | None = None
    last_error_reset_at: float | None = None


@dataclass
class Credentials:
    """All provider credentials, loaded once at startup."""

    # DeepSeek
    deepseek_api_key: str = ""
    deepseek_auth_token: str = ""

    # xAI
    xai_management_key: str = ""
    xai_team_id: str = ""

    # OpenRouter
    openrouter_api_key: str = ""

    # Vast.ai
    vastai_api_key: str = ""

    # Exa
    exa_service_key: str = ""
    exa_session_token: str = ""
    exa_enabled: bool = False

    # X (Twitter) API
    x_api_auth_token: str = ""
    x_api_ct0: str = ""
    x_api_account_id: str = ""

    # Nous
    nous_access_token: str = ""

    # Google AI Studio / Antigravity OAuth client metadata
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""

    # Codex / ChatGPT subscription accounts from Hermes credential pool
    codex_accounts: list[CodexAccountCredential] = field(default_factory=list)

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
    codex_auth_file: str | None = None,
) -> Credentials:
    """Load all credentials from files and environment variables.

    Resolution order per credential: env var → env file → fallback file.

    Args:
        env_file: Path to .env-style file (default: ~/.hermes/.env)
        vast_file: Path to Vast.ai key file (default: ~/.config/vastai/vast_api_key)
        nous_auth_file: Path to Nous OAuth JSON (default: ~/.hermes/auth.json)
        codex_auth_file: Path to Hermes auth JSON for Codex pool (default: nous_auth_file)
    """
    if env_file is None:
        env_file = os.path.expanduser("~/.hermes/.env")
    if vast_file is None:
        vast_file = os.path.expanduser("~/.config/vastai/vast_api_key")
    if nous_auth_file is None:
        nous_auth_file = os.path.expanduser("~/.hermes/auth.json")
    if codex_auth_file is None:
        codex_auth_file = nous_auth_file

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

    # Hermes Codex credential pool. Each usable openai-codex entry represents
    # a distinct ChatGPT/Codex subscription account.
    codex_accounts: list[CodexAccountCredential] = []
    if codex_auth_file and os.path.exists(codex_auth_file):
        try:
            with open(codex_auth_file) as f:
                auth = json.load(f)
            pool = auth.get("credential_pool", {})
            entries = pool.get("openai-codex", []) if isinstance(pool, dict) else []
            if isinstance(entries, list):
                for index, entry in enumerate(entries, start=1):
                    if not isinstance(entry, dict):
                        continue
                    access_token = str(entry.get("access_token", "") or "").strip()
                    if not access_token:
                        continue
                    label = str(entry.get("label", "") or "").strip()
                    if not label:
                        label = str(entry.get("source", "") or "").strip()
                    if not label:
                        label = f"account-{index}"
                    codex_accounts.append(CodexAccountCredential(
                        label=label,
                        access_token=access_token,
                        refresh_token=str(entry.get("refresh_token", "") or "").strip(),
                        base_url=str(
                            entry.get("base_url", "")
                            or "https://chatgpt.com/backend-api/codex"
                        ).strip(),
                        source=str(entry.get("source", "") or "").strip(),
                        last_refresh=str(entry.get("last_refresh", "") or "").strip(),
                        last_status=entry.get("last_status"),
                        last_error_message=entry.get("last_error_message"),
                        last_error_reset_at=entry.get("last_error_reset_at"),
                    ))
        except (json.JSONDecodeError, OSError):
            pass

    return Credentials(
        deepseek_api_key=_get("DEEPSEEK_API_KEY"),
        deepseek_auth_token=_get("DEEPSEEK_AUTH_TOKEN"),
        xai_management_key=_get("XAI_MANAGEMENT_KEY"),
        xai_team_id=_get("XAI_TEAM_ID"),
        openrouter_api_key=_get("OPENROUTER_API_KEY"),
        vastai_api_key=_get("VASTAI_API_KEY", vast_file),
        exa_service_key=_get("EXA_SERVICE_KEY"),
        exa_session_token=_get("EXA_SESSION_TOKEN"),
        exa_enabled=_get("EXA_ENABLED").lower() == "true",
        x_api_auth_token=_get("X_API_AUTH_TOKEN"),
        x_api_ct0=_get("X_API_CT0"),
        x_api_account_id=_get("X_API_ACCOUNT_ID"),
        nous_access_token=nous_token,
        google_oauth_client_id=_get("GOOGLE_OAUTH_CLIENT_ID"),
        google_oauth_client_secret=_get("GOOGLE_OAUTH_CLIENT_SECRET"),
        codex_accounts=codex_accounts,
    )
