"""Tests for trend tracking — history.jsonl append on each run."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bench import runner as runner_module
from bench.metrics import HistoryRecord, RunResult
from bench.runner import _get_git_sha, run_sandbox


def _write_active_sandbox(root: Path, *, hypothesis_id: str = "trend-h") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    expected = {
        "hypothesis_id": hypothesis_id,
        "claim": "A claim describing the hypothesis under test.",
        "metric": "primary_pct",
        "thresholds": {"confirm_at_least": 80.0, "refute_below": 60.0},
        "workload": "test.jsonl",
    }
    (root / "expected.json").write_text(json.dumps(expected))
    (root / "docker-compose.yml").write_text(
        "services:\n  bench:\n    image: alpine\n    command: ['echo', 'noop']\n"
    )
    (root / "bench.py").write_text("# placeholder\n")
    (root / "README.md").write_text("# Trend sandbox\n")
    return root


def _fake_execute(sandbox_path, expected, *, repeat, out_dir, primary=85.0):
    """Stand-in for _execute_compose that skips Docker."""
    return RunResult(
        hypothesis_id=expected.hypothesis_id,
        repeat_index=repeat,
        primary_value=primary,
        secondary_value=None,
        duration_seconds=0.01,
        raw_path=None,
    )


def test_history_jsonl_created_after_run(tmp_path: Path, monkeypatch):
    sandbox = _write_active_sandbox(tmp_path / "sandbox")
    results = tmp_path / "results"

    monkeypatch.setattr(runner_module, "_execute_compose", _fake_execute)

    summary = run_sandbox(
        sandbox,
        hardware_class="cpu-only-32gb",
        repeats=3,
        out_dir=results,
        dry_run=False,
    )

    history_path = results / "history.jsonl"
    assert history_path.exists()
    lines = history_path.read_text().splitlines()
    assert len(lines) == 1

    record = HistoryRecord.model_validate_json(lines[0])
    assert record.hypothesis_id == "trend-h"
    assert record.hardware_class == "cpu-only-32gb"
    assert record.primary_median == summary.primary_median
    assert record.verdict.value == summary.verdict.value
    assert record.repeats == 3
    assert record.wall_clock_s >= 0.0
    assert record.git_sha  # always set, "unknown" if not in repo


def test_history_jsonl_appends_not_overwrites(tmp_path: Path, monkeypatch):
    sandbox = _write_active_sandbox(tmp_path / "sandbox")
    results = tmp_path / "results"

    monkeypatch.setattr(runner_module, "_execute_compose", _fake_execute)

    run_sandbox(sandbox, hardware_class="hw", repeats=1, out_dir=results)
    run_sandbox(sandbox, hardware_class="hw", repeats=1, out_dir=results)
    run_sandbox(sandbox, hardware_class="hw", repeats=1, out_dir=results)

    lines = (results / "history.jsonl").read_text().splitlines()
    assert len(lines) == 3
    for line in lines:
        HistoryRecord.model_validate_json(line)  # each parses cleanly


def test_history_not_written_on_dry_run(tmp_path: Path, monkeypatch):
    sandbox = _write_active_sandbox(tmp_path / "sandbox")
    results = tmp_path / "results"

    monkeypatch.setattr(runner_module, "_execute_compose", _fake_execute)

    run_sandbox(
        sandbox,
        hardware_class="hw",
        repeats=1,
        out_dir=results,
        dry_run=True,
    )

    assert not (results / "history.jsonl").exists()


def test_get_git_sha_returns_unknown_outside_repo(tmp_path: Path):
    """In a fresh tmp_path (not a git repo), git_sha falls back to 'unknown'."""
    sha = _get_git_sha(repo_hint=tmp_path)
    assert sha == "unknown"


def test_get_git_sha_returns_value_in_repo():
    """Inside the actual ocm repo, git_sha returns a short SHA (7+ hex chars)."""
    sha = _get_git_sha()
    if sha == "unknown":
        pytest.skip("not running inside a git repo")
    assert len(sha) >= 7
    assert all(c in "0123456789abcdef" for c in sha)


def test_history_record_captures_secondary_median(tmp_path: Path, monkeypatch):
    sandbox = _write_active_sandbox(tmp_path / "sandbox")
    results = tmp_path / "results"

    def with_secondary(sandbox_path, expected, *, repeat, out_dir):
        return RunResult(
            hypothesis_id=expected.hypothesis_id,
            repeat_index=repeat,
            primary_value=85.0,
            secondary_value=42.0,
            duration_seconds=0.01,
            raw_path=None,
        )

    monkeypatch.setattr(runner_module, "_execute_compose", with_secondary)

    run_sandbox(sandbox, hardware_class="hw", repeats=3, out_dir=results)

    line = (results / "history.jsonl").read_text().splitlines()[0]
    record = HistoryRecord.model_validate_json(line)
    assert record.secondary_median == 42.0
