"""Codex (OpenAI) provider — session/weekly rate limits via CLI app-server."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time
from collections import OrderedDict

from ai_usage.models import ProviderData
from ai_usage.providers import Provider, registry

CODEX_LOGIN_TIMEOUT_SECONDS = 300
_CODEX_AUTH_ERROR_MARKERS = (
    "auth",
    "token_expired",
    "refresh_token_reused",
    "unauthorized",
)


def _node_version_key(version: str) -> tuple[int, ...]:
    """Sort nvm version names like v20.11.1 semantically."""
    return tuple(int(part) for part in version.lstrip("v").split(".") if part.isdigit())


def _resolve_node() -> str | None:
    """Find the node binary, resolving through nvm if not on PATH."""
    node_path = shutil.which("node")
    if node_path:
        return node_path

    nvm_dir = os.path.expanduser("~/.nvm")
    versions_dir = os.path.join(nvm_dir, "versions", "node")
    if os.path.isdir(versions_dir):
        versions = sorted(os.listdir(versions_dir), key=_node_version_key, reverse=True)
        for v in versions:
            node_bin = os.path.join(versions_dir, v, "bin", "node")
            if os.path.isfile(node_bin):
                return node_bin

    return None


def _is_codex_auth_error(message: str | None) -> bool:
    """Return True for app-server errors that can be fixed by `codex login`."""
    if not message:
        return False
    lowered = message.lower()
    return any(marker in lowered for marker in _CODEX_AUTH_ERROR_MARKERS)


def _can_interactive_login() -> bool:
    """Only run browser/device login from an interactive terminal."""
    return os.isatty(0) and os.isatty(1)


@registry.register
class CodexProvider(Provider):
    name = "codex"
    display_name = "Codex"
    is_subscription = True

    def _mark_unavailable(
        self,
        data: ProviderData,
        *,
        launch_error: str | None = None,
        rpc_error: str | None = None,
    ) -> None:
        """Keep Codex visible in subscription output when its local auth path fails."""
        if data.extra is None:
            data.extra = {"plan_type": "unknown"}
        data.meta["auth_error"] = True
        if launch_error:
            data.meta["launch_error"] = launch_error
        if rpc_error:
            data.meta["rpc_error"] = rpc_error

    def _env(self) -> dict[str, str]:
        """Build a subprocess environment where the Node-backed codex CLI can run."""
        node_bin = _resolve_node()
        env = os.environ.copy()
        if node_bin:
            node_dir = os.path.dirname(node_bin)
            env["PATH"] = node_dir + os.pathsep + env.get("PATH", "")
        return env

    def _run_login(self, env: dict[str, str], data: ProviderData) -> bool:
        """Run interactive `codex login` once when app-server auth is stale."""
        data.meta["login_attempted"] = True
        if not _can_interactive_login():
            data.meta["login_skipped"] = "non-interactive"
            return False
        try:
            result = subprocess.run(
                ["codex", "login"],
                env=env,
                timeout=CODEX_LOGIN_TIMEOUT_SECONDS,
                check=False,
            )
        except FileNotFoundError:
            data.meta["login_error"] = "codex not found"
            return False
        except subprocess.TimeoutExpired:
            data.meta["login_error"] = "timeout"
            return False
        except Exception as exc:
            data.meta["login_error"] = str(exc) or exc.__class__.__name__
            return False

        if result.returncode != 0:
            data.meta["login_error"] = f"exit {result.returncode}"
            return False
        return True

    def _fetch_once(self, env: dict[str, str]) -> ProviderData:
        data = ProviderData(models=OrderedDict())

        try:
            proc = subprocess.Popen(
                ["codex", "app-server"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
                env=env,
            )
        except FileNotFoundError:
            self._mark_unavailable(data, launch_error="codex not found")
            return data

        pending: dict[int, tuple[threading.Event, dict]] = {}
        lock = threading.Lock()
        reader_done = threading.Event()

        def reader() -> None:
            try:
                for line in iter(proc.stdout.readline, ""):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        msg = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    rid = msg.get("id")
                    with lock:
                        if rid in pending:
                            evt, container = pending.pop(rid)
                            container["msg"] = msg
                            evt.set()
            except Exception:
                pass
            finally:
                reader_done.set()

        t = threading.Thread(target=reader, daemon=True)
        t.start()

        def rpc(method: str, params: dict | None = None, rpc_timeout: int = 10) -> dict | None:
            if params is None:
                params = {}
            req_id = int(time.time() * 1000) % 100000
            payload = json.dumps({
                "jsonrpc": "2.0", "id": req_id,
                "method": method, "params": params,
            }) + "\n"
            evt = threading.Event()
            container: dict = {}
            with lock:
                pending[req_id] = (evt, container)
            try:
                proc.stdin.write(payload)
                proc.stdin.flush()
            except (BrokenPipeError, OSError):
                with lock:
                    pending.pop(req_id, None)
                return None
            if not evt.wait(timeout=rpc_timeout):
                with lock:
                    pending.pop(req_id, None)
                return None
            msg = container.get("msg", {})
            if "error" in msg:
                err = msg.get("error") or {}
                message = err.get("message") if isinstance(err, dict) else str(err)
                self._mark_unavailable(data, rpc_error=message or "unknown rpc error")
                return None
            if "result" not in msg:
                self._mark_unavailable(data, rpc_error="missing JSON-RPC result")
                return None
            return msg.get("result")

        try:
            rpc("initialize", {
                "clientInfo": {"name": "ai-usage", "version": "2.0.0"},
            })
            result = rpc("account/rateLimits/read")
            if result:
                rl = result.get("rateLimits", result)
                p = rl.get("primary")
                s = rl.get("secondary")
                cr = rl.get("credits", {})
                extra = {"plan_type": rl.get("planType", "unknown")}
                if p:
                    used_pct = p.get("usedPercent", 0)
                    extra["session"] = {
                        "used_pct": used_pct,
                        "remaining_pct": max(0, 100 - used_pct),
                        "duration_mins": p.get("windowDurationMins", 0),
                        "resets_at": p.get("resetsAt"),
                    }
                if s:
                    used_pct = s.get("usedPercent", 0)
                    extra["weekly"] = {
                        "used_pct": used_pct,
                        "remaining_pct": max(0, 100 - used_pct),
                        "duration_mins": s.get("windowDurationMins", 0),
                        "resets_at": s.get("resetsAt"),
                    }
                extra["credits"] = {
                    "balance": cr.get("balance", "0"),
                    "has_credits": cr.get("hasCredits", False),
                }
                try:
                    data.balance = float(extra["credits"]["balance"])
                except (ValueError, TypeError):
                    data.balance = 0
                data.extra = extra
        except Exception:
            self._mark_unavailable(data, rpc_error="codex provider exception")
        finally:
            try:
                proc.stdin.close()
            except Exception:
                pass
            try:
                proc.wait(timeout=3)
            except Exception:
                pass

        return data

    def fetch(self) -> ProviderData:
        env = self._env()
        data = self._fetch_once(env)
        rpc_error = data.meta.get("rpc_error")
        if data.meta.get("auth_error") and _is_codex_auth_error(rpc_error):
            if self._run_login(env, data):
                refreshed = self._fetch_once(env)
                refreshed.meta["login_refreshed"] = True
                return refreshed
        return data
