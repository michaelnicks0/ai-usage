---
id: ADR-0002
status: accepted
date: 2026-06-16
decider: Mike Nicks
scope: repo
supersedes: []
superseded_by: []
related:
  - ../workspace.dsl
  - ../../architecture.md
  - ../../data-architecture.md
  - ../../../src/ai_usage/config.py
  - ../../../src/ai_usage/providers/codex.py
verification:
  - "Targeted tests: python3 -m pytest tests/test_config.py tests/test_providers/test_codex.py tests/test_render.py tests/test_db.py tests/test_cli.py -q (48 passed)"
  - "Full test/cov suite: .venv/bin/python -m pytest tests/ -v --cov=ai_usage --cov-report=term (99 passed, 75% coverage)"
  - "C4 validation/generation gate: Structurizr validate plus 5-view generated artifact completeness check"
  - "Live smoke: hermes auth list openai-codex && ./ai-usage -p codex && ./ai-usage -j -p codex"
---

# ADR-0002: Use Hermes Codex Credential Pool for Multi-Account Quotas

## Context

`ai-usage` originally treated Codex as a single local CLI account by starting `codex app-server` and reading `account/rateLimits/read`. That matched a single `~/.codex/auth.json` login, but it could not report multiple Codex subscriptions configured in Hermes.

Hermes already supports multiple `openai-codex` credentials in `~/.hermes/auth.json` under `credential_pool.openai-codex`. Those entries have operator-controlled labels and separate OAuth access tokens. The requested behavior is to show both household Codex subscriptions in one `ai-usage -p codex` run without hard-coding personal account names or leaking credential values.

## Decision

`ai-usage` will prefer Hermes's Codex credential pool for Codex quota reporting.

When `credential_pool.openai-codex` contains usable access tokens, `config.load_credentials()` loads them as in-memory `CodexAccountCredential` objects. `CodexProvider` then calls the Codex usage endpoint once per account and stores normalized rows under `ProviderData.extra.accounts`, keyed by the Hermes account label.

The renderer displays account-qualified rows such as `Codex (primary)` and emits JSON under `subscription.codex.accounts`. Snapshot history stores multi-account Codex rows under account-qualified provider keys such as `codex:primary`; `--history-provider codex` includes both legacy `codex` and `codex:*` rows.

If no Hermes Codex pool exists, the legacy single-account Codex CLI app-server path remains the fallback.

## Decision drivers

- Show multiple Codex subscriptions in one command without asking the operator to switch local Codex CLI accounts.
- Use Hermes's existing credential labeling instead of hard-coded user/family names.
- Avoid printing or storing OAuth token material in renderers, docs, tests, or history.
- Preserve existing single-account Codex behavior for environments that only have `~/.codex/auth.json`.
- Avoid misleading history aggregation by keeping account-qualified Codex snapshots distinct.

## Options considered

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| Keep Codex CLI app-server only | Minimal implementation change; existing tests remain valid. | Only one account can be active; Hermes credential pool is ignored. | Rejected |
| Spawn Codex CLI app-server once per temporary `CODEX_HOME` | Reuses app-server RPC shape. | Risky with refresh-token rotation and temporary auth stores; slower and harder to reason about. | Rejected |
| Query Codex usage API per Hermes pool access token | Direct multi-account support; no subprocess per account; labels come from Hermes. | Must maintain provider-specific usage endpoint mapping and JWT account-id extraction. | Chosen |

## Consequences

- Positive: `./ai-usage -p codex` can display all configured Hermes Codex accounts in one table.
- Positive: JSON now has a stable multi-account shape at `subscription.codex.accounts`.
- Positive: History distinguishes account-qualified Codex rows.
- Neutral: The legacy app-server fallback remains for single-account/non-Hermes environments.
- Negative: Codex OAuth access-token freshness is delegated to Hermes/Codex auth management; stale pool entries render as account-scoped failures until refreshed.

## Verification / validation

- Verification: `python3 -m pytest tests/test_config.py tests/test_providers/test_codex.py tests/test_render.py tests/test_db.py tests/test_cli.py -q` completed with 48 passed.
- Verification: `.venv/bin/python -m pytest tests/ -v --cov=ai_usage --cov-report=term` completed with 99 passed and 75% total coverage.
- Verification: Structurizr validation and generated artifact completeness check completed for the 5 C4 views.
- Verification: `hermes auth list openai-codex && ./ai-usage -p codex && ./ai-usage -j -p codex` completed successfully and showed two account-labeled Codex subscription entries.
- Validation: a future maintainer can inspect `src/ai_usage/providers/codex.py` and see that token values are used only in request headers and are never copied into `ProviderData.extra`, rendered output, docs, or snapshot rows.

## Revisit triggers

- Supersede this ADR if Hermes exposes a stable library/CLI command that returns refreshed Codex pool credentials and account usage without reading `auth.json` directly.
- Supersede this ADR if Codex changes the usage endpoint or replaces account quota fields.
- Supersede this ADR if `ai-usage` grows first-class account entities instead of account-qualified provider keys.

## References

- `README.md`
- `docs/architecture.md`
- `docs/data-architecture.md`
- `src/ai_usage/config.py`
- `src/ai_usage/providers/codex.py`
- `src/ai_usage/render.py`
- `src/ai_usage/db.py`
