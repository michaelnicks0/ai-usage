# ai-usage Architecture

| Field | Value |
|---|---|
| Status | Active local workstation utility |
| Source of truth | Markdown and Mermaid in this file |
| Runtime entry point | `ai_usage.cli:main` / `ai-usage` |
| Implementation root | `src/ai_usage/` |
| Legacy rendered companions | `architecture.html`, `data-architecture.html` |

## Scope

`ai-usage` is a Python CLI that fetches account balance, spend, subscription quota, and token-usage data across provider APIs, normalizes those responses into `ProviderData`, stores snapshots in SQLite, and renders table or JSON output.

This document describes the current source-level architecture. The HTML files in the repo are historical rendered diagrams; Markdown/Mermaid is the canonical documentation source going forward.

## Component model

```mermaid
flowchart TB
    operator["Operator"]:::actor --> cli["CLI<br/>ai_usage.cli:main"]:::process

    cli --> config["Credential loader<br/>config.load_credentials"]:::process
    cli --> registry["Provider registry<br/>providers.registry"]:::process
    cli --> fetcher["Fetch orchestrator<br/>fetcher.fetch_all"]:::process
    cli --> db["SnapshotDB<br/>SQLite history"]:::datastore
    cli --> render["Renderer<br/>table / JSON / history"]:::process

    config --> hermesEnv[("~/.hermes/.env")]:::datastore
    config --> vastKey[("~/.config/vastai/vast_api_key")]:::datastore
    config --> nousAuth[("~/.hermes/auth.json")]:::datastore

    registry --> providers["Provider modules<br/>deepseek, xai, vastai, exa, x, codex, claude, nous, google"]:::process
    fetcher --> http["HttpClient<br/>timeout + retry"]:::process
    fetcher --> providers
    providers --> http

    http --> providerApis["External provider APIs"]:::external
    providers --> localCLIs["Local CLIs / files<br/>Codex, Claude, Google OAuth"]:::external

    providers --> normalized["ProviderData<br/>balance, spend, tokens, models, extra, meta"]:::datastore
    normalized --> db
    normalized --> render
    render --> terminal["Terminal output"]:::actor

    classDef actor fill:#dbeafe,stroke:#2563eb,color:#111827,stroke-width:1.5px;
    classDef process fill:#dcfce7,stroke:#16a34a,color:#111827,stroke-width:1.5px;
    classDef datastore fill:#fef3c7,stroke:#d97706,color:#111827,stroke-width:1.5px;
    classDef external fill:#f3e8ff,stroke:#9333ea,color:#111827,stroke-width:1.5px;
```

## Live-fetch flow

```mermaid
sequenceDiagram
    participant user as Operator
    participant cli as CLI
    participant cfg as load_credentials
    participant reg as Provider registry
    participant fetch as fetch_all
    participant prov as Provider modules
    participant api as Provider APIs / local CLIs
    participant db as SnapshotDB
    participant render as Renderer

    user->>cli: ai-usage [-p providers] [-m] [-j]
    cli->>cfg: Load credentials and timeouts
    cfg-->>cli: Credentials
    cli->>reg: Build requested providers
    reg-->>cli: Provider instances
    cli->>fetch: Fetch providers in parallel
    fetch->>prov: provider.fetch()
    prov->>api: HTTP request, local CLI call, or local file read
    api-->>prov: Raw provider response
    prov-->>fetch: ProviderData
    fetch-->>cli: Results by provider name
    cli->>db: Save fetched snapshot rows
    cli->>render: Render table or JSON
    render-->>user: Normalized output
```

## Registered providers

| Provider key | Display name | Result type | Primary source |
|---|---|---|---|
| `deepseek` | DeepSeek | Balance, spend, token usage | DeepSeek API + platform usage API |
| `xai` | xAI | Balance, spend, token usage | xAI management billing APIs |
| `vastai` | Vast.ai | Balance and spend | Vast.ai user and charges APIs |
| `exa` | Exa | Balance and spend | Exa dashboard/admin APIs |
| `x` | X API | Credit balance and spend | X console API |
| `codex` | Codex | Subscription/session quota with interactive auth-retry fallback | `codex app-server` JSON-RPC |
| `claude` | Claude Code | Subscription/session quota and local usage | Anthropic OAuth usage API + Claude local files + Claude CLI refresh |
| `nous` | Nous | Subscription credits | Nous Portal OAuth API |
| `google` | Google AI Studio | Model quota rows with OAuth refresh retry | Cloud Code internal model/quota endpoint |

## Data boundaries

- Credential values live outside the repo and must not be copied into Markdown.
- Provider errors are normalized into `ProviderData.meta` rather than crashing the whole table where possible; Codex auth failures trigger one interactive `codex login` retry on TTY and otherwise render as `auth failed` instead of disappearing from the subscription table.
- `SnapshotDB` stores normalized numeric output for history; raw provider payloads are not the documentation source.
- Codex, Claude, Google, and Nous have quota/subscription semantics that do not map cleanly to a simple dollar balance row.
- Claude OAuth refresh is delegated to the Claude Code CLI with a minimal prompt when the cached access token is near expiry or the usage endpoint rejects it with an auth/rate-limit status.
- Google OAuth refresh runs before expiry and retries once after auth/rate-limit statuses from the Cloud Code quota endpoint.

## Maintenance notes

- Add a provider by creating a dedicated module under `src/ai_usage/providers/`, registering it, and updating the README provider/API tables.
- Do not turn provider-specific quirks into broad flags on existing providers unless the implementation already uses that pattern.
- Keep `docs/data-architecture.md` synchronized when endpoint fields or normalized output fields change.
