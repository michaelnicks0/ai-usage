# Architecture Decision Records

> Purpose: track durable architecture and workflow decisions for `ai-usage`.

| Field | Value |
|---|---|
| Status | Active |
| Last updated | 2026-06-16 |
| ADR directory | `docs/architecture/adr/` |

## Index

| ADR | Status | Date | Decision |
|---|---|---:|---|
| [ADR-0001](0001-adopt-structurizr-c4-generated-artifacts.md) | accepted | 2026-06-15 | Adopt Structurizr C4 model and generated artifact workflow. |
| [ADR-0002](0002-use-hermes-codex-credential-pool-for-multi-account-quotas.md) | accepted | 2026-06-16 | Use Hermes Codex credential pool for multi-account quota reporting. |

## Rules

- Use monotonic IDs: `NNNN-kebab-title.md`.
- Preserve accepted ADR history. Supersede with a new ADR instead of rewriting material decisions.
- Include verification evidence after real commands/checks run.
- Keep secrets and credential values out of ADRs.
