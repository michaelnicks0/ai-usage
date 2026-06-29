# AGENTS.md — ai-usage

Guidance for AI coding agents working in this repo. Keep changes surgical and verify documentation against implementation before editing.

## Read first

| Document | Role |
|---|---|
| [`README.md`](README.md) | User-facing usage, provider table, API endpoints, credential setup. |
| [`docs/README.md`](docs/README.md) | Documentation reading path and generated HTML companion contract. |
| [`docs/EXECUTIVE_BRIEF.md`](docs/EXECUTIVE_BRIEF.md) | High-level value, maturity, and risk posture. |
| [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md) | Operator-first usage guide and troubleshooting map. |
| [`docs/TESTS.md`](docs/TESTS.md) | Generated test inventory and verification commands. |
| [`docs/architecture/README.md`](docs/architecture/README.md) | C4 model-as-code workflow, generated artifact contract, and verification gate. |
| [`docs/architecture/workspace.dsl`](docs/architecture/workspace.dsl) | Canonical Structurizr C4 source for topology diagrams. |
| [`docs/architecture.md`](docs/architecture.md) | Canonical Markdown/Mermaid architecture. |
| [`docs/data-architecture.md`](docs/data-architecture.md) | Canonical normalized data model and field mapping. |
| [`docs/architecture/adr/README.md`](docs/architecture/adr/README.md) | Architecture Decision Record index. |
| [`AUDIT.md`](AUDIT.md) | Code quality audit history. |
| [`ai-usage-high-level-doc.html`](ai-usage-high-level-doc.html) | Generated visual front door from `scripts/showcase.spec.json`. Do not hand-edit. |
| [`README.html`](README.html), `docs/*.html` | Generated browser companions from Markdown. Do not hand-edit. |
| [`architecture.html`](architecture.html), [`data-architecture.html`](data-architecture.html) | Legacy root renders retained as historical references. |

## What this is

`ai-usage` is a Python CLI for cross-provider balance, spend, subscription quota, and token-usage reporting. The package entry point is `ai_usage.cli:main`, exposed as `ai-usage`.

Current provider modules live in `src/ai_usage/providers/`:

- `deepseek`
- `xai`
- `openrouter`
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
7. Regenerate `docs/TESTS.md`, `ai-usage-high-level-doc.html`, and same-path HTML companions when counts, docs, or rendered navigation change.
8. If provider topology, auth flow, or data boundaries change, update `docs/architecture/workspace.dsl`, regenerate `docs/architecture/diagrams/`, and add or supersede an ADR when the decision is long-lived.
9. Keep provider-specific quirks inside the provider module unless an existing shared abstraction already fits.

### Code style

- Match the existing module pattern.
- Keep provider changes isolated; do not touch unrelated providers.
- Prefer small provider-specific helpers over broad abstractions that only serve one provider.
- Do not commit real credential values, copied OAuth JSON, cookies, bearer tokens, or private keys.

### Credential handling

- Most API and browser-session credentials are read from `~/.hermes/.env`.
- Vast.ai can also read `~/.config/vastai/vast_api_key`.
- Nous reads Hermes OAuth state from `~/.hermes/auth.json`.
- Codex prefers Hermes `~/.hermes/auth.json` `credential_pool.openai-codex` entries for multi-account quota display; the Codex CLI app-server path is a fallback when no pool entries exist.
- Google AI Studio reads `~/.hermes/auth/google_oauth.json` from the configured `google-agy`/Hermes OAuth path; do not add API-key auth without discussion.
- Exa dashboard/admin calls are skipped unless `EXA_ENABLED=true` is present in the process environment or `~/.hermes/.env`.
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

### Generated docs

```bash
python scripts/generate_test_inventory.py --write
python scripts/generate_showcase.py --spec scripts/showcase.spec.json
python scripts/render_docs.py --repo . --slug ai-usage
```

Before committing docs changes, run all three matching `--check` gates. Markdown is canonical; generated HTML companions are committed for polished browser reading and must not be hand-edited.
`render_docs.py` needs build-time `markdown`, `pygments`, `mmdc`, and a Puppeteer/Chrome headless-shell; keep those dependencies out of product code.

## Pitfalls

- `ProviderData.meta` is the expected place for provider-level failures, timeout markers, and partial-fetch context.
- Codex uses Hermes credential-pool accounts plus the Codex usage API for multi-account quotas, with the Codex CLI app-server JSON-RPC path retained as fallback.
- Claude and Google data depend on local authenticated developer tooling/OAuth state.
- `docs/architecture/workspace.dsl` is canonical for C4 topology; generated artifacts under `docs/architecture/diagrams/` must be regenerated from it. Source-level Markdown/Mermaid docs remain canonical for their narrative/data scope; same-path HTML files are generated companions from `scripts/render_docs.py`.
