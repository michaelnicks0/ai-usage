# ADR-0004: Adopt generated high-level docs and HTML companions

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-06-28 |
| Decision drivers | Browser-readable docs, drift-proof generated artifacts, consistent portfolio documentation standard |

## Context

`ai-usage` already had mature source-level Markdown, C4/Structurizr artifacts, and legacy root-level HTML renders for architecture/data pages. The missing layer was a higher-altitude documentation front door, a generated test inventory, and same-path HTML companions so browser navigation does not drop readers into raw Markdown.

The repo also needs to preserve the existing C4 model-as-code workflow: `docs/architecture/workspace.dsl` remains canonical for topology, and generated C4 artifacts remain maintainer depth rather than being replaced by a high-level page.

## Decision

Adopt a generated documentation layer:

1. Add `docs/EXECUTIVE_BRIEF.md`, `docs/USER_GUIDE.md`, `docs/README.md`, and generated `docs/TESTS.md` above the existing architecture/data docs.
2. Add `ai-usage-high-level-doc.html` at the repo root as the visual front door generated from `scripts/showcase.spec.json`.
3. Commit the shared docs generators under `scripts/`:
   - `generate_test_inventory.py`
   - `generate_showcase.py`
   - `render_docs.py`
   - `mermaid-theme.json`
4. Render Markdown companions with `scripts/render_docs.py --repo . --slug ai-usage` and commit generated HTML next to the Markdown source.
5. Keep Markdown as canonical source; do not hand-edit generated HTML.
6. Remove stale root-level historical renders; same-path `docs/*.html` companions provide the current generated browser layer.

## Consequences

- Documentation changes now have three drift checks in addition to the test suite:

  ```bash
  python scripts/generate_test_inventory.py --check
  python scripts/generate_showcase.py --spec scripts/showcase.spec.json --check
  python scripts/render_docs.py --repo . --slug ai-usage --check
  ```

- New or removed tests require regenerating `docs/TESTS.md`, the high-level doc metrics, and rendered HTML companions.
- New docs should be linked from `docs/README.md` and, when they are public entry points, from the root `README.md`.
- Existing C4 generated artifacts remain governed by ADR-0001 and `docs/architecture/README.md`.

## Verification

Accepted with this documentation pass after:

- Baseline suite: `.venv/bin/python -m pytest tests/ -v --cov=ai_usage`.
- Generated inventory write/check.
- High-level doc generation/check.
- Markdown-to-HTML companion render/check.
- Link-integrity, secret-pattern, visual QA, whitespace, and committed-tree checks.
