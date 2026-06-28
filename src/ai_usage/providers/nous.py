"""Nous Research provider — subscription credits via OAuth API."""

from __future__ import annotations

import json
import math
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


def _amount(value: object) -> float | None:
    """Coerce a Nous numeric field to a finite dollar amount."""
    if value is None or value == "":
        return None
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return None
    return amount if math.isfinite(amount) else None


def _round_amount(value: object) -> float | None:
    amount = _amount(value)
    return round(amount, 2) if amount is not None else None


def _first_amount(*values: object) -> float | None:
    for value in values:
        amount = _amount(value)
        if amount is not None:
            return amount
    return None


def _period_spend(
    *,
    member_spend: float | None,
    monthly_credits: float | None,
    rollover_credits: float | None,
    subscription_credits_remaining: float | None,
) -> tuple[float | None, str | None]:
    """Return best available period usage spend and its source.

    The Portal account API exposes ``member_spend_usd``, but live payloads can
    report a value lower than the subscription credits already consumed. The
    billing UI's "Spent This Period" is credit-consumption oriented, so prefer
    the larger of explicit member spend and inferred subscription credit drawdown.
    """
    inferred = None
    if monthly_credits is not None and subscription_credits_remaining is not None:
        period_subscription_pool = monthly_credits + (rollover_credits or 0.0)
        inferred = max(0.0, period_subscription_pool - subscription_credits_remaining)

    if member_spend is not None and inferred is not None:
        if inferred >= member_spend:
            return inferred, "subscription_credits_consumed"
        return member_spend, "member_spend_usd"
    if member_spend is not None:
        return member_spend, "member_spend_usd"
    if inferred is not None:
        return inferred, "subscription_credits_consumed"
    return None, None


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
        if not isinstance(sub, dict):
            sub = {}
        access = r.get("paid_service_access", {})
        if not isinstance(access, dict):
            access = {}

        subscription_credits = _first_amount(
            access.get("subscription_credits_remaining"),
            sub.get("credits_remaining"),
        )
        top_up_credits = _first_amount(
            access.get("purchased_credits_remaining"),
            r.get("purchased_credits_remaining"),
        )
        total_usable = _first_amount(access.get("total_usable_credits"))
        if total_usable is None:
            if subscription_credits is not None or top_up_credits is not None:
                total_usable = (subscription_credits or 0.0) + (top_up_credits or 0.0)
            else:
                total_usable = _amount(sub.get("credits_remaining"))

        monthly_charge = _first_amount(
            sub.get("monthly_charge"),
            access.get("subscription_monthly_charge"),
        )
        monthly_credits = _amount(sub.get("monthly_credits"))
        rollover_credits = _amount(sub.get("rollover_credits"))
        member_spend = _amount(access.get("member_spend_usd"))
        period_spend, period_spend_source = _period_spend(
            member_spend=member_spend,
            monthly_credits=monthly_credits,
            rollover_credits=rollover_credits,
            subscription_credits_remaining=subscription_credits,
        )
        period_end = sub.get("current_period_end")

        data.balance = _round_amount(total_usable)
        data.spent = _round_amount(period_spend)

        tier = (
            sub.get("tier")
            if sub.get("tier") is not None
            else access.get("subscription_tier")
        )
        data.extra = {
            "plan_type": sub.get("plan", "unknown"),
            "tier": tier,
            "monthly_charge": _round_amount(monthly_charge),
            "monthly_credits": _round_amount(monthly_credits),
            "credits_remaining": data.balance,
            "total_usable_credits": data.balance,
            "subscription_credits_remaining": _round_amount(subscription_credits),
            "top_up_credits_remaining": _round_amount(top_up_credits),
            "purchased_credits_remaining": _round_amount(top_up_credits),
            "rollover_credits": _round_amount(rollover_credits),
            "current_period_end": period_end,
            "member_spend_usd": _round_amount(member_spend),
            "period_spend_source": period_spend_source,
        }

        return data
