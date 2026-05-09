"""Tests for retro-sync regression detection."""

from __future__ import annotations

import json
from pathlib import Path

from bench.compare import detect_regressions, load_history


def write_summary(
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
    summary_path = run_dir / "summary.json"
    summary_path.write_text(json.dumps(payload))
    return summary_path


def test_load_history_returns_chronological(tmp_path: Path):
    write_summary(
        tmp_path, hypothesis_id="h1", hardware_class="hw1",
        primary_median=80.0, timestamp="2026-01-01T00-00-00Z",
    )
    write_summary(
        tmp_path, hypothesis_id="h1", hardware_class="hw1",
        primary_median=85.0, timestamp="2026-02-01T00-00-00Z",
    )

    entries = load_history(tmp_path)
    assert len(entries) == 2
    assert entries[0].timestamp_utc < entries[1].timestamp_utc


def test_detect_regressions_flags_drop(tmp_path: Path):
    write_summary(
        tmp_path, hypothesis_id="h1", hardware_class="hw1",
        primary_median=85.0, timestamp="2026-01-01T00-00-00Z",
    )
    write_summary(
        tmp_path, hypothesis_id="h1", hardware_class="hw1",
        primary_median=70.0, timestamp="2026-02-01T00-00-00Z",
    )

    entries = load_history(tmp_path)
    regressions = detect_regressions(entries, threshold_pp=5.0)
    assert len(regressions) == 1
    assert regressions[0].hypothesis_id == "h1"
    assert regressions[0].delta_pp == -15.0


def test_detect_regressions_ignores_small_deltas(tmp_path: Path):
    write_summary(
        tmp_path, hypothesis_id="h1", hardware_class="hw1",
        primary_median=85.0, timestamp="2026-01-01T00-00-00Z",
    )
    write_summary(
        tmp_path, hypothesis_id="h1", hardware_class="hw1",
        primary_median=82.0, timestamp="2026-02-01T00-00-00Z",
    )

    entries = load_history(tmp_path)
    regressions = detect_regressions(entries, threshold_pp=5.0)
    assert len(regressions) == 0


def test_detect_regressions_ignores_improvements(tmp_path: Path):
    write_summary(
        tmp_path, hypothesis_id="h1", hardware_class="hw1",
        primary_median=70.0, timestamp="2026-01-01T00-00-00Z",
    )
    write_summary(
        tmp_path, hypothesis_id="h1", hardware_class="hw1",
        primary_median=85.0, timestamp="2026-02-01T00-00-00Z",
    )

    entries = load_history(tmp_path)
    regressions = detect_regressions(entries, threshold_pp=5.0)
    assert len(regressions) == 0


def test_separate_hardware_classes_dont_cross_contaminate(tmp_path: Path):
    write_summary(
        tmp_path, hypothesis_id="h1", hardware_class="rtx-4090",
        primary_median=85.0, timestamp="2026-01-01T00-00-00Z",
    )
    write_summary(
        tmp_path, hypothesis_id="h1", hardware_class="m4-pro",
        primary_median=70.0, timestamp="2026-02-01T00-00-00Z",
    )

    entries = load_history(tmp_path)
    regressions = detect_regressions(entries, threshold_pp=5.0)
    assert len(regressions) == 0
