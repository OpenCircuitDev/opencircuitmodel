"""Tests for sandbox structure validation in runner.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bench.runner import DryRunError, dry_run_sandbox, list_all_sandboxes, run_sandbox


def write_sandbox(
    root: Path,
    *,
    hypothesis_id: str = "test-h",
    claim: str = "A claim describing the hypothesis under test.",
    metric: str = "primary_pct",
    thresholds: dict | None = None,
    workload: str = "test.jsonl",
    compose: str | None = None,
) -> Path:
    """Write a complete 4-file sandbox at root/."""
    expected = {
        "hypothesis_id": hypothesis_id,
        "claim": claim,
        "metric": metric,
        "thresholds": thresholds or {"confirm_at_least": 80.0, "refute_below": 60.0},
        "workload": workload,
    }
    (root / "expected.json").write_text(json.dumps(expected))
    (root / "docker-compose.yml").write_text(
        compose
        or (
            "services:\n"
            "  bench:\n"
            "    image: python:3.11-slim\n"
            "    command: ['echo', 'noop']\n"
        )
    )
    (root / "bench.py").write_text("# placeholder\n")
    (root / "README.md").write_text("# Test sandbox\n")
    return root


def test_dry_run_passes_on_valid_sandbox(tmp_path: Path):
    sandbox = write_sandbox(tmp_path)
    expected = dry_run_sandbox(sandbox)
    assert expected.hypothesis_id == "test-h"


def test_dry_run_fails_when_expected_missing(tmp_path: Path):
    sandbox = write_sandbox(tmp_path)
    (sandbox / "expected.json").unlink()
    with pytest.raises(DryRunError) as exc:
        dry_run_sandbox(sandbox)
    assert "expected" in str(exc.value)


def test_dry_run_fails_on_invalid_compose(tmp_path: Path):
    sandbox = write_sandbox(tmp_path, compose="not: yaml: at: all: [")
    with pytest.raises(DryRunError):
        dry_run_sandbox(sandbox)


def test_dry_run_fails_on_compose_without_services(tmp_path: Path):
    sandbox = write_sandbox(tmp_path, compose="version: '3'\n")
    with pytest.raises(DryRunError) as exc:
        dry_run_sandbox(sandbox)
    assert "services" in str(exc.value)


def test_dry_run_fails_on_invalid_expected_schema(tmp_path: Path):
    sandbox = write_sandbox(tmp_path)
    (sandbox / "expected.json").write_text(json.dumps({"hypothesis_id": ""}))
    with pytest.raises(DryRunError):
        dry_run_sandbox(sandbox)


def test_list_all_sandboxes(tmp_path: Path):
    s1 = tmp_path / "isolation" / "category-a" / "tool-1"
    s1.mkdir(parents=True)
    write_sandbox(s1)

    s2 = tmp_path / "isolation" / "category-b" / "tool-2"
    s2.mkdir(parents=True)
    write_sandbox(s2, hypothesis_id="test-h-2")

    found = list_all_sandboxes(tmp_path)
    assert len(found) == 2
    assert s1 in found
    assert s2 in found


def test_run_sandbox_dry_run_returns_summary(tmp_path: Path):
    sandbox = write_sandbox(tmp_path)
    summary = run_sandbox(
        sandbox,
        hardware_class="cpu-only-32gb",
        repeats=3,
        out_dir=tmp_path / "results",
        dry_run=True,
    )
    assert summary.hypothesis_id == "test-h"
    assert summary.verdict.value == "INCONCLUSIVE"
    assert "DRY_RUN" in summary.verdict_reason
