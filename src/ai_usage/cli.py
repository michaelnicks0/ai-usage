"""CLI entry point for ai-usage."""

from __future__ import annotations

import argparse
import sys

from ai_usage.config import load_credentials
from ai_usage.db import SnapshotDB
from ai_usage.fetcher import fetch_all
from ai_usage.http import HttpClient
from ai_usage.providers import registry as provider_registry
from ai_usage.render import (
    render_history,
    render_history_json,
    render_json,
    render_table,
)

# Import all providers to register them
import ai_usage.providers.deepseek  # noqa: F401
import ai_usage.providers.xai      # noqa: F401
import ai_usage.providers.openrouter  # noqa: F401
import ai_usage.providers.vastai   # noqa: F401
import ai_usage.providers.exa      # noqa: F401
import ai_usage.providers.x        # noqa: F401
import ai_usage.providers.codex    # noqa: F401
import ai_usage.providers.claude   # noqa: F401
import ai_usage.providers.nous     # noqa: F401
import ai_usage.providers.google   # noqa: F401

ALL_PROVIDERS = provider_registry.all_names()

HELP_TEXT = """\
ai-usage — cross-provider balance, spend, quota, and token usage.

Fetch normalized account balance, period spend, subscription quota,
and token breakdowns from DeepSeek, xAI, OpenRouter, Vast.ai,
Exa, X API, Codex, Claude Code, Nous, and Google AI Studio.
Reads credentials from ~/.hermes/.env and local OAuth files.

Usage:
  ai-usage                          all providers (default)
  ai-usage -p xai                   single provider
  ai-usage -p deepseek,xai,claude   multiple providers
  ai-usage -m                       per-model token breakdown
  ai-usage -j                       JSON output
  ai-usage -j -m -p deepseek        JSON with per-model models key
  ai-usage --history                 show last 10 snapshots (all providers)
  ai-usage --history --history-provider=xai  show last 10 xAI snapshots
  ai-usage --history --history-limit 30  show last 30 snapshots
  ai-usage --history -j              JSON output for history
  ai-usage help                     this text

Options:
  -p, --provider PROVIDERS  comma-separated provider names (default: all providers)
  -m, --model               add per-model token rows below totals
  -j, --json                machine-readable JSON output
      --history             query saved snapshots instead of live fetch
      --history-provider NAME  filter history to one provider
      --history-limit N     number of snapshots to show (default: 10)
  -h, --help                this text

Output fields (table):
  Provider                 provider name (rows)
  Balance                  credit remaining (USD for API-credit providers)
  Spend                    cost this billing cycle (USD for API-credit providers)
  Tokens In (Hit)          cached prompt tokens
  Tokens In (Miss)         uncached prompt tokens
  Tokens Out               completion tokens
  Tokens Total             sum of all token types

Credentials (from ~/.hermes/.env):
  DEEPSEEK_API_KEY         standard API key
  DEEPSEEK_AUTH_TOKEN      platform session token (expires, see README)
  XAI_MANAGEMENT_KEY       xAI management API key
  XAI_TEAM_ID              xAI team UUID
  OPENROUTER_API_KEY       OpenRouter API key
  VASTAI_API_KEY           Vast.ai API key (or ~/.config/vastai/vast_api_key)
  EXA_SERVICE_KEY          Exa service key (from dashboard.exa.ai)
  EXA_SESSION_TOKEN        Exa dashboard session token (expires, see README)
  EXA_ENABLED              set true to enable Exa dashboard/admin fetches
  X_API_AUTH_TOKEN         X console auth_token cookie
  X_API_CT0                X console CSRF token (ct0 cookie)
  X_API_ACCOUNT_ID         X account ID (from console URL /accounts/{id})
  Codex: requires `codex login` for OAuth token (~/.codex/auth.json)
  Claude Code: reads local ~/.claude.json and ~/.claude/stats-cache.json
  Nous: reads ~/.hermes/auth.json providers.nous.access_token (auto)
  Google AI Studio: reads ~/.hermes/auth/google_oauth.json (auto)
"""


def main(argv: list[str] | None = None) -> int:
    """Main entry point. Returns exit code."""
    if argv is None:
        argv = sys.argv[1:]

    # Help shortcut
    if argv and argv[0] == "help":
        print(HELP_TEXT)
        return 0

    parser = argparse.ArgumentParser(
        description="Cross-provider balance, spend, quota, and token usage.",
        usage="%(prog)s [-p PROVIDERS] [-m] [-j] [--history [--history-provider P] [--history-limit N]]",
        add_help=False,
    )
    parser.add_argument("--model", "-m", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--json", "-j", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument(
        "--provider", "-p",
        default=",".join(ALL_PROVIDERS),
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--history", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--history-provider", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--history-limit", type=int, default=10, help=argparse.SUPPRESS)
    parser.add_argument("--help", "-h", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.help:
        print(HELP_TEXT)
        return 0

    # ── History mode ──
    if args.history:
        db = SnapshotDB()
        provider = args.history_provider
        if provider and provider not in ALL_PROVIDERS:
            print(
                f"Unknown provider: {provider}. Choices: {','.join(ALL_PROVIDERS)}",
                file=sys.stderr,
            )
            return 1
        rows = db.query(
            provider=provider,
            limit=args.history_limit,
            provider_count=len(ALL_PROVIDERS),
        )
        if args.json:
            print(render_history_json(rows))
        else:
            print(render_history(rows, provider=provider))
        db.close()
        return 0

    # ── Live fetch mode ──
    providers = [s.strip().lower() for s in args.provider.split(",") if s.strip()]
    for prov in providers:
        if prov not in ALL_PROVIDERS:
            print(
                f"Unknown provider: {prov}. Choices: {','.join(ALL_PROVIDERS)}",
                file=sys.stderr,
            )
            return 1

    # Load config
    creds = load_credentials()
    http = HttpClient(timeout=creds.http_timeout)

    # Build only requested providers
    prov_instances = {
        name: provider_registry.get(name, creds, http)
        for name in providers
    }

    # Fetch (parallel by default, with total timeout)
    results = fetch_all(
        prov_instances,
        parallel=True,
        total_timeout=creds.total_timeout,
    )

    # Save snapshots (only for fetched providers)
    db = SnapshotDB()
    for name in providers:
        if name in results:
            d = results[name]
            if name == "codex" and d.extra and d.extra.get("accounts"):
                for label, account_data in d.extra["accounts"].items():
                    credits = account_data.get("credits") or {}
                    balance = None
                    if isinstance(credits, dict):
                        try:
                            balance = float(credits.get("balance", 0) or 0)
                        except (TypeError, ValueError):
                            balance = None
                    db.save(
                        f"codex:{label}", balance, None,
                        d.tokens.input, d.tokens.cached, d.tokens.output,
                    )
                continue
            db.save(
                name, d.balance, d.spent,
                d.tokens.input, d.tokens.cached, d.tokens.output,
            )
    db.close()

    # Render
    if args.json:
        print(render_json(results, show_model=args.model))
    else:
        print(render_table(results, show_model=args.model))

    return 0


if __name__ == "__main__":
    sys.exit(main())
