"""Tests for Codex provider."""

from __future__ import annotations

import base64
import json
import queue
from email.message import Message
from types import SimpleNamespace
from urllib.error import HTTPError

from ai_usage.config import CodexAccountCredential
from ai_usage.providers import codex as codex_module
from ai_usage.providers.codex import CodexProvider


class _FakeStdin:
    def __init__(self, process):
        self.process = process
        self.writes: list[str] = []
        self.closed = False

    def write(self, data):
        self.writes.append(data)
        req = json.loads(data)
        self.process.enqueue_response(req)

    def flush(self):
        pass

    def close(self):
        self.closed = True
        self.process.stdout.close()


class _FakeStdout:
    def __init__(self):
        self._queue: queue.Queue[str | None] = queue.Queue()

    def put(self, line: str) -> None:
        self._queue.put(line)

    def readline(self):
        line = self._queue.get(timeout=1)
        return "" if line is None else line

    def close(self):
        self._queue.put(None)


class _FakeProcess:
    def __init__(self, rate_limit_response: dict):
        self.rate_limit_response = rate_limit_response
        self.stdout = _FakeStdout()
        self.stdin = _FakeStdin(self)
        self.wait_timeout = None

    def enqueue_response(self, req: dict) -> None:
        if req["method"] == "initialize":
            response = {"id": req["id"], "result": {"userAgent": "ai-usage-test"}}
        elif req["method"] == "account/rateLimits/read":
            response = {"id": req["id"], **self.rate_limit_response}
        else:
            response = {"id": req["id"], "error": {"message": "unexpected method"}}
        self.stdout.put(json.dumps(response) + "\n")

    def wait(self, timeout=None):
        self.wait_timeout = timeout
        return 0


def _success_response() -> dict:
    return {
        "result": {
            "rateLimits": {
                "planType": "pro",
                "primary": {"usedPercent": 6, "windowDurationMins": 300, "resetsAt": 1778467926},
                "secondary": {"usedPercent": 37, "windowDurationMins": 10080, "resetsAt": 1779054726},
                "credits": {"balance": "0", "hasCredits": False},
            }
        }
    }


def _jwt(claims: dict) -> str:
    header = {"alg": "none", "typ": "JWT"}

    def encode(part: dict) -> str:
        raw = json.dumps(part, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    return f"{encode(header)}.{encode(claims)}.signature"


def _usage_payload(plan_type: str, primary_used: int, weekly_used: int) -> dict:
    return {
        "plan_type": plan_type,
        "rate_limit": {
            "primary_window": {
                "used_percent": primary_used,
                "limit_window_seconds": 18000,
                "reset_at": 1778467926,
            },
            "secondary_window": {
                "used_percent": weekly_used,
                "limit_window_seconds": 604800,
                "reset_at": 1779054726,
            },
        },
        "credits": {"balance": 0, "has_credits": False, "unlimited": False},
    }


def test_fetches_all_hermes_codex_accounts(credentials, mock_http):
    token_1 = _jwt({
        "https://api.openai.com/auth": {
            "chatgpt_account_id": "acct-primary",
            "chatgpt_plan_type": "plus",
        }
    })
    token_2 = _jwt({
        "https://api.openai.com/auth": {
            "chatgpt_account_id": "acct-wife",
            "chatgpt_plan_type": "pro",
        }
    })
    credentials.codex_accounts = [
        CodexAccountCredential(label="primary", access_token=token_1, source="device_code"),
        CodexAccountCredential(label="wife-codex-pro", access_token=token_2, source="manual"),
    ]
    mock_http.get_json.side_effect = [
        _usage_payload("plus", primary_used=23, weekly_used=51),
        _usage_payload("pro", primary_used=10, weekly_used=40),
    ]

    data = CodexProvider(credentials, mock_http).fetch()

    assert data.extra is not None
    accounts = data.extra["accounts"]
    assert list(accounts) == ["primary", "wife-codex-pro"]
    assert accounts["primary"]["session"]["remaining_pct"] == 77
    assert accounts["wife-codex-pro"]["weekly"]["remaining_pct"] == 60
    assert mock_http.get_json.call_count == 2
    first_headers = mock_http.get_json.call_args_list[0].args[1]
    assert first_headers["ChatGPT-Account-Id"] == "acct-primary"


def test_hermes_codex_account_failure_does_not_hide_other_accounts(credentials, mock_http):
    credentials.codex_accounts = [
        CodexAccountCredential(label="stale", access_token="not-a-jwt"),
        CodexAccountCredential(label="wife-codex-pro", access_token="not-a-jwt-either"),
    ]
    mock_http.get_json.side_effect = [
        HTTPError("https://chatgpt.com/backend-api/wham/usage", 401, "Unauthorized", Message(), None),
        _usage_payload("pro", primary_used=10, weekly_used=40),
    ]

    data = CodexProvider(credentials, mock_http).fetch()

    assert data.extra is not None
    accounts = data.extra["accounts"]
    assert accounts["stale"]["error"] == "auth failed"
    assert accounts["wife-codex-pro"]["session"]["remaining_pct"] == 90
    assert data.meta["account_errors"] == {"stale": "auth failed"}
    assert "auth_error" not in data.meta


def test_rpc_auth_error_is_reported_not_silent_when_relogin_unavailable(monkeypatch, credentials, mock_http):
    error_message = "failed to fetch codex rate limits: token_expired"
    proc = _FakeProcess({"error": {"code": -32603, "message": error_message}})

    monkeypatch.setattr(codex_module, "_resolve_node", lambda: "/tmp/node")
    monkeypatch.setattr(codex_module.os, "isatty", lambda _fd: False)
    monkeypatch.setattr(codex_module.subprocess, "Popen", lambda *args, **kwargs: proc)

    data = CodexProvider(credentials, mock_http).fetch()

    assert data.extra == {"plan_type": "unknown"}
    assert data.meta["auth_error"] is True
    assert data.meta["rpc_error"] == error_message
    assert data.meta["login_skipped"] == "non-interactive"


def test_rpc_auth_error_runs_codex_login_and_retries(monkeypatch, credentials, mock_http):
    error_message = "failed to fetch codex rate limits: token_expired"
    procs = [
        _FakeProcess({"error": {"code": -32603, "message": error_message}}),
        _FakeProcess(_success_response()),
    ]
    login_calls = []

    monkeypatch.setattr(codex_module, "_resolve_node", lambda: "/tmp/node")
    monkeypatch.setattr(codex_module.os, "isatty", lambda _fd: True)
    monkeypatch.setattr(codex_module.subprocess, "Popen", lambda *args, **kwargs: procs.pop(0))

    def fake_run(cmd, **kwargs):
        login_calls.append((cmd, kwargs))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(codex_module.subprocess, "run", fake_run)

    data = CodexProvider(credentials, mock_http).fetch()

    assert login_calls
    assert login_calls[0][0] == ["codex", "login"]
    assert data.extra is not None
    assert data.extra["plan_type"] == "pro"
    assert data.extra["session"]["remaining_pct"] == 94
    assert data.extra["weekly"]["remaining_pct"] == 63
    assert data.meta["login_refreshed"] is True
    assert "auth_error" not in data.meta


def test_missing_codex_cli_is_reported_not_silent(monkeypatch, credentials, mock_http):
    monkeypatch.setattr(codex_module, "_resolve_node", lambda: None)

    def raise_not_found(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(codex_module.subprocess, "Popen", raise_not_found)

    data = CodexProvider(credentials, mock_http).fetch()

    assert data.extra == {"plan_type": "unknown"}
    assert data.meta["auth_error"] is True
    assert data.meta["launch_error"] == "codex not found"
