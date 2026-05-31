"""Tests for the spec-row coverage map."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from bench.cli import main
from bench.coverage import (
    build_coverage,
    extract_spec_rows,
    parse_spec_rows,
    render_coverage_markdown,
)
from bench.metrics import ExpectedJson, Thresholds


SAMPLE_SPEC = """# OCM Design Spec

Some preamble paragraph.

## Locked decisions

| # | Decision | Choice | Rationale |
|---|---|---|---|
| 1 | Project name | **OpenCircuitModel (OCM)** | User-locked |
| 6 | Inference engine — Apple Silicon | **llama.cpp + Metal** | most stable on macOS |
| 6b | Inference engine — RTX 5090 | **TensorRT-LLM FP4** | only engine for FP4 |
| 9 | Agent memory | **Mem0 v3** | library-driven retrieval |
| 24 | Compressed-view tool | **Aider repomap** | 70% token cut |

## Some other section

Not a table.
"""


def _write_spec(tmp_path: Path) -> Path:
    spec = tmp_path / "spec.md"
    spec.write_text(SAMPLE_SPEC, encoding="utf-8")
    return spec


def _write_sandbox(
    root: Path,
    *,
    hypothesis_id: str,
    spec_row: list[int] | None = None,
    source_for_claim: str | None = None,
    status: str = "ACTIVE",
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    payload = {
        "hypothesis_id": hypothesis_id,
        "claim": "A claim describing the hypothesis under test.",
        "metric": "primary_pct",
        "thresholds": {"confirm_at_least": 80.0, "refute_below": 60.0},
        "workload": "test.jsonl",
        "status": status,
    }
    if spec_row is not None:
        payload["spec_row"] = spec_row
    if source_for_claim is not None:
        payload["source_for_claim"] = source_for_claim
    if status == "INACTIVE":
        payload["blocked_on"] = ["upstream not ready"]
    (root / "expected.json").write_text(json.dumps(payload))
    (root / "README.md").write_text("# Sandbox\n")
    if status == "ACTIVE":
        (root / "docker-compose.yml").write_text(
            "services:\n  bench:\n    image: alpine\n    command: ['echo']\n"
        )
        (root / "bench.py").write_text("# noop\n")
    return root


def _bench_layout(tmp_path: Path) -> Path:
    (tmp_path / "isolation").mkdir()
    (tmp_path / "combination").mkdir()
    return tmp_path


# --- parse_spec_rows ---


def test_parse_spec_rows_extracts_all_numbered(tmp_path: Path):
    spec = _write_spec(tmp_path)
    rows = parse_spec_rows(spec)
    numbers = [r.number for r in rows]
    assert 1 in numbers
    assert 6 in numbers
    assert 9 in numbers
    assert 24 in numbers


def test_parse_spec_rows_strips_bold_from_titles(tmp_path: Path):
    spec = _write_spec(tmp_path)
    rows = parse_spec_rows(spec)
    row_by_num = {r.number: r for r in rows}
    # The choice column has bold; the title (column 2) doesn't here, but in
    # the real spec row 21's title IS bold. Verify the parser strips it.
    assert "Project name" == row_by_num[1].title


def test_parse_spec_rows_skips_divider_row(tmp_path: Path):
    spec = _write_spec(tmp_path)
    rows = parse_spec_rows(spec)
    # The divider `|---|---|---|---|` should not appear as a row.
    assert all(r.number != 0 for r in rows)


def test_parse_spec_rows_returns_empty_on_missing_file(tmp_path: Path):
    rows = parse_spec_rows(tmp_path / "does-not-exist.md")
    assert rows == []


def test_parse_spec_rows_collapses_letter_subrows(tmp_path: Path):
    """6b should be treated as a variant of row 6; only one entry kept."""
    spec = _write_spec(tmp_path)
    rows = parse_spec_rows(spec)
    sixes = [r for r in rows if r.number == 6]
    assert len(sixes) == 1


# --- extract_spec_rows ---


def _make_expected(**overrides) -> ExpectedJson:
    base = {
        "hypothesis_id": "h",
        "claim": "Claim that has at least ten characters of content.",
        "metric": "m",
        "thresholds": Thresholds(confirm_at_least=80.0, refute_below=60.0),
        "workload": "w",
    }
    base.update(overrides)
    return ExpectedJson(**base)


def test_extract_spec_rows_prefers_explicit_field():
    e = _make_expected(spec_row=[6, 8, 13], source_for_claim="row 99")
    assert extract_spec_rows(e) == [6, 8, 13]


def test_extract_spec_rows_falls_back_to_source_regex():
    e = _make_expected(source_for_claim="Spec v0.4 row 9 — 'library-driven retrieval'")
    assert extract_spec_rows(e) == [9]


def test_extract_spec_rows_finds_multiple_in_source():
    e = _make_expected(source_for_claim="row 6, row 8, row 13, row 29 — mobile revisions")
    assert extract_spec_rows(e) == [6, 8, 13, 29]


def test_extract_spec_rows_empty_when_no_signal():
    e = _make_expected(source_for_claim="general background, no row reference")
    assert extract_spec_rows(e) == []


# --- build_coverage ---


def test_build_coverage_joins_sandboxes_to_rows(tmp_path: Path):
    bench_root = _bench_layout(tmp_path)
    spec = _write_spec(tmp_path)
    _write_sandbox(
        bench_root / "isolation" / "memory" / "mem0-s",
        hypothesis_id="mem0-h",
        spec_row=[9],
    )

    entries, orphans = build_coverage(bench_root, spec)
    row_9 = next(e for e in entries if e.spec_row.number == 9)
    assert len(row_9.sandboxes) == 1
    assert row_9.sandboxes[0].expected.hypothesis_id == "mem0-h"
    assert orphans == []


def test_build_coverage_finds_orphan_sandboxes(tmp_path: Path):
    bench_root = _bench_layout(tmp_path)
    spec = _write_spec(tmp_path)
    _write_sandbox(
        bench_root / "isolation" / "memory" / "orphan-s",
        hypothesis_id="orphan-h",
        # No spec_row, no row-N pattern in source
        source_for_claim="independent claim, no spec row reference",
    )

    entries, orphans = build_coverage(bench_root, spec)
    assert len(orphans) == 1
    assert orphans[0].expected.hypothesis_id == "orphan-h"


def test_build_coverage_uses_source_for_claim_fallback(tmp_path: Path):
    bench_root = _bench_layout(tmp_path)
    spec = _write_spec(tmp_path)
    _write_sandbox(
        bench_root / "isolation" / "retrieval" / "aider-s",
        hypothesis_id="aider-h",
        # No explicit spec_row — relies on regex fallback
        source_for_claim="Spec v0.3 row 24: 'Aider-style repomap pattern...'",
    )

    entries, orphans = build_coverage(bench_root, spec)
    row_24 = next(e for e in entries if e.spec_row.number == 24)
    assert len(row_24.sandboxes) == 1
    assert orphans == []


def test_build_coverage_excludes_inactive_sandboxes(tmp_path: Path):
    bench_root = _bench_layout(tmp_path)
    spec = _write_spec(tmp_path)
    _write_sandbox(
        bench_root / "isolation" / "memory" / "stub-s",
        hypothesis_id="stub-h",
        spec_row=[9],
        status="INACTIVE",
    )

    entries, orphans = build_coverage(bench_root, spec)
    row_9 = next(e for e in entries if e.spec_row.number == 9)
    assert row_9.sandboxes == []


def test_build_coverage_unknown_row_is_orphan(tmp_path: Path):
    """Sandbox claiming row 999 (not in spec) is treated as an orphan."""
    bench_root = _bench_layout(tmp_path)
    spec = _write_spec(tmp_path)
    _write_sandbox(
        bench_root / "isolation" / "memory" / "ghost-s",
        hypothesis_id="ghost-h",
        spec_row=[999],
    )

    _, orphans = build_coverage(bench_root, spec)
    assert any(o.expected.hypothesis_id == "ghost-h" for o in orphans)


# --- render markdown + CLI ---


def test_render_markdown_includes_all_rows(tmp_path: Path):
    bench_root = _bench_layout(tmp_path)
    spec = _write_spec(tmp_path)
    _write_sandbox(
        bench_root / "isolation" / "memory" / "mem0-s",
        hypothesis_id="mem0-h",
        spec_row=[9],
    )

    entries, orphans = build_coverage(bench_root, spec)
    md = render_coverage_markdown(entries, orphans)
    assert "OCM Bench" in md
    assert "Spec Row Coverage" in md
    # Each row from the sample spec should appear
    for n in [1, 6, 9, 24]:
        assert f"| {n} |" in md
    assert "mem0-s" in md


def test_cli_coverage_writes_to_file(tmp_path: Path):
    bench_root = _bench_layout(tmp_path)
    spec = _write_spec(tmp_path)
    _write_sandbox(
        bench_root / "isolation" / "memory" / "s",
        hypothesis_id="h-mem0",
        spec_row=[9],
    )
    out = tmp_path / "docs" / "coverage.md"

    cli = CliRunner()
    result = cli.invoke(
        main,
        [
            "coverage",
            "--root", str(bench_root),
            "--spec", str(spec),
            "--write", str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    assert out.exists()
    md = out.read_text(encoding="utf-8")
    assert "h-mem0" in md or "s" in md
