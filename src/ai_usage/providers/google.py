"""Google AI Studio / Antigravity provider — Cloud Code entitlement and quotas."""

from __future__ import annotations

import json
import os
import time
from collections import OrderedDict
from datetime import datetime, timezone
import urllib.request
import urllib.parse
import urllib.error

from ai_usage.models import ProviderData
from ai_usage.providers import Provider, registry

_GOOGLE_AUTH_PATH = os.path.expanduser("~/.hermes/auth/google_oauth.json")
_CLOUD_CODE_BASE = "https://daily-cloudcode-pa.googleapis.com"
_ANTIGRAVITY_USER_AGENT = "antigravity"
_AUTH_RETRY_STATUSES = {401, 403, 429}


def _cloud_code_post(method: str, token: str, body: dict) -> dict:
    """POST to a Cloud Code v1internal method using Antigravity OAuth context."""
    req = urllib.request.Request(
        f"{_CLOUD_CODE_BASE}/v1internal:{method}",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": _ANTIGRAVITY_USER_AGENT,
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def _tier_dict(value: object) -> dict:
    """Return a tier object only when the API returned a dict."""
    return value if isinstance(value, dict) else {}


def _google_plan_from_entitlement(load_res: dict) -> dict:
    """Normalize loadCodeAssist tier fields without inferring from model access.

    `paidTier.id` is the authoritative Google One AI entitlement signal
    exposed by the Cloud Code API. Model availability/quota responses can lag
    or represent provisioned quota and must not be treated as subscription
    status.
    """
    paid_tier = _tier_dict(load_res.get("paidTier"))
    current_tier = _tier_dict(load_res.get("currentTier"))

    source = "loadCodeAssist.paidTier" if paid_tier.get("id") else "loadCodeAssist.currentTier"
    tier = paid_tier if paid_tier.get("id") else current_tier
    raw_tier_id = str(tier.get("id") or "").strip()
    raw_tier_label = str(tier.get("name") or "").strip()
    normalized = raw_tier_id.lower()

    if "ultra" in normalized:
        plan_type = "ultra"
        plan_label = raw_tier_label or "Google AI Ultra"
        subscription_status = "active"
    elif "pro" in normalized:
        plan_type = "pro"
        plan_label = raw_tier_label or "Google AI Pro"
        subscription_status = "active"
    elif "standard" in normalized:
        plan_type = "standard"
        plan_label = raw_tier_label or "Standard"
        subscription_status = "active"
    elif "free" in normalized or "legacy" in normalized:
        plan_type = "free"
        plan_label = raw_tier_label or "Free"
        subscription_status = "free"
    else:
        plan_type = "unknown"
        plan_label = "Unknown"
        subscription_status = "unknown"
        source = "loadCodeAssist.unavailable"

    return {
        "plan_type": plan_type,
        "plan_label": plan_label,
        "plan_source": source,
        "subscription_status": subscription_status,
        "raw_tier_id": raw_tier_id or None,
    }


def _google_refresh_token(auth_data: dict) -> str:
    """Refresh the Google OAuth token, updating ~/.hermes/auth/google_oauth.json in-place."""
    refresh_packed = auth_data.get("refresh", "")
    if not refresh_packed:
        return auth_data.get("access", "")
    
    # Split the packed token (refreshToken|projectId|managedProjectId)
    refresh_token = refresh_packed.split("|")[0]
    
    # Use agy / Antigravity public desktop credentials
    client_id = "1071006060591-tmhssin2h21lcre235vtolojh4g403ep.apps.googleusercontent.com"
    client_secret = "GOOGLE_OAUTH_CLIENT_SECRET_PLACEHOLDER"
    
    try:
        data = urllib.parse.urlencode({
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }).encode()
        
        req = urllib.request.Request(
            "https://oauth2.googleapis.com/token",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            new_tokens = json.loads(resp.read().decode())
            
        at = new_tokens.get("access_token", "")
        if at:
            auth_data["access"] = at
            expires_in = new_tokens.get("expires_in", 3600)
            auth_data["expires"] = int((time.time() + expires_in) * 1000)
            with open(_GOOGLE_AUTH_PATH, "w") as f:
                json.dump(auth_data, f, indent=2)
            return at
    except Exception:
        pass
    
    return auth_data.get("access", "")


def _google_get_token() -> tuple[str, str | None]:
    """Get valid Google OAuth access token and packed refresh string, refreshing if expired."""
    if not os.path.exists(_GOOGLE_AUTH_PATH):
        return "", None
    try:
        with open(_GOOGLE_AUTH_PATH) as f:
            auth_data = json.load(f)
        
        access = auth_data.get("access", "")
        expires = auth_data.get("expires", 0)
        refresh = auth_data.get("refresh", "")
        
        # Check if expired or about to expire (within 60 seconds buffer)
        if access and expires:
            if int(time.time() * 1000) >= (expires - 60000):
                access = _google_refresh_token(auth_data)
        
        return access, refresh
    except Exception:
        return "", None


@registry.register
class GoogleProvider(Provider):
    name = "google"
    display_name = "Google AI Studio"
    is_subscription = True

    def fetch(self) -> ProviderData:
        data = ProviderData(models=OrderedDict())

        access_token, refresh_packed = _google_get_token()
        if not access_token:
            data.meta["auth_error"] = True
            return data

        # 1. Resolve Project ID
        project_id = "inspired-jar-mf4nj"  # default fallback
        if refresh_packed:
            parts = refresh_packed.split("|")
            if len(parts) >= 2 and parts[1]:
                project_id = parts[1]

        def with_auth_retry(method: str, body: dict) -> dict:
            nonlocal access_token
            try:
                return _cloud_code_post(method, access_token, body)
            except urllib.error.HTTPError as exc:
                if exc.code not in _AUTH_RETRY_STATUSES:
                    raise
                data.meta["oauth_retry_status"] = exc.code
                with open(_GOOGLE_AUTH_PATH) as f:
                    auth_data = json.load(f)
                refreshed_token = _google_refresh_token(auth_data)
                if not refreshed_token or refreshed_token == access_token:
                    raise
                data.meta["token_refreshed"] = True
                access_token = refreshed_token
                return _cloud_code_post(method, access_token, body)

        # 2. Fetch entitlement first. Do not infer subscription from model access.
        plan_info = _google_plan_from_entitlement({})
        metadata = {
            "ideType": "IDE_UNSPECIFIED",
            "platform": "PLATFORM_UNSPECIFIED",
            "pluginType": "GEMINI",
            "duetProject": project_id,
        }
        entitlement_body = {
            "cloudaicompanionProject": project_id,
            "metadata": metadata,
        }

        try:
            entitlement_res = with_auth_retry("loadCodeAssist", entitlement_body)
            plan_info = _google_plan_from_entitlement(entitlement_res)
            companion_project = entitlement_res.get("cloudaicompanionProject")
            if isinstance(companion_project, str) and companion_project.strip():
                project_id = companion_project.strip()
        except Exception as e:
            data.meta["plan_error"] = str(e)

        # 3. Fetch Available Models and Quotas
        models_res: dict = {}
        try:
            models_res = with_auth_retry("fetchAvailableModels", {"project": project_id})
        except Exception as e:
            data.meta["api_error"] = str(e)

        try:
            models = models_res.get("models", {})

            # Map target models for details view (the 7 main models from the UI)
            target_models = {
                "claude-opus-4-6-thinking": "Claude Opus 4.6 (Think)",
                "claude-sonnet-4-6": "Claude Sonnet 4.6 (Think)",
                "gemini-3.1-pro-high": "Gemini 3.1 Pro (High)",
                "gemini-2.5-pro": "Gemini 2.5 Pro",
                "gemini-3-flash-agent": "Gemini 3.5 Flash (High)",
                "gemini-3.1-flash-lite": "Gemini 3.1 Flash Lite",
                "gpt-oss-120b-medium": "GPT-OSS 120B (Medium)"
            }

            extra_models = {}
            for mkey, display_name in target_models.items():
                if mkey in models:
                    m = models[mkey]
                    quota = m.get("quotaInfo", {})
                    if "remainingFraction" in quota:
                        fraction = quota["remainingFraction"]
                        if isinstance(fraction, str):
                            try:
                                fraction = float(fraction)
                            except ValueError:
                                fraction = 1.0
                    else:
                        # When remainingFraction is absent but quotaInfo
                        # exists, the quota is exhausted (0% remaining).
                        fraction = 0.0

                    pct = round(fraction * 100)
                    reset_str = quota.get("resetTime")
                    resets_at = None
                    if reset_str:
                        try:
                            # Parse resetTime (e.g. 2026-05-21T02:25:50Z)
                            dt = datetime.fromisoformat(reset_str.replace("Z", "+00:00"))
                            resets_at = int(dt.timestamp())
                        except Exception:
                            pass

                    extra_models[mkey] = {
                        "display_name": display_name,
                        "remaining_pct": pct,
                        "resets_at": resets_at
                    }

            data.extra = {
                **plan_info,
                "quota_source": "fetchAvailableModels",
                "models": extra_models,
            }

        except Exception as e:
            data.meta["api_error"] = str(e)

        return data
