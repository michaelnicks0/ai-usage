"""Nous Research provider — subscription credits via OAuth API."""

from __future__ import annotations

import json
import os
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ai_usage.config import Credentials
from ai_usage.http import HttpClient
from ai_usage.models import ProviderData
from ai_usage.providers import Provider, registry

_NOUS_AUTH_PATH = os.path.expanduser("~/.hermes/auth.json")


def _nous_refresh_token(access_token: str) -> str:
    """Refresh the Nous OAuth token, updating ~/.hermes/auth.json in-place."""
    if not os.path.exists(_NOUS_AUTH_PATH):
        return access_token
    try:
        with open(_NOUS_AUTH_PATH) as f:
            auth = json.load(f)
        nous = auth.get("providers", {}).get("nous", {})
        rt = nous.get("refresh_token", "")
        cid = nous.get("client_id", "")
        if not rt or not cid:
            return nous.get("access_token", access_token)

        data = urlencode({
            "grant_type": "refresh_token",
            "refresh_token": rt,
            "client_id": cid,
        }).encode()
        req = Request(
            "https://portal.nousresearch.com/api/oauth/token",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urlopen(req, timeout=10) as resp:
            new_tokens = json.loads(resp.read())

        at = new_tokens.get("access_token", "")
        if at:
            nous["access_token"] = at
            if "refresh_token" in new_tokens:
                nous["refresh_token"] = new_tokens["refresh_token"]
            expires_in = new_tokens.get("expires_in", 900)
            nous["expires_at"] = (
                datetime.now(timezone.utc) + timedelta(seconds=expires_in)
            ).isoformat()
            nous["obtained_at"] = datetime.now(timezone.utc).isoformat()
            with open(_NOUS_AUTH_PATH, "w") as f:
                json.dump(auth, f, indent=2)
        return at
    except Exception:
        return access_token


def _nous_get_token(initial: str) -> str:
    """Get a valid Nous access token, refreshing if expired."""
    if not os.path.exists(_NOUS_AUTH_PATH):
        return initial
    try:
        with open(_NOUS_AUTH_PATH) as f:
            auth = json.load(f)
        nous = auth.get("providers", {}).get("nous", {})
        at = nous.get("access_token", "")
        expires = nous.get("expires_at", "")
        if at and expires:
            try:
                exp = datetime.fromisoformat(expires)
                if datetime.now(timezone.utc) >= exp:
                    return _nous_refresh_token(at)
            except (ValueError, TypeError):
                pass
        return at or initial
    except Exception:
        return initial


@registry.register
class NousProvider(Provider):
    name = "nous"
    display_name = "Nous"

    def fetch(self) -> ProviderData:
        data = ProviderData(models=OrderedDict())

        token = _nous_get_token(self.creds.nous_access_token)
        if token:
            try:
                r = self.http.get_json(
                    "https://portal.nousresearch.com/api/oauth/account",
                    {"Authorization": f"Bearer {token}"},
                )
                sub = r.get("subscription", {})
                credits = sub.get("credits_remaining")
                charge = sub.get("monthly_charge")
                period_end = sub.get("current_period_end")

                data.balance = round(float(credits), 2) if credits is not None else None
                data.spent = round(float(charge), 2) if charge is not None else None

                data.extra = {
                    "plan_type": sub.get("plan", "unknown"),
                    "tier": sub.get("tier"),
                    "monthly_charge": data.spent,
                    "credits_remaining": data.balance,
                    "current_period_end": period_end,
                }
            except Exception:
                data.meta["api_error"] = True

        return data
