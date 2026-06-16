"""Nous Research provider — subscription credits via OAuth API."""

from __future__ import annotations

import json
import os
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ai_usage.models import ProviderData
from ai_usage.providers import Provider, registry

_NOUS_AUTH_PATH = os.path.expanduser("~/.hermes/auth.json")


@dataclass
class NousRefreshResult:
    """Safe, token-redacted status for a Nous OAuth refresh attempt."""

    ok: bool
    status: str
    message: str
    access_token: str = ""


def refresh_nous_auth(auth_path: str | None = None) -> NousRefreshResult:
    """Refresh the Nous OAuth token in Hermes auth state.

    The returned ``message`` is safe to print; the raw token is kept in
    ``access_token`` for callers that need to retry immediately.
    """
    if auth_path is None:
        auth_path = _NOUS_AUTH_PATH

    if not os.path.exists(auth_path):
        return NousRefreshResult(
            False,
            "missing_auth_file",
            f"Nous auth file not found at {auth_path}; run `hermes auth add`.",
        )

    try:
        with open(auth_path) as f:
            auth = json.load(f)
    except (json.JSONDecodeError, OSError):
        return NousRefreshResult(
            False,
            "invalid_auth_file",
            f"Could not read Nous auth state from {auth_path}; run `hermes auth add`.",
        )

    providers = auth.get("providers", {}) if isinstance(auth, dict) else {}
    nous = providers.get("nous", {}) if isinstance(providers, dict) else {}
    if not isinstance(nous, dict):
        return NousRefreshResult(
            False,
            "missing_provider",
            "Nous auth state is missing; run `hermes auth add`.",
        )

    rt = str(nous.get("refresh_token", "") or "").strip()
    cid = str(nous.get("client_id", "") or "").strip()
    if not rt:
        return NousRefreshResult(
            False,
            "missing_refresh_token",
            "Nous refresh token is missing; run `hermes auth add` to re-authenticate.",
        )
    if not cid:
        return NousRefreshResult(
            False,
            "missing_client_id",
            "Nous OAuth client_id is missing; run `hermes auth add` to re-authenticate.",
        )

    try:
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
            new_tokens = json.loads(resp.read().decode())
    except HTTPError as exc:
        return NousRefreshResult(
            False,
            f"http_{exc.code}",
            f"Nous token refresh failed with HTTP {exc.code}; run `hermes auth add`.",
        )
    except Exception as exc:
        return NousRefreshResult(
            False,
            "refresh_failed",
            f"Nous token refresh failed: {exc.__class__.__name__}.",
        )

    at = str(new_tokens.get("access_token", "") or "").strip()
    if not at:
        return NousRefreshResult(
            False,
            "missing_access_token",
            "Nous token refresh response did not include an access token; run `hermes auth add`.",
        )

    nous["access_token"] = at
    if "refresh_token" in new_tokens:
        nous["refresh_token"] = new_tokens["refresh_token"]
    expires_in = new_tokens.get("expires_in", 900)
    nous["expires_at"] = (
        datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    ).isoformat()
    nous["obtained_at"] = datetime.now(timezone.utc).isoformat()
    try:
        with open(auth_path, "w") as f:
            json.dump(auth, f, indent=2)
    except OSError:
        return NousRefreshResult(
            False,
            "write_failed",
            f"Could not write refreshed Nous auth state to {auth_path}.",
        )
    return NousRefreshResult(True, "refreshed", "Nous token refreshed successfully.", at)


def _nous_get_token(initial: str) -> tuple[str, dict]:
    """Get a valid Nous access token, refreshing if expired or missing."""
    meta: dict = {}
    if not os.path.exists(_NOUS_AUTH_PATH):
        if initial:
            return initial, meta
        meta["skip_reason"] = "auth missing"
        meta["skip_detail"] = "Nous auth file missing; run `hermes auth add`."
        return "", meta
    try:
        with open(_NOUS_AUTH_PATH) as f:
            auth = json.load(f)
        nous = auth.get("providers", {}).get("nous", {})
        if not isinstance(nous, dict):
            raise ValueError("Nous auth provider missing")
        at = str(nous.get("access_token", "") or "").strip()
        rt = str(nous.get("refresh_token", "") or "").strip()
        cid = str(nous.get("client_id", "") or "").strip()
        expires = nous.get("expires_at", "")
        if at and expires:
            try:
                exp = datetime.fromisoformat(str(expires).replace("Z", "+00:00"))
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) >= exp - timedelta(seconds=60):
                    refreshed = refresh_nous_auth()
                    if refreshed.ok:
                        meta["token_refreshed"] = True
                        return refreshed.access_token, meta
                    meta["refresh_error"] = refreshed.status
            except (ValueError, TypeError):
                pass

        if at:
            return at, meta
        if initial:
            return initial, meta
        if rt and cid:
            refreshed = refresh_nous_auth()
            if refreshed.ok:
                meta["token_refreshed"] = True
                return refreshed.access_token, meta
            meta["refresh_error"] = refreshed.status
            meta["skip_detail"] = refreshed.message
        else:
            missing = [name for name, value in (
                ("access_token", at), ("refresh_token", rt), ("client_id", cid),
            ) if not value]
            meta["skip_detail"] = (
                f"Nous OAuth {', '.join(missing)} missing; run `hermes auth add`."
            )
        meta["skip_reason"] = "auth missing"
        return "", meta
    except Exception:
        if initial:
            return initial, meta
        meta["skip_reason"] = "auth missing"
        meta["skip_detail"] = "Nous auth state unreadable; run `hermes auth add`."
        return "", meta


@registry.register
class NousProvider(Provider):
    name = "nous"
    display_name = "Nous"

    def fetch(self) -> ProviderData:
        data = ProviderData(models=OrderedDict())

        token, auth_meta = _nous_get_token(self.creds.nous_access_token)
        data.meta.update(auth_meta)
        if not token:
            return data

        def fetch_account(access_token: str) -> dict:
            r = self.http.get_json(
                "https://portal.nousresearch.com/api/oauth/account",
                {"Authorization": f"Bearer {access_token}"},
            )
            return r if isinstance(r, dict) else {}

        try:
            r = fetch_account(token)
        except HTTPError as exc:
            if exc.code not in {401, 403}:
                data.meta["api_error"] = True
                return data

            data.meta["oauth_retry_status"] = exc.code
            refreshed = refresh_nous_auth()
            if not refreshed.ok:
                data.meta["auth_error"] = True
                data.meta["refresh_error"] = refreshed.status
                data.meta["skip_reason"] = "auth failed"
                data.meta["skip_detail"] = refreshed.message
                return data

            data.meta["token_refreshed"] = True
            try:
                r = fetch_account(refreshed.access_token)
            except HTTPError as retry_exc:
                if retry_exc.code in {401, 403}:
                    data.meta["auth_error"] = True
                    data.meta["skip_reason"] = "auth failed"
                    data.meta["skip_detail"] = "Nous token rejected after refresh."
                else:
                    data.meta["api_error"] = True
                return data
            except Exception:
                data.meta["api_error"] = True
                return data
        except Exception:
            data.meta["api_error"] = True
            return data

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

        return data
