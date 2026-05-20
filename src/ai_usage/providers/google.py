"""Google AI Studio / Antigravity provider — subscription rate limits via Cloud Code API."""

from __future__ import annotations

import json
import os
import time
from collections import OrderedDict
from datetime import datetime, timezone
import urllib.request
import urllib.parse

from ai_usage.models import ProviderData
from ai_usage.providers import Provider, registry

_GOOGLE_AUTH_PATH = os.path.expanduser("~/.hermes/auth/google_oauth.json")


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
                
        # 2. Fetch Available Models and Quotas
        try:
            req_fm = urllib.request.Request(
                "https://daily-cloudcode-pa.googleapis.com/v1internal:fetchAvailableModels",
                data=json.dumps({"project": project_id}).encode(),
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "User-Agent": "antigravity",
                    "Content-Type": "application/json"
                }
            )
            with urllib.request.urlopen(req_fm, timeout=10) as resp:
                models_res = json.loads(resp.read().decode())
                
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
                    fraction = quota.get("remainingFraction", 1.0)
                    if isinstance(fraction, str):
                        try:
                            fraction = float(fraction)
                        except ValueError:
                            fraction = 1.0
                            
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
                "plan_type": "Ultra 20x" if "gemini-3.1-pro-high" in models else "unknown",
                "models": extra_models
            }
            
        except Exception as e:
            data.meta["api_error"] = str(e)
            
        return data
