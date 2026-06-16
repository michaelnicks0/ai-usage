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
        "subscription": {
            "plan": "Plus",
            "tier": "plus",
            "credits_remaining": 17.25,
            "monthly_charge": 20,
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
    assert data.spent == 20.0
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
