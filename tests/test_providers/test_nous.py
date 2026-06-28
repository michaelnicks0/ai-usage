"""Tests for Nous Research provider."""

from __future__ import annotations

import json
from email.message import Message
from urllib.error import HTTPError

from ai_usage.providers import nous as nous_module
from ai_usage.providers.nous import NousProvider


class _JsonResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


def _account_payload() -> dict:
    return {
        "paid_service_access": {
            "allowed": True,
            "has_active_subscription": True,
            "subscription_credits_remaining": 17.25,
            "purchased_credits_remaining": 0,
            "total_usable_credits": 17.25,
        },
        "purchased_credits_remaining": 0,
        "subscription": {
            "plan": "Plus",
            "tier": "plus",
            "credits_remaining": 17.25,
            "monthly_charge": 20,
            "monthly_credits": 22,
            "rollover_credits": 0,
            "current_period_end": "2026-06-30T00:00:00Z",
        }
    }


def test_missing_nous_token_reports_auth_missing(monkeypatch, tmp_path, credentials, mock_http):
    auth_path = tmp_path / "auth.json"
    auth_path.write_text(json.dumps({"providers": {"nous": {"client_id": "cid"}}}))
    monkeypatch.setattr(nous_module, "_NOUS_AUTH_PATH", str(auth_path))
    credentials.nous_access_token = ""

    data = NousProvider(credentials, mock_http).fetch()

    assert data.balance is None
    assert data.meta["skip_reason"] == "auth missing"
    assert "refresh_token" in data.meta["skip_detail"]
    mock_http.get_json.assert_not_called()


def test_missing_access_token_refreshes_from_refresh_token(
    monkeypatch, tmp_path, credentials, mock_http,
):
    auth_path = tmp_path / "auth.json"
    auth_path.write_text(json.dumps({
        "providers": {
            "nous": {
                "client_id": "cid",
                "refresh_token": "refresh-old",
            }
        }
    }))
    monkeypatch.setattr(nous_module, "_NOUS_AUTH_PATH", str(auth_path))
    monkeypatch.setattr(
        nous_module,
        "urlopen",
        lambda *args, **kwargs: _JsonResponse({
            "access_token": "access-new",
            "refresh_token": "refresh-new",
            "expires_in": 900,
        }),
    )
    credentials.nous_access_token = ""
    mock_http.get_json.return_value = _account_payload()

    data = NousProvider(credentials, mock_http).fetch()

    assert data.balance == 17.25
    assert data.spent == 4.75
    assert data.meta["token_refreshed"] is True
    headers = mock_http.get_json.call_args.args[1]
    assert headers["Authorization"] == "Bearer access-new"
    stored = json.loads(auth_path.read_text())["providers"]["nous"]
    assert stored["access_token"] == "access-new"
    assert stored["refresh_token"] == "refresh-new"


def test_rejected_token_refreshes_and_retries(monkeypatch, tmp_path, credentials, mock_http):
    auth_path = tmp_path / "auth.json"
    auth_path.write_text(json.dumps({
        "providers": {
            "nous": {
                "client_id": "cid",
                "access_token": "access-stale",
                "refresh_token": "refresh-old",
            }
        }
    }))
    monkeypatch.setattr(nous_module, "_NOUS_AUTH_PATH", str(auth_path))
    monkeypatch.setattr(
        nous_module,
        "urlopen",
        lambda *args, **kwargs: _JsonResponse({"access_token": "access-fresh"}),
    )
    credentials.nous_access_token = ""
    mock_http.get_json.side_effect = [
        HTTPError(
            "https://portal.nousresearch.com/api/oauth/account",
            401,
            "Unauthorized",
            Message(),
            None,
        ),
        _account_payload(),
    ]

    data = NousProvider(credentials, mock_http).fetch()

    assert data.balance == 17.25
    assert data.meta["oauth_retry_status"] == 401
    assert data.meta["token_refreshed"] is True
    retry_headers = mock_http.get_json.call_args_list[1].args[1]
    assert retry_headers["Authorization"] == "Bearer access-fresh"


def test_fetch_reports_total_usable_and_credit_breakdown(credentials, mock_http):
    credentials.nous_access_token = "access-token"
    mock_http.get_json.return_value = {
        "paid_service_access": {
            "allowed": True,
            "has_active_subscription": True,
            "active_subscription_is_paid": True,
            "subscription_tier": 2,
            "subscription_monthly_charge": 20,
            "subscription_credits_remaining": 0,
            "purchased_credits_remaining": 39.83518781012158,
            "total_usable_credits": 39.83518781012158,
            "member_spend_usd": "20.4553837444686889614614",
        },
        "purchased_credits_remaining": 39.83518781012158,
        "subscription": {
            "plan": "Plus",
            "tier": 2,
            "credits_remaining": 0,
            "monthly_charge": 20,
            "monthly_credits": 22,
            "rollover_credits": 3.66,
            "current_period_end": "2026-07-11T15:17:45.000Z",
        },
    }

    data = NousProvider(credentials, mock_http).fetch()

    assert data.balance == 39.84
    assert data.spent == 25.66
    assert data.extra == {
        "plan_type": "Plus",
        "tier": 2,
        "monthly_charge": 20.0,
        "monthly_credits": 22.0,
        "credits_remaining": 39.84,
        "total_usable_credits": 39.84,
        "subscription_credits_remaining": 0.0,
        "top_up_credits_remaining": 39.84,
        "purchased_credits_remaining": 39.84,
        "rollover_credits": 3.66,
        "current_period_end": "2026-07-11T15:17:45.000Z",
        "member_spend_usd": 20.46,
        "period_spend_source": "subscription_credits_consumed",
    }
