"""Cross-sandbox metrics dashboard.

Walks every ACTIVE sandbox, finds the most recent run per
(hypothesis_id, hardware_class) pair under results/, and renders a unified
markdown table with an overall PASS/FAIL badge.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .metrics import ExpectedJson, Verdict
from .runner import list_all_sandboxes, load_expected


@dataclass
class DashboardRow:
    """One row in the dashboard — one (sandbox, hardware_class) pair."""

    sandbox_path: Path
    category: str
    expected: ExpectedJson
    hardware_class: str | None
    primary_median: float | None
    secondary_median: float | None
    verdict: Verdict | None
    timestamp_utc: str | None
    summary_path: Path | None


def _category_of(sandbox_path: Path, bench_root: Path) -> str:
    """Derive category from path, e.g. isolation/memory/mem0-v3 → 'memory'."""
    try:
        rel_parts = sandbox_path.relative_to(bench_root).parts
    except ValueError:
        return "?"
    if len(rel_parts) >= 2:
        return rel_parts[1]
    return "?"


def _threshold_str(expected: ExpectedJson) -> str:
    """Format the primary threshold for display (ASCII-only)."""
    t = expected.thresholds
    if t.confirm_at_least is not None:
        return f">= {t.confirm_at_least}"
    if t.confirm_at_most is not None:
        return f"<= {t.confirm_at_most}"
    return "-"


def _find_latest_summary_for(
    results_root: Path, hypothesis_id: str
) -> dict[str, dict]:
    """Return {hardware_class: parsed_summary} for the most recent run per hardware_class."""
    latest: dict[str, tuple[str, dict, Path]] = {}
    if not results_root.exists():
        return {}
    for summary_path in results_root.rglob("summary.json"):
        try:
            data = json.loads(summary_path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if data.get("hypothesis_id") != hypothesis_id:
            continue
        hw = data.get("hardware_class", "?")
        ts = data.get("timestamp_utc", "")
        existing = latest.get(hw)
        if existing is None or ts > existing[0]:
            latest[hw] = (ts, data, summary_path)
    return {hw: {"data": tup[1], "path": tup[2]} for hw, tup in latest.items()}


def collect_dashboard_rows(
    bench_root: Path, results_root: Path | None = None
) -> list[DashboardRow]:
    """Walk ACTIVE sandboxes and join with their latest results."""
    results_root = results_root or (bench_root / "results")
    sandboxes = (
        list_all_sandboxes(bench_root / "isolation")
        + list_all_sandboxes(bench_root / "combination")
    )

    rows: list[DashboardRow] = []
    for sandbox in sandboxes:
        try:
            expected = load_expected(sandbox)
        except Exception:  # noqa: BLE001
            continue
        if expected.status != "ACTIVE":
            continue

        category = _category_of(sandbox, bench_root)
        latest = _find_latest_summary_for(results_root, expected.hypothesis_id)

        if not latest:
            rows.append(
                DashboardRow(
                    sandbox_path=sandbox,
                    category=category,
                    expected=expected,
                    hardware_class=None,
                    primary_median=None,
                    secondary_median=None,
                    verdict=None,
                    timestamp_utc=None,
                    summary_path=None,
                )
            )
            continue

        for hw, info in latest.items():
            data = info["data"]
            try:
                verdict = Verdict(data.get("verdict"))
            except ValueError:
                verdict = None
            rows.append(
                DashboardRow(
                    sandbox_path=sandbox,
                    category=category,
                    expected=expected,
                    hardware_class=hw,
                    primary_median=data.get("primary_median"),
                    secondary_median=data.get("secondary_median"),
                    verdict=verdict,
                    timestamp_utc=data.get("timestamp_utc"),
                    summary_path=info["path"],
                )
            )

    rows.sort(key=lambda r: (r.category, r.expected.hypothesis_id, r.hardware_class or ""))
    return rows


def compute_overall_status(rows: list[DashboardRow]) -> tuple[str, dict[str, int]]:
    """Return ('PASS' or 'FAIL', verdict_counts).

    PASS only when every ACTIVE row has a CONFIRMED verdict. Rows without a
    run yet count against the badge (treated as INCONCLUSIVE).
    """
    counts = {"CONFIRMED": 0, "REFUTED": 0, "INCONCLUSIVE": 0, "NO_RUN": 0}
    for row in rows:
        if row.verdict is None:
            counts["NO_RUN"] += 1
        else:
            counts[row.verdict.value] += 1
    status = "PASS" if counts["CONFIRMED"] == len(rows) and rows else "FAIL"
    return status, counts


_VERDICT_BADGE = {
    "CONFIRMED": "**CONFIRMED**",
    "REFUTED": "**REFUTED**",
    "INCONCLUSIVE": "INCONCLUSIVE",
}


def render_markdown(rows: list[DashboardRow], *, status: str, counts: dict[str, int]) -> str:
    """Render the dashboard as a markdown document.

    ASCII-only output so the same string renders on GitHub *and* prints to
    Windows-legacy consoles without hitting cp1252 encoding errors.
    """
    parts = counts_to_summary(counts)
    badge = f"**[{status}]** {parts}"

    lines: list[str] = [
        "# OCM Bench: Metrics Dashboard",
        "",
        "_Auto-generated by `bench dashboard`. Do not edit by hand._",
        "",
        badge,
        "",
        "| Sandbox | Hypothesis | Category | Primary metric | Latest | Threshold | Verdict | Hardware | Run |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        sandbox_name = row.sandbox_path.name
        hypothesis = row.expected.hypothesis_id
        metric = row.expected.metric
        latest = (
            f"{row.primary_median:.3f}" if row.primary_median is not None else "-"
        )
        threshold = _threshold_str(row.expected)
        verdict = (
            _VERDICT_BADGE[row.verdict.value] if row.verdict else "(no run yet)"
        )
        hw = row.hardware_class or "-"
        ts = row.timestamp_utc or "-"
        lines.append(
            f"| `{sandbox_name}` | `{hypothesis}` | {row.category} | `{metric}` | "
            f"{latest} | {threshold} | {verdict} | `{hw}` | {ts} |"
        )

    return "\n".join(lines) + "\n"


def counts_to_summary(counts: dict[str, int]) -> str:
    """Format verdict counts: '4 CONFIRMED / 0 REFUTED / 0 INCONCLUSIVE / 1 no-run'."""
    parts = [
        f"{counts['CONFIRMED']} CONFIRMED",
        f"{counts['REFUTED']} REFUTED",
        f"{counts['INCONCLUSIVE']} INCONCLUSIVE",
    ]
    if counts.get("NO_RUN", 0):
        parts.append(f"{counts['NO_RUN']} no-run")
    return " / ".join(parts)
