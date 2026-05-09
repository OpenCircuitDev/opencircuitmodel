"""Retro-sync analysis: compare runs across time, detect regressions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .metrics import SandboxSummary


@dataclass
class HistoryEntry:
    timestamp_utc: str
    hypothesis_id: str
    hardware_class: str
    primary_median: float
    verdict: str
    summary_path: Path


@dataclass
class Regression:
    hypothesis_id: str
    hardware_class: str
    from_value: float
    to_value: float
    delta_pp: float
    from_timestamp: str
    to_timestamp: str


def load_history(results_root: Path) -> list[HistoryEntry]:
    """Walk results/ and return all SandboxSummary entries chronologically."""
    entries: list[HistoryEntry] = []
    for summary_path in results_root.rglob("summary.json"):
        try:
            data = json.loads(summary_path.read_text())
            entries.append(
                HistoryEntry(
                    timestamp_utc=data["timestamp_utc"],
                    hypothesis_id=data["hypothesis_id"],
                    hardware_class=data["hardware_class"],
                    primary_median=data["primary_median"],
                    verdict=data["verdict"],
                    summary_path=summary_path,
                )
            )
        except (json.JSONDecodeError, KeyError):
            continue
    entries.sort(key=lambda e: e.timestamp_utc)
    return entries


def filter_history(
    entries: list[HistoryEntry],
    *,
    hypothesis_id: str | None = None,
    hardware_class: str | None = None,
    limit: int | None = None,
) -> list[HistoryEntry]:
    filtered = entries
    if hypothesis_id:
        filtered = [e for e in filtered if e.hypothesis_id == hypothesis_id]
    if hardware_class:
        filtered = [e for e in filtered if e.hardware_class == hardware_class]
    if limit:
        filtered = filtered[-limit:]
    return filtered


def detect_regressions(
    entries: list[HistoryEntry], *, threshold_pp: float = 5.0
) -> list[Regression]:
    """Flag drops > threshold_pp between consecutive runs of the same hypothesis+hardware."""
    by_key: dict[tuple[str, str], list[HistoryEntry]] = {}
    for e in entries:
        by_key.setdefault((e.hypothesis_id, e.hardware_class), []).append(e)

    regressions: list[Regression] = []
    for (hyp, hw), runs in by_key.items():
        runs.sort(key=lambda x: x.timestamp_utc)
        for prev, curr in zip(runs, runs[1:], strict=False):
            delta = curr.primary_median - prev.primary_median
            if delta < -threshold_pp:
                regressions.append(
                    Regression(
                        hypothesis_id=hyp,
                        hardware_class=hw,
                        from_value=prev.primary_median,
                        to_value=curr.primary_median,
                        delta_pp=delta,
                        from_timestamp=prev.timestamp_utc,
                        to_timestamp=curr.timestamp_utc,
                    )
                )
    return regressions


def retro_sync_report(
    results_root: Path,
    *,
    hypothesis_id: str | None = None,
    hardware_class: str | None = None,
    limit: int = 20,
) -> str:
    """Human-readable report for `bench report`."""
    entries = load_history(results_root)
    filtered = filter_history(
        entries, hypothesis_id=hypothesis_id, hardware_class=hardware_class, limit=limit
    )
    if not filtered:
        return "No matching benchmark runs found."

    lines = [f"Found {len(filtered)} runs:"]
    for e in filtered:
        lines.append(
            f"  {e.timestamp_utc}  {e.hypothesis_id:<40s}  {e.hardware_class:<25s}  "
            f"value={e.primary_median:.3f}  {e.verdict}"
        )

    regressions = detect_regressions(filtered)
    if regressions:
        lines.append("")
        lines.append(f"Regressions detected ({len(regressions)}):")
        for r in regressions:
            lines.append(
                f"  {r.hypothesis_id} @ {r.hardware_class}: "
                f"{r.from_value:.3f} -> {r.to_value:.3f} "
                f"(Δ {r.delta_pp:.2f}pp) between {r.from_timestamp} and {r.to_timestamp}"
            )
    return "\n".join(lines)


def regression_summary(
    summary_a: SandboxSummary, summary_b: SandboxSummary, *, threshold_pp: float = 5.0
) -> Regression | None:
    """Compare two summaries directly. Returns Regression if delta exceeds threshold."""
    if summary_a.hypothesis_id != summary_b.hypothesis_id:
        return None
    if summary_a.hardware_class != summary_b.hardware_class:
        return None
    delta = summary_b.primary_median - summary_a.primary_median
    if delta < -threshold_pp:
        return Regression(
            hypothesis_id=summary_a.hypothesis_id,
            hardware_class=summary_a.hardware_class,
            from_value=summary_a.primary_median,
            to_value=summary_b.primary_median,
            delta_pp=delta,
            from_timestamp=summary_a.timestamp_utc,
            to_timestamp=summary_b.timestamp_utc,
        )
    return None
