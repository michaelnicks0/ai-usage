"""Tests for Codex provider."""

from __future__ import annotations

import json
import queue

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


def test_rpc_auth_error_is_reported_not_silent(monkeypatch, credentials, mock_http):
    error_message = "failed to fetch codex rate limits: token_expired"
    proc = _FakeProcess({"error": {"code": -32603, "message": error_message}})

    monkeypatch.setattr(codex_module, "_resolve_node", lambda: "/tmp/node")
    monkeypatch.setattr(codex_module.subprocess, "Popen", lambda *args, **kwargs: proc)

    data = CodexProvider(credentials, mock_http).fetch()

    assert data.extra == {"plan_type": "unknown"}
    assert data.meta["auth_error"] is True
    assert data.meta["rpc_error"] == error_message


def test_missing_codex_cli_is_reported_not_silent(monkeypatch, credentials, mock_http):
    monkeypatch.setattr(codex_module, "_resolve_node", lambda: None)

    def raise_not_found(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(codex_module.subprocess, "Popen", raise_not_found)

    data = CodexProvider(credentials, mock_http).fetch()

    assert data.extra == {"plan_type": "unknown"}
    assert data.meta["auth_error"] is True
    assert data.meta["launch_error"] == "codex not found"
