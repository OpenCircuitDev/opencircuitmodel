"""Tests for verdict logic in metrics.py."""

from __future__ import annotations

from bench.metrics import ExpectedJson, Thresholds, Verdict, decide_verdict


def make_expected(thresholds: dict, **overrides) -> ExpectedJson:
    base = {
        "hypothesis_id": "test-hypothesis",
        "claim": "Test claim that has at least ten characters of text.",
        "metric": "test_metric",
        "thresholds": Thresholds(**thresholds),
        "workload": "test.jsonl",
    }
    base.update(overrides)
    return ExpectedJson(**base)


def test_confirm_at_least_passes():
    e = make_expected({"confirm_at_least": 80.0, "refute_below": 60.0})
    v, _ = decide_verdict(85.0, e)
    assert v == Verdict.CONFIRMED


def test_refute_below_classifies_refuted():
    e = make_expected({"confirm_at_least": 80.0, "refute_below": 60.0})
    v, _ = decide_verdict(50.0, e)
    assert v == Verdict.REFUTED


def test_inconclusive_between_thresholds():
    e = make_expected({"confirm_at_least": 80.0, "refute_below": 60.0})
    v, _ = decide_verdict(70.0, e)
    assert v == Verdict.INCONCLUSIVE


def test_confirm_at_most_passes():
    e = make_expected({"confirm_at_most": 1000.0, "refute_above": 2000.0})
    v, _ = decide_verdict(800.0, e)
    assert v == Verdict.CONFIRMED


def test_refute_above_classifies_refuted():
    e = make_expected({"confirm_at_most": 1000.0, "refute_above": 2000.0})
    v, _ = decide_verdict(2500.0, e)
    assert v == Verdict.REFUTED


def test_secondary_threshold_can_demote_to_inconclusive():
    e = make_expected(
        {"confirm_at_least": 80.0, "refute_below": 60.0},
        secondary_metric="latency_ms",
        secondary_thresholds=Thresholds(confirm_at_most=1000.0, refute_above=5000.0),
    )
    v, _ = decide_verdict(85.0, e, secondary_median=2000.0)
    assert v == Verdict.INCONCLUSIVE


def test_secondary_threshold_can_demote_to_refuted():
    e = make_expected(
        {"confirm_at_least": 80.0, "refute_below": 60.0},
        secondary_metric="latency_ms",
        secondary_thresholds=Thresholds(confirm_at_most=1000.0, refute_above=5000.0),
    )
    v, _ = decide_verdict(85.0, e, secondary_median=6000.0)
    assert v == Verdict.REFUTED


def test_no_thresholds_yields_inconclusive():
    e = make_expected({})
    v, _ = decide_verdict(50.0, e)
    assert v == Verdict.INCONCLUSIVE
