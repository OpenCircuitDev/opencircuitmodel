"""Tests for the `bench run-all` CLI command.

Focuses on the orchestration logic — sandbox iteration, INACTIVE skip path,
exit codes — without invoking Docker. Active-sandbox execution would require
a running docker daemon and is exercised in integration tests on real hardware.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from bench.cli import main


def _write_inactive(root: Path, *, hypothesis_id: str) -> Path:
    expected = {
        "hypothesis_id": hypothesis_id,
        "claim": "A claim describing a hypothesis blocked on future work.",
        "metric": "primary_pct",
        "thresholds": {"confirm_at_least": 80.0, "refute_below": 60.0},
        "workload": "test.jsonl",
        "status": "INACTIVE",
        "blocked_on": ["upstream not ready"],
    }
    (root / "expected.json").write_text(json.dumps(expected))
    (root / "README.md").write_text("# Inactive\n")
    return root


def _bench_layout(tmp_path: Path) -> Path:
    """Create a minimal bench-root layout with `isolation/` + `combination/`."""
    iso = tmp_path / "isolation" / "category" / "stub"
    iso.mkdir(parents=True)
    _write_inactive(iso, hypothesis_id="stub-h")

    (tmp_path / "combination").mkdir()
    return tmp_path


def test_run_all_skips_all_inactive(tmp_path: Path):
    bench_root = _bench_layout(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "run-all",
            "--hardware-class", "cpu-only-32gb",
            "--repeats", "1",
            "--root", str(bench_root),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "INACTIVE" in result.output
    assert "0 errored" in result.output
    assert "0 CONFIRMED" in result.output


def test_run_all_empty_bench_dir(tmp_path: Path):
    """No sandboxes anywhere → graceful exit."""
    (tmp_path / "isolation").mkdir()
    (tmp_path / "combination").mkdir()
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "run-all",
            "--hardware-class", "cpu-only-32gb",
            "--root", str(tmp_path),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "No sandboxes found" in result.output


def test_run_all_requires_hardware_class(tmp_path: Path):
    """--hardware-class is required (not optional)."""
    bench_root = _bench_layout(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["run-all", "--root", str(bench_root)])
    assert result.exit_code != 0
    assert "hardware-class" in result.output.lower() or "required" in result.output.lower()
