"""Aider-style repomap token-reduction measurement.

Reads a Python codebase fixture, builds a repomap-compressed view (signatures
+ docstrings only, function bodies elided), counts tokens before/after, and
reports pct reduction.

Two outputs:
  primary_value: pct token reduction (compressed vs full)
  symbol_coverage: fraction of public symbols preserved (sanity check —
                   should be 1.0 since the AST extractor is exhaustive)

NO model invocation — pure deterministic measurement of the structural-
compression axis. The accuracy axis ("does the model still answer correctly
with the compressed view?") needs a model and lives in a future paired
sandbox.
"""

from __future__ import annotations

import ast
import json
import os
import statistics
import time
from pathlib import Path

# Tokenizer with the same fallback pattern as sandbox-e
try:
    import tiktoken  # type: ignore
    _TOKENIZER = tiktoken.get_encoding("cl100k_base")

    def count_tokens(text: str) -> int:
        return len(_TOKENIZER.encode(text))

    TOKENIZER_NAME = "cl100k_base"
except ImportError:
    def count_tokens(text: str) -> int:
        return max(1, len(text) // 4)

    TOKENIZER_NAME = "char-div-4-fallback"


# ----------------------------------------------------------------------
# Repomap extractor — AST-based signature/docstring view
# ----------------------------------------------------------------------

def _is_public(name: str) -> bool:
    """Public name = no leading underscore. Dunders also pass (e.g. __init__)."""
    return not name.startswith("_") or (name.startswith("__") and name.endswith("__"))


def _get_signature_text(node: ast.FunctionDef | ast.AsyncFunctionDef, source: str) -> str:
    """Extract the def-line(s) verbatim from source, up to the colon that
    opens the body.

    Uses ast end_col/end_lineno of the body's first statement to find the
    boundary deterministically rather than re-formatting (which would lose
    fidelity to the source's actual signature line breaks).
    """
    src_lines = source.splitlines(keepends=True)
    start_line = node.lineno - 1  # 0-indexed
    if not node.body:
        end_line = start_line
    else:
        end_line = node.body[0].lineno - 2  # last line of header is body[0].lineno - 1, then -1 for inclusive
    if end_line < start_line:
        end_line = start_line
    return "".join(src_lines[start_line : end_line + 1])


def _extract_docstring(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> str | None:
    """Return the first-line of a docstring if present, else None."""
    docstring = ast.get_docstring(node, clean=True)
    if not docstring:
        return None
    # Repomap convention: first line only — preserve summary, drop details
    return docstring.splitlines()[0]


def build_repomap_for_file(path: Path) -> tuple[str, list[str]]:
    """Return (compressed_view, list_of_public_symbols).

    Compressed view shape per file:
        # path/to/module.py
        from x import y, z
        IMPORTS_AS_USED  # consolidated, no duplicates
        CONSTANTS_AT_MODULE_LEVEL

        def public_func(arg: T, ...) -> R:
            \"\"\"first-line docstring\"\"\"
            ...

        class PublicClass:
            \"\"\"first-line docstring\"\"\"

            def public_method(self, ...) -> R:
                \"\"\"...\"\"\"
                ...
    """
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    out_lines: list[str] = [f"# {path.name}"]
    symbols: list[str] = []

    # Module-level docstring
    mod_doc = ast.get_docstring(tree, clean=True)
    if mod_doc:
        out_lines.append(f'"""{mod_doc.splitlines()[0]}"""')

    # Imports — preserve verbatim
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            out_lines.append(ast.unparse(node))

    # Module-level functions + classes
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not _is_public(node.name):
                continue
            symbols.append(node.name)
            sig = _get_signature_text(node, source).rstrip()
            doc = _extract_docstring(node)
            out_lines.append("")
            out_lines.append(sig)
            if doc:
                out_lines.append(f'    """{doc}"""')
            out_lines.append("    ...")

        elif isinstance(node, ast.ClassDef):
            if not _is_public(node.name):
                continue
            symbols.append(node.name)
            class_def_line = source.splitlines()[node.lineno - 1]
            out_lines.append("")
            out_lines.append(class_def_line)
            cls_doc = _extract_docstring(node)
            if cls_doc:
                out_lines.append(f'    """{cls_doc}"""')
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if not _is_public(child.name):
                        continue
                    symbols.append(f"{node.name}.{child.name}")
                    msig = _get_signature_text(child, source).rstrip()
                    mdoc = _extract_docstring(child)
                    out_lines.append("")
                    out_lines.append(msig)
                    if mdoc:
                        out_lines.append(f'        """{mdoc}"""')
                    out_lines.append("        ...")

    return "\n".join(out_lines) + "\n", symbols


def list_public_symbols_full(path: Path) -> list[str]:
    """Enumerate every public function + class (and class methods) in a file.

    Used as the GROUND TRUTH coverage check — the repomap extractor's
    output should preserve every name in this list.
    """
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    symbols: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if _is_public(node.name):
                symbols.append(node.name)
        elif isinstance(node, ast.ClassDef):
            if _is_public(node.name):
                symbols.append(node.name)
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if _is_public(child.name):
                            symbols.append(f"{node.name}.{child.name}")
    return symbols


# ----------------------------------------------------------------------
# Bench entry point
# ----------------------------------------------------------------------

def main() -> int:
    fixture_root = Path(os.environ.get("FIXTURE_ROOT", "/workloads/codebase-fixture-python"))
    if not fixture_root.exists():
        repo_fixture = (
            Path(__file__).resolve().parents[3] / "workloads" / "codebase-fixture-python"
        )
        if repo_fixture.exists():
            fixture_root = repo_fixture
        else:
            print(f"ERROR: fixture not found at {fixture_root} or {repo_fixture}")
            return 2

    py_files = sorted(p for p in fixture_root.rglob("*.py") if p.is_file())
    if not py_files:
        print(f"ERROR: no .py files under {fixture_root}")
        return 2

    started = time.monotonic()

    full_text_parts: list[str] = []
    repomap_parts: list[str] = []
    expected_symbols: list[str] = []
    extracted_symbols: list[str] = []
    per_file: list[dict] = []

    for path in py_files:
        rel = str(path.relative_to(fixture_root))
        full_content = path.read_text(encoding="utf-8")
        full_with_header = f"# {rel}\n{full_content}"
        full_text_parts.append(full_with_header)

        repomap_view, syms = build_repomap_for_file(path)
        repomap_parts.append(repomap_view)
        extracted_symbols.extend(f"{rel}::{s}" for s in syms)

        full_syms = list_public_symbols_full(path)
        expected_symbols.extend(f"{rel}::{s}" for s in full_syms)

        per_file.append({
            "path": rel,
            "full_tokens": count_tokens(full_with_header),
            "repomap_tokens": count_tokens(repomap_view),
            "public_symbols_extracted": len(syms),
            "public_symbols_expected": len(full_syms),
        })

    full_corpus = "\n".join(full_text_parts)
    repomap_corpus = "\n".join(repomap_parts)
    full_tokens = count_tokens(full_corpus)
    repomap_tokens = count_tokens(repomap_corpus)
    pct_reduction = (1 - repomap_tokens / full_tokens) * 100 if full_tokens else 0.0

    expected_set = set(expected_symbols)
    extracted_set = set(extracted_symbols)
    coverage = (
        len(extracted_set & expected_set) / len(expected_set)
        if expected_set
        else 1.0
    )
    missing_symbols = sorted(expected_set - extracted_set)

    elapsed = time.monotonic() - started

    output = {
        "primary_value": pct_reduction,
        "secondary_value": coverage,
        "duration_seconds": elapsed,
        "tokenizer": TOKENIZER_NAME,
        "n_files": len(py_files),
        "full_tokens_total": full_tokens,
        "repomap_tokens_total": repomap_tokens,
        "symbol_coverage": coverage,  # alias for human readers
        "missing_symbols": missing_symbols[:20],  # cap for output size
        "per_file": per_file,
    }

    Path("outputs.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in output.items() if k != "per_file"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
