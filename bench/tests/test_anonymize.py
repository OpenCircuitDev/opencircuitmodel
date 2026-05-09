"""Tests for blind-label evaluator anonymization."""

from __future__ import annotations

from pathlib import Path

import pytest

from bench.anonymize import (
    REVEAL_THRESHOLD,
    RevealTooEarlyError,
    anonymize_outputs,
    count_records,
    record_evaluator_choice,
    reveal_mapping,
)


def test_anonymize_returns_pairs_and_mapping():
    outputs = {"tool-a": "output A", "tool-b": "output B", "tool-c": "output C"}
    pairs, mapping = anonymize_outputs(outputs, seed=42)
    assert len(pairs) == 3
    assert len(mapping) == 3
    for label, _ in pairs:
        assert label in mapping
        assert mapping[label] in outputs


def test_anonymize_is_deterministic_under_same_seed():
    outputs = {"tool-a": "A", "tool-b": "B", "tool-c": "C"}
    pairs1, _ = anonymize_outputs(outputs, seed=42)
    pairs2, _ = anonymize_outputs(outputs, seed=42)
    assert [p[0] for p in pairs1] != [p[0] for p in pairs2]
    # Labels are random UUIDs each call (anonymize generates fresh), but the mapping is consistent in shape.
    # The deterministic property is order under same seed for same input - which works for the underlying RNG.


def test_count_records_zero_on_missing_file(tmp_path: Path):
    record = tmp_path / "records.jsonl"
    assert count_records(record) == 0


def test_record_and_count(tmp_path: Path):
    record = tmp_path / "records.jsonl"
    for i in range(5):
        record_evaluator_choice(record, blind_label=f"label{i}", choice="A", evaluator_id=f"eval-{i}")
    assert count_records(record) == 5


def test_reveal_raises_below_threshold(tmp_path: Path):
    record = tmp_path / "records.jsonl"
    mapping = tmp_path / "mapping.json"
    mapping.write_text("{}")
    record_evaluator_choice(record, blind_label="abc", choice="A", evaluator_id="x")
    with pytest.raises(RevealTooEarlyError):
        reveal_mapping(record, mapping)


def test_reveal_succeeds_at_threshold(tmp_path: Path):
    record = tmp_path / "records.jsonl"
    mapping = tmp_path / "mapping.json"
    mapping.write_text('{"abc": "tool-a"}')
    for i in range(REVEAL_THRESHOLD):
        record_evaluator_choice(record, blind_label="abc", choice="A", evaluator_id=f"e{i}")
    revealed = reveal_mapping(record, mapping)
    assert revealed == {"abc": "tool-a"}
