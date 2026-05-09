"""Blind-label evaluator inputs to eliminate bias on subjective comparisons."""

from __future__ import annotations

import json
import random
import uuid
from pathlib import Path

REVEAL_THRESHOLD = 20  # Minimum evaluator records before mapping is revealed


class RevealTooEarlyError(Exception):
    """Raised when reveal_mapping is called before REVEAL_THRESHOLD records exist."""


def anonymize_outputs(
    outputs: dict[str, str], *, seed: int | None = None
) -> tuple[list[tuple[str, str]], dict[str, str]]:
    """Map tool-name -> output dict to (label, output) pairs + label-to-tool mapping.

    Pairs are shuffled deterministically by seed; the mapping is stored separately
    so evaluators see only blind labels until threshold reveal.
    """
    rng = random.Random(seed)
    items: list[tuple[str, str, str]] = []
    for tool, output in outputs.items():
        label = uuid.uuid4().hex[:8]
        items.append((label, output, tool))
    rng.shuffle(items)
    pairs = [(label, output) for label, output, _ in items]
    mapping = {label: tool for label, _, tool in items}
    return pairs, mapping


def record_evaluator_choice(
    record_path: Path, *, blind_label: str, choice: str, evaluator_id: str
) -> None:
    """Append an evaluator's choice to the record file."""
    record_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "blind_label": blind_label,
        "choice": choice,
        "evaluator_id": evaluator_id,
    }
    with record_path.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def count_records(record_path: Path) -> int:
    """Number of evaluator records in the file."""
    if not record_path.exists():
        return 0
    return sum(1 for line in record_path.read_text().splitlines() if line.strip())


def reveal_mapping(record_path: Path, mapping_path: Path) -> dict[str, str]:
    """Reveal label-to-tool mapping ONLY if >= REVEAL_THRESHOLD records exist."""
    n = count_records(record_path)
    if n < REVEAL_THRESHOLD:
        raise RevealTooEarlyError(
            f"only {n} evaluator records exist; need >= {REVEAL_THRESHOLD} before reveal"
        )
    return json.loads(mapping_path.read_text())
