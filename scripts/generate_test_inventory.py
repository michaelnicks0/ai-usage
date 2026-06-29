#!/usr/bin/env python3
"""Generate the canonical test inventory in docs/TESTS.md from pytest sources.

Why this exists
---------------
Hand-maintained test counts in docs drift from reality. This script makes the
inventory genuinely *generated* and self-verifying: it parses the test sources
with Python's ``ast`` module (no execution, no installed dependencies) and
rewrites the sentinel-marked GENERATED regions in ``docs/TESTS.md``.

What it counts
--------------
pytest discovers tests as ``def test_*`` / ``async def test_*`` functions at
module level, plus ``test_*`` methods inside ``Test*`` classes. We count those
*test functions* via AST. This is a deterministic static metric: it does not
expand ``@pytest.mark.parametrize`` cases (that requires collection at runtime),
so the doc states "test functions", not "collected cases". The number is stable,
reproducible anywhere, and cannot silently drift because ``--check`` recomputes
it from source.

Usage
-----
  python scripts/generate_test_inventory.py --write   # rewrite generated regions
  python scripts/generate_test_inventory.py --check    # exit 1 if stale
  python scripts/generate_test_inventory.py --json     # print computed inventory

Body-safe: reads only test source files and prints counts, test/class names,
and line numbers. Never reads mailboxes, tokens, or private databases.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

# Test directories and filename patterns, in preference order.
TEST_DIRS = ("tests", "test")
TEST_GLOBS = ("test_*.py", "*_test.py")
TARGET_DOC = os.path.join("docs", "TESTS.md")

REGION_IDS = ("inventory-summary", "audit-run", "per-file-counts", "test-case-inventory")


@dataclass
class TestCase:
    file: str
    suite: str  # class name, or "(module)" for module-level tests
    name: str
    line: int
    note: str


@dataclass
class FileEntry:
    file: str
    classes: int
    cases: list[TestCase] = field(default_factory=list)


@dataclass
class Inventory:
    file_count: int
    total_cases: int
    total_classes: int
    per_file: list[FileEntry]


def humanize(name: str, docstring: str | None) -> str:
    """Body-safe coverage note from the test's docstring or its name."""
    if docstring:
        first = docstring.strip().splitlines()[0].strip()
        if first:
            sentence = first[0].upper() + first[1:]
            return sentence if sentence[-1:] in ".!?" else sentence + "."
    base = name
    for prefix in ("test_",):
        if base.startswith(prefix):
            base = base[len(prefix):]
    base = base.replace("_", " ").strip()
    if not base:
        return ""
    sentence = base[0].upper() + base[1:]
    return sentence + "."


def escape_cell(value: str) -> str:
    # Markdown-table safety (backslash, pipe) AND HTML-safety: a note lifted from a
    # test docstring may contain literal tags (e.g. "<sub>", '<div class="md-footer">').
    # Left raw, those become ACTIVE tags when the .md is rendered to an .html companion,
    # producing malformed nesting (observed: "</sub> before </details>" tripping a repo's
    # html-well-formedness validator). Escape angle brackets/ampersand so they render as
    # visible text, not markup, in both GitHub-rendered Markdown and the HTML companion.
    return (
        value.replace("\\", "\\\\")
        .replace("|", "\\|")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def find_test_root(root: Path) -> Path | None:
    for name in TEST_DIRS:
        candidate = root / name
        if candidate.is_dir():
            return candidate
    return None


def list_test_files(root: Path) -> list[Path]:
    test_root = find_test_root(root)
    if test_root is None:
        return []
    seen: dict[Path, None] = {}
    for pattern in TEST_GLOBS:
        for path in sorted(test_root.rglob(pattern)):
            seen.setdefault(path, None)
    return list(seen.keys())


def is_test_func(node: ast.AST) -> bool:
    return (
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and (node.name.startswith("test_") or node.name == "test")
    )


def is_test_method(node: ast.AST) -> bool:
    # Methods inside a TestCase subclass: unittest collects "test*"-named methods.
    return (
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test")
    )


def _base_names(node: ast.ClassDef) -> set[str]:
    names: set[str] = set()
    for base in node.bases:
        if isinstance(base, ast.Name):
            names.add(base.id)
        elif isinstance(base, ast.Attribute):
            names.add(base.attr)
    return names


def is_testcase_class(node: ast.AST) -> bool:
    # Detect by base class (unittest.TestCase / TestCase / IsolatedAsyncioTestCase),
    # which is convention-accurate, plus the pytest "Test*"-prefixed class style.
    if not isinstance(node, ast.ClassDef):
        return False
    bases = _base_names(node)
    if bases & {"TestCase", "IsolatedAsyncioTestCase", "AsyncTestCase"}:
        return True
    if any(b.endswith("TestCase") for b in bases):
        return True
    return node.name.startswith("Test")


def parse_test_file(abs_path: Path, rel_path: str) -> FileEntry:
    source = abs_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(abs_path))
    cases: list[TestCase] = []
    class_count = 0
    # Module-level test functions (pytest-style and bare unittest functions).
    for node in tree.body:
        if is_test_func(node):
            cases.append(
                TestCase(
                    file=rel_path,
                    suite="(module)",
                    name=node.name,
                    line=node.lineno,
                    note=humanize(node.name, ast.get_docstring(node)),
                )
            )
    # Test classes: unittest.TestCase subclasses (detected by base class) and
    # pytest Test*-prefixed classes.
    for node in tree.body:
        if is_testcase_class(node):
            method_tests = [m for m in node.body if is_test_method(m)]
            if method_tests:
                class_count += 1
            for m in method_tests:
                cases.append(
                    TestCase(
                        file=rel_path,
                        suite=node.name,
                        name=m.name,
                        line=m.lineno,
                        note=humanize(m.name, ast.get_docstring(m)),
                    )
                )
    cases.sort(key=lambda c: c.line)
    return FileEntry(file=rel_path, classes=class_count, cases=cases)


def build_inventory(root: Path) -> Inventory:
    files = list_test_files(root)
    per_file: list[FileEntry] = []
    total_cases = 0
    total_classes = 0
    for path in files:
        rel = path.relative_to(root).as_posix()
        entry = parse_test_file(path, rel)
        per_file.append(entry)
        total_cases += len(entry.cases)
        total_classes += entry.classes
    return Inventory(
        file_count=len(files),
        total_cases=total_cases,
        total_classes=total_classes,
        per_file=per_file,
    )


def render_summary(inv: Inventory) -> str:
    return (
        f"> **Current inventory:** {inv.total_cases} test functions across "
        f"{inv.file_count} files ({inv.total_classes} test classes)"
    )


def render_run(inv: Inventory) -> str:
    return (
        f"Latest inventory: **{inv.total_cases} test functions** across "
        f"**{inv.file_count} files** and **{inv.total_classes} test classes** "
        f"(AST of `test_*` / `*_test.py`). Regenerate with "
        f"`python scripts/generate_test_inventory.py --write`; enforce with "
        f"`--check`. Counts are static test functions, not parametrized-case "
        f"expansions."
    )


def render_per_file(inv: Inventory) -> str:
    rows = [f"| `{e.file}` | {len(e.cases)} |" for e in inv.per_file]
    return "\n".join(
        ["| Test file | Test functions |", "|---|---:|", *rows,
         f"| **Total** | **{inv.total_cases}** |"]
    )


def render_inventory(inv: Inventory) -> str:
    rows = []
    for e in inv.per_file:
        for c in e.cases:
            rows.append(
                f"| `{e.file}` | `{escape_cell(c.suite)}` | "
                f"`{escape_cell(c.name)}` | {c.line} | {escape_cell(c.note)} |"
            )
    return "\n".join(
        ["| File | Class | Test function | Line | Coverage note |",
         "|---|---|---|---:|---|", *rows]
    )


RENDERERS = {
    "inventory-summary": render_summary,
    "audit-run": render_run,
    "per-file-counts": render_per_file,
    "test-case-inventory": render_inventory,
}


def replace_region(doc: str, region_id: str, body: str) -> str:
    begin = f"<!-- BEGIN GENERATED:{region_id} -->"
    end = f"<!-- END GENERATED:{region_id} -->"
    start = doc.find(begin)
    stop = doc.find(end)
    if start == -1 or stop == -1 or stop < start:
        raise ValueError(
            f"missing or malformed GENERATED markers for '{region_id}' in "
            f"{TARGET_DOC} (expected {begin} ... {end})"
        )
    return doc[: start + len(begin)] + "\n" + body + "\n" + doc[stop:]


def render_doc(doc: str, inv: Inventory) -> str:
    for region_id, renderer in RENDERERS.items():
        doc = replace_region(doc, region_id, renderer(inv))
    return doc


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate the test inventory.")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--write", action="store_const", const="write", dest="mode")
    g.add_argument("--check", action="store_const", const="check", dest="mode")
    p.add_argument("--json", action="store_true")
    p.add_argument("--root", default=None, help="repo root (default: cwd)")
    p.set_defaults(mode="check")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    root = Path(args.root or os.getcwd()).resolve()
    inv = build_inventory(root)

    if args.json:
        print(json.dumps(asdict(inv), indent=2))
        return 0

    doc_path = root / TARGET_DOC
    original = doc_path.read_text(encoding="utf-8")
    updated = render_doc(original, inv)

    if args.mode == "write":
        # Normalize EOF to exactly one trailing newline so a sentinel region at
        # end-of-file never leaves a "new blank line at EOF" that trips
        # `git diff --check`. Idempotent: --check below compares the same form.
        updated = updated.rstrip("\n") + "\n"
        if updated != original:
            doc_path.write_text(updated, encoding="utf-8")
            print(
                f"updated {TARGET_DOC}: {inv.total_cases} functions / "
                f"{inv.file_count} files / {inv.total_classes} classes"
            )
        else:
            print(f"{TARGET_DOC} already current ({inv.total_cases} functions)")
        return 0

    # Apply the same EOF normalization the --write path uses, so a freshly
    # written doc compares clean here (no false "stale" on the trailing newline).
    updated = updated.rstrip("\n") + "\n"
    if updated != original:
        sys.stderr.write(
            f"ERROR {TARGET_DOC} is stale. Run: "
            f"python scripts/generate_test_inventory.py --write "
            f"(expected {inv.total_cases} functions / {inv.file_count} files)\n"
        )
        return 1
    print(
        f"{TARGET_DOC} ok: {inv.total_cases} functions / {inv.file_count} files / "
        f"{inv.total_classes} classes"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
