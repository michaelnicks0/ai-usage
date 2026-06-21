"""Tests for Claude Code provider."""

from __future__ import annotations

import json
from email.message import Message
from types import SimpleNamespace
from urllib.error import HTTPError

from ai_usage.providers import claude as claude_module
from ai_usage.providers.claude import ClaudeProvider


FUTURE_MS = 9_999_999_999_999


def _write_credentials(
    home,
    token: str,
    expires_at: int = FUTURE_MS,
    subscription_type: str | None = "pro",
) -> None:
    claude_dir = home / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    oauth = {
        "accessToken": token,
        "expiresAt": expires_at,
    }
    if subscription_type is not None:
        oauth["subscriptionType"] = subscription_type
    (claude_dir / ".credentials.json").write_text(json.dumps({
        "claudeAiOauth": oauth,
    }))


def _write_claude_json(home, oauth_account: dict) -> None:
    (home / ".claude.json").write_text(json.dumps({
        "oauthAccount": oauth_account,
        "projects": {},
    }))


def _usage_payload() -> dict:
    return {
        "five_hour": {
            "utilization": 2.0,
            "resets_at": "2026-05-25T01:20:01.056124+00:00",
        },
        "seven_day": {
            "utilization": 0.0,
            "resets_at": "2026-05-25T05:00:00.056154+00:00",
        },
    }


def _http_error(status: int) -> HTTPError:
    return HTTPError(
        "https://api.anthropic.com/api/oauth/usage",
        status,
        "Unauthorized",
        Message(),
        None,
    )


def test_expired_token_refreshes_before_usage_call(tmp_path, monkeypatch, mock_http, credentials):
    _write_credentials(tmp_path, "old-token", expires_at=0)
    monkeypatch.setenv("HOME", str(tmp_path))

    refresh_calls = []

    def fake_run(cmd, **kwargs):
        refresh_calls.append((cmd, kwargs))
        _write_credentials(tmp_path, "new-token", expires_at=FUTURE_MS)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(
        claude_module,
        "subprocess",
        SimpleNamespace(run=fake_run, DEVNULL=object(), TimeoutExpired=TimeoutError),
        raising=False,
    )
    mock_http.get_json.return_value = _usage_payload()

    data = ClaudeProvider(credentials, mock_http).fetch()

    assert refresh_calls
    assert "claude" in refresh_calls[0][0][0]
    headers = mock_http.get_json.call_args.args[1]
    assert headers["Authorization"] == "Bearer new-token"
    assert data.extra is not None
    assert data.extra["session"]["remaining_pct"] == 98
    assert data.meta["token_refreshed"] is True


def test_auth_failure_refreshes_token_and_retries(tmp_path, monkeypatch, mock_http, credentials):
    _write_credentials(tmp_path, "stale-token", expires_at=FUTURE_MS)
    monkeypatch.setenv("HOME", str(tmp_path))

    refresh_calls = []

    def fake_run(cmd, **kwargs):
        refresh_calls.append((cmd, kwargs))
        _write_credentials(tmp_path, "fresh-token", expires_at=FUTURE_MS)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(
        claude_module,
        "subprocess",
        SimpleNamespace(run=fake_run, DEVNULL=object(), TimeoutExpired=TimeoutError),
        raising=False,
    )
    mock_http.get_json.side_effect = [
        _http_error(401),
        _usage_payload(),
    ]

    data = ClaudeProvider(credentials, mock_http).fetch()

    assert refresh_calls
    first_headers = mock_http.get_json.call_args_list[0].args[1]
    second_headers = mock_http.get_json.call_args_list[1].args[1]
    assert first_headers["Authorization"] == "Bearer stale-token"
    assert second_headers["Authorization"] == "Bearer fresh-token"
    assert data.extra is not None
    assert data.extra["weekly"]["remaining_pct"] == 100
    assert data.meta["token_refreshed"] is True


def test_plan_type_falls_back_to_local_organization_type(
    tmp_path,
    monkeypatch,
    mock_http,
    credentials,
):
    _write_credentials(tmp_path, "token", subscription_type=None)
    _write_claude_json(tmp_path, {
        "billingType": "stripe_subscription",
        "organizationType": "claude_pro",
    })
    monkeypatch.setenv("HOME", str(tmp_path))
    mock_http.get_json.return_value = _usage_payload()

    data = ClaudeProvider(credentials, mock_http).fetch()

    assert data.extra is not None
    assert data.extra["plan_type"] == "pro"


def test_local_plan_type_ignores_billing_transport_label(
    tmp_path,
    monkeypatch,
    mock_http,
    credentials,
):
    _write_claude_json(tmp_path, {
        "billingType": "stripe_subscription",
        "organizationType": "claude_max",
    })
    monkeypatch.setenv("HOME", str(tmp_path))

    data = ClaudeProvider(credentials, mock_http).fetch()

    assert data.extra is not None
    assert data.extra["plan_type"] == "max"
    mock_http.get_json.assert_not_called()


def test_refresh_failure_is_reported_without_raising(tmp_path, monkeypatch, mock_http, credentials):
    _write_credentials(tmp_path, "old-token", expires_at=0)
    monkeypatch.setenv("HOME", str(tmp_path))

    def fake_run(cmd, **kwargs):
        return SimpleNamespace(returncode=7)

    monkeypatch.setattr(
        claude_module,
        "subprocess",
        SimpleNamespace(run=fake_run, DEVNULL=object(), TimeoutExpired=TimeoutError),
        raising=False,
    )
    mock_http.get_json.side_effect = _http_error(401)

    data = ClaudeProvider(credentials, mock_http).fetch()

    assert data.meta["refresh_error"] == "exit 7"
    assert data.meta["oauth_error"] is True
