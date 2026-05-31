"""Spec-row coverage map: which spec decisions have validating benchmarks?

Joins three sources into a single markdown table:
1. Spec rows parsed from the OCM design-spec markdown.
2. Sandboxes' declared spec_row field (or regex fallback on source_for_claim).
3. Latest verdict per sandbox (via dashboard.collect_dashboard_rows).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .dashboard import DashboardRow, collect_dashboard_rows
from .metrics import ExpectedJson, Verdict


_SPEC_ROW_FALLBACK_RE = re.compile(r"row\s+(\d+)", re.IGNORECASE)
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")


@dataclass
class SpecRow:
    """One row from the spec's locked-decisions table."""

    number: int
    raw_number: str  # preserves "6b" etc.
    title: str


@dataclass
class CoverageEntry:
    """One row in the coverage map."""

    spec_row: SpecRow
    sandboxes: list[DashboardRow] = field(default_factory=list)

    @property
    def best_verdict(self) -> Verdict | None:
        """Return the strongest verdict among sandboxes claiming this row.

        CONFIRMED > INCONCLUSIVE > REFUTED > None. A row counts as validated
        as soon as at least one sandbox CONFIRMs it.
        """
        priority = {
            Verdict.CONFIRMED: 3,
            Verdict.INCONCLUSIVE: 2,
            Verdict.REFUTED: 1,
        }
        best: Verdict | None = None
        best_pri = 0
        for sb in self.sandboxes:
            if sb.verdict is None:
                continue
            pri = priority.get(sb.verdict, 0)
            if pri > best_pri:
                best = sb.verdict
                best_pri = pri
        return best


def parse_spec_rows(spec_path: Path) -> list[SpecRow]:
    """Parse a spec markdown file for numbered decision rows.

    Rows look like `| 9 | Title | Choice | Rationale |`. The first cell must
    be a number (with optional letter suffix like "6b"). Header/divider rows
    are skipped automatically because their first cell isn't a digit.
    """
    rows: list[SpecRow] = []
    if not spec_path.exists():
        return rows
    seen: set[int] = set()
    for line in spec_path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        first = cells[0]
        match = re.match(r"^(\d+)([a-z]?)$", first)
        if not match:
            continue
        number = int(match.group(1))
        raw_number = first
        title = _BOLD_RE.sub(r"\1", cells[1]).strip()
        # If a row number appears twice (e.g. "6" then "6b"), keep the first
        # canonical entry — sub-letter rows tend to be variants of the parent.
        if number in seen:
            continue
        seen.add(number)
        rows.append(SpecRow(number=number, raw_number=raw_number, title=title))
    return rows


def extract_spec_rows(expected: ExpectedJson) -> list[int]:
    """Return spec rows this sandbox claims to validate.

    Prefers the explicit `spec_row` field. Falls back to regex-parsing
    `source_for_claim` for sandboxes that haven't been backfilled yet.
    """
    if expected.spec_row:
        return list(expected.spec_row)
    source = expected.source_for_claim or ""
    return [int(m) for m in _SPEC_ROW_FALLBACK_RE.findall(source)]


def build_coverage(
    bench_root: Path,
    spec_path: Path,
    results_root: Path | None = None,
) -> tuple[list[CoverageEntry], list[DashboardRow]]:
    """Build the coverage join.

    Returns (entries_by_spec_row, orphan_sandboxes). Orphans are ACTIVE
    sandboxes whose spec_row resolves to an empty list — they validate
    something not (yet) numbered in the spec.
    """
    spec_rows = parse_spec_rows(spec_path)
    dashboard_rows = collect_dashboard_rows(bench_root, results_root)

    entries = {row.number: CoverageEntry(spec_row=row) for row in spec_rows}
    orphans: list[DashboardRow] = []

    seen_paths: set[Path] = set()
    for db_row in dashboard_rows:
        rows_claimed = extract_spec_rows(db_row.expected)
        if not rows_claimed:
            if db_row.sandbox_path not in seen_paths:
                orphans.append(db_row)
                seen_paths.add(db_row.sandbox_path)
            continue
        for row_num in rows_claimed:
            entry = entries.get(row_num)
            if entry is None:
                # Sandbox references a row not in the spec — surface it as orphan too
                if db_row.sandbox_path not in seen_paths:
                    orphans.append(db_row)
                    seen_paths.add(db_row.sandbox_path)
                continue
            entry.sandboxes.append(db_row)

    return list(entries.values()), orphans


_VERDICT_LABEL = {
    Verdict.CONFIRMED: "**CONFIRMED**",
    Verdict.REFUTED: "**REFUTED**",
    Verdict.INCONCLUSIVE: "INCONCLUSIVE",
}


def render_coverage_markdown(
    entries: list[CoverageEntry],
    orphans: list[DashboardRow],
) -> str:
    """Render the coverage map as markdown."""
    validated = sum(1 for e in entries if e.best_verdict == Verdict.CONFIRMED)
    has_sandbox = sum(1 for e in entries if e.sandboxes)
    total = len(entries)

    lines: list[str] = [
        "# OCM Bench: Spec Row Coverage",
        "",
        "_Auto-generated by `bench coverage`. Do not edit by hand._",
        "",
        f"**Spec rows:** {total} total | **with a sandbox:** {has_sandbox} "
        f"| **CONFIRMED:** {validated}",
        "",
        "| Row | Decision title | Sandbox(es) | Best verdict |",
        "|---|---|---|---|",
    ]
    for entry in entries:
        row = entry.spec_row
        if entry.sandboxes:
            sandbox_str = "<br>".join(
                f"`{db.sandbox_path.name}`" for db in entry.sandboxes
            )
            verdict = entry.best_verdict
            verdict_str = _VERDICT_LABEL.get(verdict, "(no run yet)") if verdict else "(no run yet)"
        else:
            sandbox_str = "_(none)_"
            verdict_str = "—"
        lines.append(
            f"| {row.raw_number} | {row.title} | {sandbox_str} | {verdict_str} |"
        )

    if orphans:
        lines.extend(
            [
                "",
                "## Orphan sandboxes",
                "",
                "_ACTIVE sandboxes whose `spec_row` field or `source_for_claim` "
                "did not resolve to a known spec row._",
                "",
                "| Sandbox | Hypothesis | Source-for-claim hint |",
                "|---|---|---|",
            ]
        )
        for db in orphans:
            source = (db.expected.source_for_claim or "").replace("\n", " ").strip()
            if len(source) > 80:
                source = source[:77] + "..."
            lines.append(
                f"| `{db.sandbox_path.name}` | `{db.expected.hypothesis_id}` | {source or '-'} |"
            )

    return "\n".join(lines) + "\n"
