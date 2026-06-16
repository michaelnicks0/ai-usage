# ai-usage Architecture Artifacts

> Purpose: define the repo-local C4 model-as-code source, generated diagram artifacts, and verification workflow for `ai-usage`.

| Field | Value |
|---|---|
| Owner | Mike Nicks |
| Status | Active |
| Last updated | 2026-06-16 |
| Canonical C4 source | [`workspace.dsl`](workspace.dsl) |
| Generated atlas | [`c4-diagrams.md`](c4-diagrams.md) |
| ADR index | [`adr/README.md`](adr/README.md) |

## Artifact contract

`workspace.dsl` is the canonical C4/Structurizr model. Generated artifacts under `diagrams/` and the generated atlas are derived from that DSL and should be refreshed together.

```text
docs/architecture/
  workspace.dsl              # canonical C4 model
  README.md                  # this guide
  c4-diagrams.md             # generated diagram atlas
  diagrams/                  # generated Mermaid, DOT, SVG, PNG, and per-view Markdown
  adr/                       # architecture decision records
```

The older source-level Markdown documents remain useful and intentionally stay in place:

| Document | Role |
|---|---|
| [`../architecture.md`](../architecture.md) | Source-level architecture narrative and Mermaid diagrams. |
| [`../data-architecture.md`](../data-architecture.md) | Normalized data model and provider field mapping. |
| [`../../README.md`](../../README.md) | User-facing CLI usage, providers, endpoints, and setup. |
| [`../../AGENTS.md`](../../AGENTS.md) | Agent operating rules for provider and documentation changes. |

## C4 view set

| View key | Level | Purpose |
|---|---|---|
| `SystemContext` | C1 | Shows `ai-usage` in its local workstation/provider ecosystem. |
| `Containers` | C2 | Shows the Python CLI process and local SQLite history store. |
| `CliComponents` | C3 | Shows the source-level components inside the CLI process. |
| `LiveFetchFlow` | Dynamic | Shows the live fetch, normalization, persistence, and render sequence. |
| `HistoryFlow` | Dynamic | Shows the `--history` read/render sequence. |

## Source grounding

The C4 model was grounded in these repo artifacts:

| Source | Grounded facts |
|---|---|
| `AGENTS.md` | Provider inventory, module map, credential handling rules, test command, and documentation conventions. |
| `README.md` | CLI usage, provider/API matrix, credential setup, and output branches. |
| `docs/architecture.md` | Existing source-level component model, live-fetch flow, data boundaries, and maintenance notes. |
| `docs/data-architecture.md` | `ProviderData`/`TokenData` field semantics and provider-to-field mapping. |
| `src/ai_usage/*.py` | Entry point, config loading, fetch orchestration, HTTP retry behavior, SQLite history, rendering, and normalized dataclasses. |
| `src/ai_usage/providers/*.py` | Provider registrations, external API/CLI/file dependencies, OAuth refresh behavior, and normalization paths. |
| `AUDIT.md` | Current provider count, SQLite path, default behavior, and legacy rendered-doc caveat. |

## Regeneration

Run from the repo root:

```bash
STRUCTURIZR_CLI=${STRUCTURIZR_CLI:-/tmp/structurizr-cli/structurizr.sh}
C4_SKILL_DIR=${C4_SKILL_DIR:-$HOME/.hermes/skills/software-development/c4-structurizr-architecture}

"$STRUCTURIZR_CLI" validate -workspace docs/architecture/workspace.dsl

mkdir -p docs/architecture/diagrams
find docs/architecture/diagrams -maxdepth 1 -type f \( -name '*.mmd' -o -name '*.svg' -o -name '*.png' \) -delete
JAVA_TOOL_OPTIONS='-Djava.awt.headless=true' \
  "$STRUCTURIZR_CLI" export -workspace docs/architecture/workspace.dsl -format mermaid -output docs/architecture/diagrams

cat > /tmp/c4-mermaid-config.json <<'JSON'
{"securityLevel":"loose","htmlLabels":true}
JSON
for f in docs/architecture/diagrams/*.mmd; do
  npx --yes @mermaid-js/mermaid-cli -c /tmp/c4-mermaid-config.json -i "$f" -o "${f%.mmd}.svg"
  npx --yes @mermaid-js/mermaid-cli -c /tmp/c4-mermaid-config.json -i "$f" -o "${f%.mmd}.png" -b transparent
done

rm -rf docs/architecture/diagrams/dot docs/architecture/diagrams/dot-rendered
mkdir -p docs/architecture/diagrams/dot docs/architecture/diagrams/dot-rendered
JAVA_TOOL_OPTIONS='-Djava.awt.headless=true' \
  "$STRUCTURIZR_CLI" export -workspace docs/architecture/workspace.dsl -format dot -output docs/architecture/diagrams/dot
python3 "$C4_SKILL_DIR/scripts/graphviz-edge-label-backgrounds.py" docs/architecture/diagrams/dot
for file in docs/architecture/diagrams/dot/*.dot; do
  base=$(basename "$file" .dot)
  dot -Tsvg "$file" -o "docs/architecture/diagrams/dot-rendered/$base.svg"
  dot -Tpng "$file" -o "docs/architecture/diagrams/dot-rendered/$base.png"
done

rm -rf docs/architecture/diagrams/markdown docs/architecture/diagrams/README.md docs/architecture/c4-diagrams.md
python3 "$C4_SKILL_DIR/scripts/structurizr-diagrams-to-markdown.py" \
  --diagrams-dir docs/architecture/diagrams \
  --workspace docs/architecture/workspace.dsl \
  --title "ai-usage C4 Diagrams"
```

## Verification gate

```bash
STRUCTURIZR_CLI=${STRUCTURIZR_CLI:-/tmp/structurizr-cli/structurizr.sh}
"$STRUCTURIZR_CLI" validate -workspace docs/architecture/workspace.dsl

python3 - <<'PY'
from pathlib import Path
expected = len(list(Path('docs/architecture/diagrams').glob('*.mmd')))
assert expected == 5, expected
checks = {
    'mermaid_svg': list(Path('docs/architecture/diagrams').glob('*.svg')),
    'mermaid_png': list(Path('docs/architecture/diagrams').glob('*.png')),
    'dot': list(Path('docs/architecture/diagrams/dot').glob('*.dot')),
    'dot_svg': list(Path('docs/architecture/diagrams/dot-rendered').glob('*.svg')),
    'dot_png': list(Path('docs/architecture/diagrams/dot-rendered').glob('*.png')),
    'markdown': list(Path('docs/architecture/diagrams/markdown').glob('*.md')),
}
for name, files in checks.items():
    assert len(files) == expected, (name, len(files), expected)
assert Path('docs/architecture/c4-diagrams.md').exists()
assert Path('docs/architecture/diagrams/README.md').exists()
print('generated C4 artifact set complete')
PY

git diff --check -- .
```

## Maintenance rules

- Patch `workspace.dsl` first when topology changes; regenerate derived artifacts from a clean derived tree.
- Keep secrets out of diagrams and ADRs. Use environment-variable names and path patterns only.
- Add or supersede ADRs for long-lived architecture, data-boundary, provider-auth, or generated-artifact workflow decisions.
- Do not edit generated Mermaid/DOT/PNG/SVG/Markdown wrappers by hand unless debugging the generator; carry intentional changes back into `workspace.dsl`.
