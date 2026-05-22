# AGENTS.md — ai-usage

Guidance for AI coding agents working in this repo. Focused on what an agent wouldn't infer from the code itself.

## Read first

- [`README.md`](README.md) — what this tool does, provider table, API endpoints, credential setup
- [`AUDIT.md`](AUDIT.md) — code quality audit (test coverage, safety, performance)
- [`architecture.html`](architecture.html) — visual architecture diagram

## What this is

Cross-provider balance + token usage CLI. One command (`ai-usage`) queries 10+ providers (DeepSeek, xAI, Vast.ai, Exa, X API, Codex, Claude, Nous, Google AI Studio) and renders a unified table. v2.0, Python 3.11+, lives at `~/.local/bin/ai-usage`.

## Architecture

```
src/ai_usage/
  cli.py       — argparse CLI entry point
  config.py    — env var loading (~/.hermes/.env)
  fetcher.py   — per-provider fetch orchestration
  http.py      — HTTP client (httpx, retry logic)
  models.py    — dataclasses: Provider, Balance, SubscriptionRow, etc.
  db.py        — SQLite history + cache
  render.py    — table rendering (rich)
  providers/   — one module per provider (deepseek.py, xai.py, codex.py, etc.)
```

## Conventions

### Adding a new provider

1. Create `src/ai_usage/providers/<name>.py` with a `fetch(client, config) -> ProviderResult` function
2. Register it in `src/ai_usage/fetcher.py`'s provider dispatch map
3. Add any new env vars to `src/ai_usage/config.py`
4. Add tests in `tests/test_providers/test_<name>.py`
5. Update README provider table + API endpoints table
6. **Do NOT add a `provider=` parameter to an existing function.** Create a separate provider module. This is an explicit user preference.

### Code style

- Separate functions over parameterized ones
- Surgical changes only — don't touch unrelated providers
- Match existing code style exactly

### Credential handling

- All credentials live in `~/.hermes/.env`, never committed
- Three credentials expire and need manual browser-cookie refresh:
  - `DEEPSEEK_AUTH_TOKEN` — from platform.deepseek.com Network tab
  - `EXA_SESSION_TOKEN` — from dashboard.exa.ai cookies
  - X API cookies (`X_API_AUTH_TOKEN`, `X_API_CT0`) — from console.x.com
- All other credentials are long-lived API keys or auto-refreshing OAuth
- See README "Credential refresh" section for exact steps per provider

### Testing

```bash
cd ~/repos/workstation/ai-usage
.venv/bin/python -m pytest tests/ -v --cov=ai_usage
```

Tests use `conftest.py` fixtures — mock HTTP responses, never real API calls. Test files mirror src structure.

### Provider parity

When a provider's API changes (endpoint moved, schema changed, auth method updated):
1. Fix the provider module
2. Update README API endpoints table
3. If the change affects credential refresh, update the README "Credential refresh" section
4. Check if the provider billing skill needs updating (`provider-billing`)

## Pitfalls

- **Exa, DeepSeek, X API tokens expire.** When balance shows `—` for these providers, the session cookie expired. Don't "fix" the code — the user needs to refresh the cookie in Chrome.
- **Codex uses JSON-RPC over the Codex CLI app-server.** It's not a REST API. The `codex` provider spawns `codex --app-server` and talks JSON-RPC to it.
- **Nous credits deplete with usage.** The `nous` provider uses `~/.hermes/auth.json` OAuth — no manual credential needed, but credits run out mid-month.
- **Google AI Studio uses `google-agy` OAuth.** Don't add Google API key support without discussion — the user prefers the agy integration path.
- **Don't touch `config.py` lightly.** It's the single source of env var names. A typo there breaks real credential loading.
