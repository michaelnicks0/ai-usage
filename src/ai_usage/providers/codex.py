"""Codex (OpenAI) provider — session/weekly rate limits via CLI app-server."""

from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import threading
import time
from collections import OrderedDict
from urllib.error import HTTPError

from ai_usage.config import CodexAccountCredential
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


def _codex_usage_url(base_url: str) -> str:
    """Return the Codex usage endpoint for a backend/API base URL."""
    normalized = (base_url or "").strip().rstrip("/")
    if not normalized:
        normalized = "https://chatgpt.com/backend-api/codex"
    if normalized.endswith("/codex"):
        normalized = normalized[: -len("/codex")]
    if "/backend-api" in normalized:
        return normalized + "/wham/usage"
    return normalized + "/api/codex/usage"


def _decode_jwt_payload(token: str) -> dict:
    """Decode an OAuth JWT payload without logging or validating secrets."""
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return {}
        payload = parts[1]
        payload += "=" * ((4 - len(payload) % 4) % 4)
        decoded = base64.urlsafe_b64decode(payload.encode())
        parsed = json.loads(decoded)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _codex_account_id(token: str) -> str | None:
    """Extract ChatGPT account id from a Codex OAuth token, if present."""
    claims = _decode_jwt_payload(token)
    auth_claims = claims.get("https://api.openai.com/auth", {})
    if not isinstance(auth_claims, dict):
        return None
    account_id = auth_claims.get("chatgpt_account_id")
    if isinstance(account_id, str) and account_id.strip():
        return account_id.strip()
    return None


def _codex_plan_type(token: str) -> str | None:
    """Extract plan type from a Codex OAuth token, if present."""
    claims = _decode_jwt_payload(token)
    auth_claims = claims.get("https://api.openai.com/auth", {})
    if not isinstance(auth_claims, dict):
        return None
    plan_type = auth_claims.get("chatgpt_plan_type")
    if isinstance(plan_type, str) and plan_type.strip():
        return plan_type.strip()
    return None


def _clean_percent(value: float) -> int | float:
    """Keep percentage output compact while preserving fractional values."""
    rounded = round(value, 1)
    return int(rounded) if rounded.is_integer() else rounded


def _usage_window(window: dict, label: str) -> dict | None:
    """Normalize one Codex usage API rate-limit window."""
    used = window.get("used_percent")
    if used is None:
        return None
    try:
        used_pct = float(used)
    except (TypeError, ValueError):
        return None

    reset_at = window.get("reset_at")
    try:
        resets_at = int(float(reset_at)) if reset_at is not None else None
    except (TypeError, ValueError):
        resets_at = None

    duration = window.get("limit_window_seconds")
    try:
        duration_mins = int(float(duration) / 60) if duration is not None else 0
    except (TypeError, ValueError):
        duration_mins = 0

    remaining_pct = max(0.0, 100.0 - used_pct)
    return {
        "label": label,
        "used_pct": _clean_percent(used_pct),
        "remaining_pct": _clean_percent(remaining_pct),
        "duration_mins": duration_mins,
        "resets_at": resets_at,
    }


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

    def _fetch_hermes_account(self, account: CodexAccountCredential) -> dict:
        """Fetch one Hermes credential-pool Codex account via usage API."""
        headers = {
            "Authorization": f"Bearer {account.access_token}",
            "Accept": "application/json",
            "User-Agent": "codex-cli",
        }
        account_id = _codex_account_id(account.access_token)
        if account_id:
            headers["ChatGPT-Account-Id"] = account_id

        payload = self.http.get_json(
            _codex_usage_url(account.base_url),
            headers,
            timeout=self.creds.http_timeout,
        )
        if not isinstance(payload, dict):
            raise ValueError("Codex usage endpoint returned non-object JSON")

        rate_limit = payload.get("rate_limit") or {}
        if not isinstance(rate_limit, dict):
            rate_limit = {}

        entry = {
            "label": account.label,
            "source": account.source,
            "plan_type": (
                payload.get("plan_type")
                or _codex_plan_type(account.access_token)
                or "unknown"
            ),
        }
        session = _usage_window(rate_limit.get("primary_window") or {}, "Session")
        weekly = _usage_window(rate_limit.get("secondary_window") or {}, "Weekly")
        if session:
            entry["session"] = session
        if weekly:
            entry["weekly"] = weekly

        credits = payload.get("credits") or {}
        if isinstance(credits, dict):
            entry["credits"] = {
                "balance": credits.get("balance", "0"),
                "has_credits": bool(credits.get("has_credits")),
                "unlimited": bool(credits.get("unlimited")),
            }
        return entry

    def _fetch_hermes_accounts(self) -> ProviderData:
        """Fetch all Hermes credential-pool Codex accounts."""
        data = ProviderData(models=OrderedDict())
        accounts: OrderedDict[str, dict] = OrderedDict()
        errors: dict[str, str] = {}

        for index, account in enumerate(self.creds.codex_accounts, start=1):
            label = account.label or f"account-{index}"
            try:
                accounts[label] = self._fetch_hermes_account(account)
            except HTTPError as exc:
                reason = "auth failed" if exc.code in {401, 403} else f"http {exc.code}"
                accounts[label] = {
                    "label": label,
                    "source": account.source,
                    "plan_type": _codex_plan_type(account.access_token) or "unknown",
                    "error": reason,
                }
                errors[label] = reason
            except Exception as exc:
                accounts[label] = {
                    "label": label,
                    "source": account.source,
                    "plan_type": _codex_plan_type(account.access_token) or "unknown",
                    "error": "api error",
                }
                errors[label] = exc.__class__.__name__

        data.extra = {"accounts": accounts}
        if errors:
            data.meta["account_errors"] = errors
            if len(errors) == len(accounts) and all(
                reason == "auth failed" for reason in errors.values()
            ):
                data.meta["auth_error"] = True

        # Compatibility for existing single-account render/tests/consumers.
        if len(accounts) == 1:
            only = next(iter(accounts.values()))
            for key in ("plan_type", "session", "weekly", "credits"):
                if key in only:
                    data.extra[key] = only[key]

        total_balance = 0.0
        saw_balance = False
        for account_data in accounts.values():
            credits = account_data.get("credits") or {}
            if not isinstance(credits, dict):
                continue
            try:
                total_balance += float(credits.get("balance", 0) or 0)
                saw_balance = True
            except (TypeError, ValueError):
                pass
        if saw_balance:
            data.balance = total_balance

        return data

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
        if self.creds.codex_accounts:
            return self._fetch_hermes_accounts()

        env = self._env()
        data = self._fetch_once(env)
        rpc_error = data.meta.get("rpc_error")
        if data.meta.get("auth_error") and _is_codex_auth_error(rpc_error):
            if self._run_login(env, data):
                refreshed = self._fetch_once(env)
                refreshed.meta["login_refreshed"] = True
                return refreshed
        return data
