"""Tests for the bench dashboard subcommand and dashboard.py helpers."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from bench.cli import main
from bench.dashboard import (
    collect_dashboard_rows,
    compute_overall_status,
    render_markdown,
)


def _write_sandbox(
    root: Path,
    *,
    hypothesis_id: str,
    status: str = "ACTIVE",
    confirm_at_least: float = 80.0,
    metric: str = "primary_pct",
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    payload = {
        "hypothesis_id": hypothesis_id,
        "claim": "A claim describing the hypothesis under test.",
        "metric": metric,
        "thresholds": {"confirm_at_least": confirm_at_least, "refute_below": 60.0},
        "workload": "test.jsonl",
        "status": status,
    }
    if status == "INACTIVE":
        payload["blocked_on"] = ["upstream not ready"]
    (root / "expected.json").write_text(json.dumps(payload))
    (root / "README.md").write_text("# Sandbox\n")
    if status == "ACTIVE":
        (root / "docker-compose.yml").write_text(
            "services:\n  bench:\n    image: alpine\n    command: ['echo', 'noop']\n"
        )
        (root / "bench.py").write_text("# noop\n")
    return root


def _write_summary(
    results_root: Path,
    *,
    hypothesis_id: str,
    hardware_class: str,
    primary_median: float,
    timestamp: str,
    verdict: str = "CONFIRMED",
) -> Path:
    run_dir = results_root / f"{timestamp}-{hypothesis_id}-{hardware_class}"
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "hypothesis_id": hypothesis_id,
        "hardware_class": hardware_class,
        "timestamp_utc": timestamp,
        "expected": {},
        "runs": [],
        "primary_median": primary_median,
        "primary_std": None,
        "secondary_median": None,
        "secondary_std": None,
        "verdict": verdict,
        "verdict_reason": "test",
    }
    path = run_dir / "summary.json"
    path.write_text(json.dumps(payload))
    return path


def _bench_layout(tmp_path: Path) -> Path:
    """Create a minimal bench-root with isolation/ + combination/."""
    (tmp_path / "isolation").mkdir()
    (tmp_path / "combination").mkdir()
    return tmp_path


def test_collect_rows_excludes_inactive(tmp_path: Path):
    bench_root = _bench_layout(tmp_path)
    _write_sandbox(bench_root / "isolation" / "memory" / "active-s", hypothesis_id="h-active")
    _write_sandbox(
        bench_root / "isolation" / "memory" / "inactive-s",
        hypothesis_id="h-inactive",
        status="INACTIVE",
    )

    rows = collect_dashboard_rows(bench_root)
    assert len(rows) == 1
    assert rows[0].expected.hypothesis_id == "h-active"
    assert rows[0].category == "memory"


def test_collect_rows_picks_latest_per_hardware(tmp_path: Path):
    bench_root = _bench_layout(tmp_path)
    _write_sandbox(bench_root / "isolation" / "memory" / "s", hypothesis_id="h1")
    results = bench_root / "results"
    _write_summary(
        results, hypothesis_id="h1", hardware_class="rtx-4090",
        primary_median=80.0, timestamp="2026-01-01T00-00-00Z",
    )
    _write_summary(
        results, hypothesis_id="h1", hardware_class="rtx-4090",
        primary_median=85.0, timestamp="2026-02-01T00-00-00Z",
    )

    rows = collect_dashboard_rows(bench_root)
    assert len(rows) == 1
    assert rows[0].primary_median == 85.0
    assert rows[0].timestamp_utc == "2026-02-01T00-00-00Z"


def test_collect_rows_splits_by_hardware_class(tmp_path: Path):
    bench_root = _bench_layout(tmp_path)
    _write_sandbox(bench_root / "isolation" / "memory" / "s", hypothesis_id="h1")
    results = bench_root / "results"
    _write_summary(
        results, hypothesis_id="h1", hardware_class="rtx-4090",
        primary_median=85.0, timestamp="2026-01-01T00-00-00Z",
    )
    _write_summary(
        results, hypothesis_id="h1", hardware_class="m4-pro",
        primary_median=70.0, timestamp="2026-01-01T00-00-00Z",
        verdict="INCONCLUSIVE",
    )

    rows = collect_dashboard_rows(bench_root)
    assert len(rows) == 2
    by_hw = {r.hardware_class: r for r in rows}
    assert by_hw["rtx-4090"].verdict.value == "CONFIRMED"
    assert by_hw["m4-pro"].verdict.value == "INCONCLUSIVE"


def test_no_runs_yet_shows_row_with_none(tmp_path: Path):
    bench_root = _bench_layout(tmp_path)
    _write_sandbox(bench_root / "isolation" / "memory" / "s", hypothesis_id="h-fresh")

    rows = collect_dashboard_rows(bench_root)
    assert len(rows) == 1
    assert rows[0].verdict is None
    assert rows[0].primary_median is None


def test_overall_status_pass_when_all_confirmed(tmp_path: Path):
    bench_root = _bench_layout(tmp_path)
    _write_sandbox(bench_root / "isolation" / "memory" / "s1", hypothesis_id="h1")
    _write_sandbox(bench_root / "isolation" / "memory" / "s2", hypothesis_id="h2")
    results = bench_root / "results"
    _write_summary(
        results, hypothesis_id="h1", hardware_class="hw",
        primary_median=85.0, timestamp="2026-01-01T00-00-00Z",
    )
    _write_summary(
        results, hypothesis_id="h2", hardware_class="hw",
        primary_median=90.0, timestamp="2026-01-01T00-00-00Z",
    )

    rows = collect_dashboard_rows(bench_root)
    status, counts = compute_overall_status(rows)
    assert status == "PASS"
    assert counts["CONFIRMED"] == 2


def test_overall_status_fail_when_any_refuted(tmp_path: Path):
    bench_root = _bench_layout(tmp_path)
    _write_sandbox(bench_root / "isolation" / "memory" / "s1", hypothesis_id="h1")
    _write_sandbox(bench_root / "isolation" / "memory" / "s2", hypothesis_id="h2")
    results = bench_root / "results"
    _write_summary(
        results, hypothesis_id="h1", hardware_class="hw",
        primary_median=85.0, timestamp="2026-01-01T00-00-00Z",
    )
    _write_summary(
        results, hypothesis_id="h2", hardware_class="hw",
        primary_median=40.0, timestamp="2026-01-01T00-00-00Z",
        verdict="REFUTED",
    )

    rows = collect_dashboard_rows(bench_root)
    status, counts = compute_overall_status(rows)
    assert status == "FAIL"
    assert counts["REFUTED"] == 1


def test_overall_status_fail_when_no_runs(tmp_path: Path):
    bench_root = _bench_layout(tmp_path)
    _write_sandbox(bench_root / "isolation" / "memory" / "s", hypothesis_id="h-fresh")

    rows = collect_dashboard_rows(bench_root)
    status, _ = compute_overall_status(rows)
    assert status == "FAIL"


def test_render_markdown_contains_badge_and_rows(tmp_path: Path):
    bench_root = _bench_layout(tmp_path)
    _write_sandbox(bench_root / "isolation" / "memory" / "my-sandbox", hypothesis_id="h1")
    results = bench_root / "results"
    _write_summary(
        results, hypothesis_id="h1", hardware_class="rtx-4090",
        primary_median=85.0, timestamp="2026-01-01T00-00-00Z",
    )

    rows = collect_dashboard_rows(bench_root)
    status, counts = compute_overall_status(rows)
    md = render_markdown(rows, status=status, counts=counts)
    assert "OCM Bench" in md
    assert "[PASS]" in md
    assert "my-sandbox" in md
    assert "85.000" in md
    assert "rtx-4090" in md
    assert "CONFIRMED" in md


def test_cli_dashboard_writes_to_file(tmp_path: Path):
    bench_root = _bench_layout(tmp_path)
    _write_sandbox(bench_root / "isolation" / "memory" / "s", hypothesis_id="h1")
    results = bench_root / "results"
    _write_summary(
        results, hypothesis_id="h1", hardware_class="hw",
        primary_median=85.0, timestamp="2026-01-01T00-00-00Z",
    )
    out_path = tmp_path / "docs" / "metrics.md"

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["dashboard", "--root", str(bench_root), "--write", str(out_path)],
    )
    assert result.exit_code == 0, result.output
    assert out_path.exists()
    md = out_path.read_text()
    assert "OCM Bench" in md
    assert "h1" in md


def test_cli_dashboard_check_exits_1_on_refuted(tmp_path: Path):
    bench_root = _bench_layout(tmp_path)
    _write_sandbox(bench_root / "isolation" / "memory" / "s", hypothesis_id="h1")
    results = bench_root / "results"
    _write_summary(
        results, hypothesis_id="h1", hardware_class="hw",
        primary_median=40.0, timestamp="2026-01-01T00-00-00Z",
        verdict="REFUTED",
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["dashboard", "--root", str(bench_root), "--check"],
    )
    assert result.exit_code == 1


def test_cli_dashboard_check_passes_when_all_confirmed(tmp_path: Path):
    bench_root = _bench_layout(tmp_path)
    _write_sandbox(bench_root / "isolation" / "memory" / "s", hypothesis_id="h1")
    results = bench_root / "results"
    _write_summary(
        results, hypothesis_id="h1", hardware_class="hw",
        primary_median=85.0, timestamp="2026-01-01T00-00-00Z",
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["dashboard", "--root", str(bench_root), "--check"],
    )
    assert result.exit_code == 0, result.output
