# AGENTS.md — ai-usage

Guidance for AI coding agents working in this repo. Keep changes surgical and verify documentation against implementation before editing.

## Read first

| Document | Role |
|---|---|
| [`README.md`](README.md) | User-facing usage, provider table, API endpoints, credential setup. |
| [`docs/architecture.md`](docs/architecture.md) | Canonical Markdown/Mermaid architecture. |
| [`docs/data-architecture.md`](docs/data-architecture.md) | Canonical normalized data model and field mapping. |
| [`AUDIT.md`](AUDIT.md) | Code quality audit history. |
| [`architecture.html`](architecture.html) | Legacy rendered architecture companion. Do not edit unless explicitly regenerating rendered docs. |
| [`data-architecture.html`](data-architecture.html) | Legacy rendered data companion. Do not edit unless explicitly regenerating rendered docs. |

## What this is

`ai-usage` is a Python CLI for cross-provider balance, spend, subscription quota, and token-usage reporting. The package entry point is `ai_usage.cli:main`, exposed as `ai-usage`.

Current provider modules live in `src/ai_usage/providers/`:

- `deepseek`
- `xai`
- `vastai`
- `exa`
- `x`
- `codex`
- `claude`
- `nous`
- `google`

## Architecture

```text
src/ai_usage/
  cli.py       — argparse CLI entry point
  config.py    — env/config loading from ~/.hermes/.env and provider auth files
  fetcher.py   — parallel/sequential provider fetch orchestration
  http.py      — urllib-based HTTP client with timeout/retry handling
  models.py    — ProviderData and TokenData dataclasses
  db.py        — SQLite snapshot history
  render.py    — table, JSON, and history rendering
  providers/   — one registered Provider subclass per provider
```

## Conventions

### Adding a provider

1. Create `src/ai_usage/providers/<name>.py` with a `Provider` subclass.
2. Decorate the class with `@registry.register`.
3. Import the module in `src/ai_usage/cli.py` so registration happens at startup.
4. Add any new credential fields to `src/ai_usage/config.py`.
5. Add tests in `tests/test_providers/test_<name>.py`.
6. Update `README.md`, `docs/architecture.md`, and `docs/data-architecture.md`.
7. Keep provider-specific quirks inside the provider module unless an existing shared abstraction already fits.

### Code style

- Match the existing module pattern.
- Keep provider changes isolated; do not touch unrelated providers.
- Prefer small provider-specific helpers over broad abstractions that only serve one provider.
- Do not commit real credential values, copied OAuth JSON, cookies, bearer tokens, or private keys.

### Credential handling

- Most credentials are read from `~/.hermes/.env`.
- Vast.ai can also read `~/.config/vastai/vast_api_key`.
- Nous reads Hermes OAuth state from `~/.hermes/auth.json`.
- Google AI Studio uses the configured `google-agy`/Hermes OAuth path; do not add API-key auth without discussion.
- Browser-session credentials that may expire:
  - `DEEPSEEK_AUTH_TOKEN`
  - `EXA_SESSION_TOKEN`
  - `X_API_AUTH_TOKEN`
  - `X_API_CT0`

### Testing

```bash
cd ~/repos/workstation/ai-usage
.venv/bin/python -m pytest tests/ -v --cov=ai_usage
```

Tests should mock HTTP responses and local subprocess/file interactions. Do not run live provider calls from tests.

## Pitfalls

- `ProviderData.meta` is the expected place for provider-level failures, timeout markers, and partial-fetch context.
- Codex uses the Codex CLI app-server JSON-RPC path, not a normal REST API.
- Claude and Google data depend on local authenticated developer tooling/OAuth state.
- Markdown/Mermaid docs are canonical; HTML files are legacy rendered companions unless explicitly regenerated.
