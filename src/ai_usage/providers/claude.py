"""Claude Code (Anthropic) provider — OAuth rate limits + local stats."""

from __future__ import annotations

import json
import os
import subprocess
import time
from collections import OrderedDict
from datetime import datetime
from urllib.error import HTTPError

from ai_usage.models import ProviderData, TokenData
from ai_usage.providers import Provider, registry


CLAUDE_USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
CLAUDE_REFRESH_THRESHOLD_MS = 2 * 60 * 60 * 1000
CLAUDE_REFRESH_TIMEOUT_SECONDS = 90
CLAUDE_REFRESH_AUTH_STATUSES = {401, 403, 429}


def _normalize_plan_type(value: object) -> str | None:
    """Normalize Claude local-account tier fields to stable display values."""
    if value is None:
        return None
    raw = str(value).strip().lower().replace("-", "_")
    if not raw or raw in {"none", "null", "unknown"}:
        return None

    # Account metadata also contains billing/rate-limit implementation details
    # that are not user-facing subscription tiers.
    if raw in {"stripe_subscription", "default_claude_ai"}:
        return None

    for prefix in ("claude_", "anthropic_"):
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
    for suffix in ("_tier", "_subscription"):
        if raw.endswith(suffix):
            raw = raw[: -len(suffix)]

    aliases = {
        "professional": "pro",
        "team_plan": "team",
        "enterprise_plan": "enterprise",
    }
    return aliases.get(raw, raw) or None


def _plan_type_from_sources(creds: dict, oauth_account: dict | None = None) -> str:
    """Return the best Claude plan type from current credential/local schemas."""
    oauth_account = oauth_account or {}
    for source in (
        creds.get("subscriptionType"),
        creds.get("planType"),
        oauth_account.get("seatTier"),
        oauth_account.get("organizationType"),
        oauth_account.get("userRateLimitTier"),
        oauth_account.get("billingType"),
    ):
        normalized = _normalize_plan_type(source)
        if normalized:
            return normalized
    return "unknown"


@registry.register
class ClaudeProvider(Provider):
    name = "claude"
    display_name = "Claude Code"
    is_subscription = True

    def _load_oauth(self, path: str) -> dict:
        with open(path) as f:
            return json.load(f).get("claudeAiOauth", {})

    def _token_needs_refresh(self, creds: dict) -> bool:
        expires_at = creds.get("expiresAt")
        if expires_at is None:
            return False
        try:
            expires_ms = int(expires_at)
        except (TypeError, ValueError):
            return False
        return expires_ms - int(time.time() * 1000) <= CLAUDE_REFRESH_THRESHOLD_MS

    def _refresh_token(self, data: ProviderData) -> bool:
        try:
            result = subprocess.run(
                [
                    "claude",
                    "-p",
                    "ping",
                    "--effort",
                    "low",
                    "--max-turns",
                    "1",
                    "--output-format",
                    "json",
                    "--no-session-persistence",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=CLAUDE_REFRESH_TIMEOUT_SECONDS,
                check=False,
            )
        except FileNotFoundError:
            data.meta["refresh_error"] = "claude not found"
            return False
        except subprocess.TimeoutExpired:
            data.meta["refresh_error"] = "timeout"
            return False
        except Exception as exc:
            data.meta["refresh_error"] = str(exc) or exc.__class__.__name__
            return False

        if result.returncode != 0:
            data.meta["refresh_error"] = f"exit {result.returncode}"
            return False

        data.meta["token_refreshed"] = True
        data.meta.pop("refresh_error", None)
        return True

    def _fetch_usage(self, creds: dict) -> dict:
        token = creds.get("accessToken", "")
        if not token:
            return {}
        usage = self.http.get_json(
            CLAUDE_USAGE_URL,
            {
                "Authorization": f"Bearer {token}",
                "anthropic-beta": "oauth-2025-04-20",
            },
        )
        return usage if isinstance(usage, dict) else {}

    def _usage_extra(self, creds: dict, usage: dict, oauth_account: dict | None = None) -> dict:
        extra: dict[str, object] = {"plan_type": _plan_type_from_sources(creds, oauth_account)}
        fh = usage.get("five_hour", {})
        sd = usage.get("seven_day", {})
        if fh:
            util = fh.get("utilization", 0)
            pct = round(util) if util is not None else 0
            resets = fh.get("resets_at")
            extra["session"] = {
                "used_pct": pct,
                "remaining_pct": max(0, 100 - pct),
                "resets_at": (
                    int(datetime.fromisoformat(resets).timestamp())
                    if resets else None
                ),
            }
        if sd:
            util = sd.get("utilization", 0)
            pct = round(util) if util is not None else 0
            resets = sd.get("resets_at")
            extra["weekly"] = {
                "used_pct": pct,
                "remaining_pct": max(0, 100 - pct),
                "resets_at": (
                    int(datetime.fromisoformat(resets).timestamp())
                    if resets else None
                ),
            }
        return extra

    def fetch(self) -> ProviderData:
        data = ProviderData(models=OrderedDict())

        claude_json = os.path.expanduser("~/.claude.json")
        local_config: dict = {}
        local_oauth: dict = {}
        if os.path.exists(claude_json):
            try:
                with open(claude_json) as f:
                    parsed = json.load(f)
                if isinstance(parsed, dict):
                    local_config = parsed
                    oauth = parsed.get("oauthAccount", {})
                    if isinstance(oauth, dict):
                        local_oauth = oauth
            except Exception:
                data.meta["local_config_error"] = True

        creds: dict = {}
        creds_path = os.path.expanduser("~/.claude/.credentials.json")

        # OAuth rate limit API
        if os.path.exists(creds_path):
            try:
                creds = self._load_oauth(creds_path)
                if self._token_needs_refresh(creds) and self._refresh_token(data):
                    creds = self._load_oauth(creds_path)

                try:
                    usage = self._fetch_usage(creds)
                except HTTPError as exc:
                    if exc.code not in CLAUDE_REFRESH_AUTH_STATUSES:
                        raise
                    data.meta["oauth_retry_status"] = exc.code
                    if not self._refresh_token(data):
                        raise
                    creds = self._load_oauth(creds_path)
                    usage = self._fetch_usage(creds)

                if usage:
                    data.extra = self._usage_extra(creds, usage, local_oauth)
            except Exception:
                data.meta["oauth_error"] = True

        # Local file fallback: ~/.claude.json
        if local_config:
            try:
                total_cost = 0.0
                for _proj_path, proj in local_config.get("projects", {}).items():
                    total_cost += proj.get("lastCost", 0)
                    lmu = proj.get("lastModelUsage", {})
                    for model_name, mu in lmu.items():
                        md = data.models.setdefault(model_name, TokenData())
                        md.input += mu.get("inputTokens", 0)
                        md.cached += (
                            mu.get("cacheReadInputTokens", 0) +
                            mu.get("cacheCreationInputTokens", 0)
                        )
                        md.output += mu.get("outputTokens", 0)
                if total_cost > 0:
                    data.spent = round(total_cost, 4)
                if not data.extra:
                    data.extra = {"plan_type": _plan_type_from_sources(creds, local_oauth)}
            except Exception:
                data.meta["local_config_error"] = True

        # Aggregated model usage from stats-cache
        stats_path = os.path.expanduser("~/.claude/stats-cache.json")
        if os.path.exists(stats_path):
            try:
                with open(stats_path) as f:
                    stats = json.load(f)
                model_usage = stats.get("modelUsage", {})
                for model_name, mu in model_usage.items():
                    inp = mu.get("inputTokens", 0)
                    cached = (
                        mu.get("cacheReadInputTokens", 0) +
                        mu.get("cacheCreationInputTokens", 0)
                    )
                    out = mu.get("outputTokens", 0)
                    md = data.models.setdefault(model_name, TokenData())
                    if inp > md.input:
                        md.input = inp
                    if cached > md.cached:
                        md.cached = cached
                    if out > md.output:
                        md.output = out
                data.tokens.input = sum(m.input for m in data.models.values())
                data.tokens.cached = sum(m.cached for m in data.models.values())
                data.tokens.output = sum(m.output for m in data.models.values())
            except Exception:
                data.meta["stats_cache_error"] = True

        return data
