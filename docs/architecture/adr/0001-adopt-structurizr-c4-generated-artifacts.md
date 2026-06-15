---
id: ADR-0001
status: accepted
date: 2026-06-15
decider: Mike Nicks
scope: repo
supersedes: []
superseded_by: []
related:
  - ../workspace.dsl
  - ../README.md
verification:
  - "Structurizr validate: /tmp/structurizr-cli/structurizr.sh validate -workspace docs/architecture/workspace.dsl"
  - "Generated artifact gate: 5 views with Mermaid SVG/PNG, DOT, Graphviz SVG/PNG, per-view Markdown, c4-diagrams.md, and diagrams/README.md"
  - "Visual QA: all 5 Graphviz PNG views passed readability review"
  - "Repo tests: .venv/bin/python -m pytest tests/ -v --cov=ai_usage --cov-report=term (88 passed, 74% coverage)"
---

# ADR-0001: Adopt Structurizr C4 Model and Generated Artifacts

## Context

`ai-usage` already has source-level Markdown/Mermaid architecture documentation in `docs/architecture.md` and data-shape documentation in `docs/data-architecture.md`. The repo also has legacy rendered HTML companions that are not the canonical maintenance surface.

The requested `/c4-generated-artifact-workflows` application needs a repeatable model-as-code workflow: one canonical C4 source, regenerated review artifacts, and a clear gate that catches stale or partial diagram trees. The requested `/adr` application also needs a repo-local place to record durable architecture decisions.

## Decision

We will maintain the repo's C4 topology in `docs/architecture/workspace.dsl` and treat generated artifacts under `docs/architecture/diagrams/` plus `docs/architecture/c4-diagrams.md` as derived outputs.

We will store Architecture Decision Records in `docs/architecture/adr/`, with `docs/architecture/adr/README.md` as the index. Existing `docs/architecture.md` and `docs/data-architecture.md` remain source-level narrative/data docs; they do not replace the C4 model or ADR log.

## Decision drivers

- Keep C4 topology reviewable as text and renderable as diagrams.
- Avoid hand-maintained diagram drift by regenerating Mermaid, DOT, SVG, PNG, and Markdown wrappers from one DSL file.
- Preserve rationale for future provider/auth/data-boundary and documentation-workflow decisions.
- Keep credential values and host-local secrets out of committed architecture artifacts.

## Options considered

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| Keep only existing Markdown/Mermaid docs | Minimal churn; already familiar. | No Structurizr source of truth; generated artifact workflow remains undefined; no ADR index. | Rejected |
| Add only `workspace.dsl` | Adds model-as-code source. | Fails the generated-artifact workflow; reviewers lack rendered diagrams and per-view pages. | Rejected |
| Add `workspace.dsl`, generated artifacts, and ADR directory | One canonical C4 source, complete derived review tree, and durable decision log. | Adds generated files that must be refreshed when topology changes. | Chosen |

## Consequences

- Positive: Architecture topology can be reviewed as DSL, Markdown atlas pages, Mermaid, DOT, SVG, or PNG.
- Positive: Future long-lived provider/auth/data-boundary decisions have a durable ADR location.
- Neutral / operational: Diagram updates require running the regeneration and artifact-count gates.
- Negative: The repo now carries generated image artifacts; stale artifacts are possible if contributors bypass the workflow.

## Verification / validation

- Verification: `/tmp/structurizr-cli/structurizr.sh validate -workspace docs/architecture/workspace.dsl` completed successfully.
- Verification: the generated artifact gate found 5 views and matching Mermaid SVG/PNG, DOT, Graphviz SVG/PNG, and per-view Markdown artifacts, plus `docs/architecture/c4-diagrams.md` and `docs/architecture/diagrams/README.md`.
- Verification: visual QA passed for all 5 Graphviz PNG views: `SystemContext`, `Containers`, `CliComponents`, `LiveFetchFlow`, and `HistoryFlow`.
- Verification: `.venv/bin/python -m pytest tests/ -v --cov=ai_usage --cov-report=term` completed with 88 passed and 74% total coverage.
- Validation: a future maintainer can inspect `docs/architecture/README.md`, regenerate diagrams from `workspace.dsl`, and understand why generated C4 artifacts are committed.

## Revisit triggers

- Supersede this ADR if the repo adopts another canonical architecture modeling tool.
- Supersede this ADR if generated image artifacts are moved out of Git or replaced by CI-only renders.
- Supersede this ADR if `docs/architecture.md` and `docs/data-architecture.md` are consolidated into the Structurizr workflow.

## References

- `AGENTS.md`
- `README.md`
- `docs/architecture.md`
- `docs/data-architecture.md`
- `src/ai_usage/`
