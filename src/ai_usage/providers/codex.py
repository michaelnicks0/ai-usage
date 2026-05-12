"""Codex (OpenAI) provider — session/weekly rate limits via CLI app-server."""

from __future__ import annotations

import json
import subprocess
import threading
import time
from collections import OrderedDict

from ai_usage.models import ProviderData
from ai_usage.providers import Provider, registry


@registry.register
class CodexProvider(Provider):
    name = "codex"
    display_name = "Codex"
    is_subscription = True

    def fetch(self) -> ProviderData:
        data = ProviderData(models=OrderedDict())

        try:
            proc = subprocess.Popen(
                ["codex", "app-server"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
            )
        except FileNotFoundError:
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
            if "error" in msg or "result" not in msg:
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
                    extra["session"] = {
                        "used_pct": p.get("usedPercent", 0),
                        "remaining_pct": 100 - p.get("usedPercent", 0),
                        "duration_mins": p.get("windowDurationMins", 0),
                        "resets_at": p.get("resetsAt"),
                    }
                if s:
                    extra["weekly"] = {
                        "used_pct": s.get("usedPercent", 0),
                        "remaining_pct": 100 - s.get("usedPercent", 0),
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
            pass
        finally:
            # Clean shutdown
            try:
                proc.stdin.close()
            except Exception:
                pass
            proc.wait(timeout=3)

        return data
