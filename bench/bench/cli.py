"""OCM bench CLI: `bench list`, `bench run`, `bench report`."""

from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from .compare import retro_sync_report
from .runner import DryRunError, list_all_sandboxes, load_expected, run_sandbox

console = Console()


@click.group()
@click.version_option(package_name="ocm-bench")
def main() -> None:
    """OCM benchmark + sandbox framework CLI."""


def _bench_root() -> Path:
    """Return the bench/ directory (parent of this package)."""
    return Path(__file__).resolve().parent.parent


@main.command(name="list")
@click.option("--root", type=click.Path(exists=True, path_type=Path), default=None,
              help="Override the bench/ root directory (default: auto-detected).")
def list_sandboxes(root: Path | None) -> None:
    """List every isolation + combination sandbox in the framework."""
    bench_root = root or _bench_root()
    isolation = list_all_sandboxes(bench_root / "isolation")
    combination = list_all_sandboxes(bench_root / "combination")

    table = Table(title="OCM Bench Sandboxes")
    table.add_column("Type", style="cyan")
    table.add_column("Path", style="green")

    for path in isolation:
        table.add_row("isolation", str(path.relative_to(bench_root)))
    for path in combination:
        table.add_row("combination", str(path.relative_to(bench_root)))

    if not isolation and not combination:
        console.print("[yellow]No sandboxes found.[/yellow]")
        return
    console.print(table)


@main.command()
@click.argument("sandbox_path", type=click.Path(exists=True, path_type=Path))
@click.option("--hardware-class", required=True,
              help="e.g. nvidia-rtx-4090-24gb, apple-m4-pro-32gb, cpu-only-32gb")
@click.option("--repeats", type=int, default=3, show_default=True)
@click.option("--out-dir", type=click.Path(path_type=Path), default=None,
              help="Override results output dir (default: bench/results)")
@click.option("--dry-run", is_flag=True,
              help="Validate sandbox structure without invoking Docker.")
def run(
    sandbox_path: Path,
    hardware_class: str,
    repeats: int,
    out_dir: Path | None,
    dry_run: bool,
) -> None:
    """Run a sandbox `repeats` times and record verdict to results/."""
    out_dir = out_dir or (_bench_root() / "results")
    try:
        summary = run_sandbox(
            sandbox_path,
            hardware_class=hardware_class,
            repeats=repeats,
            out_dir=out_dir,
            dry_run=dry_run,
        )
    except DryRunError as e:
        console.print(f"[red]DRY-RUN FAILED:[/red] {e}")
        sys.exit(2)

    if dry_run:
        console.print(
            f"[green]DRY-RUN PASSED:[/green] {summary.hypothesis_id} "
            f"(structure valid; would run {repeats} repeats)"
        )
        return

    color = {
        "CONFIRMED": "green",
        "REFUTED": "red",
        "INCONCLUSIVE": "yellow",
    }[summary.verdict.value]
    console.print(
        f"[{color}]Verdict: {summary.verdict.value}[/{color}] — "
        f"{summary.verdict_reason}"
    )
    console.print(f"  primary median: {summary.primary_median:.3f}")
    if summary.secondary_median is not None:
        console.print(f"  secondary median: {summary.secondary_median:.3f}")


@main.command()
@click.option("--hypothesis-id", default=None)
@click.option("--hardware-class", default=None)
@click.option("--limit", type=int, default=20, show_default=True)
@click.option("--root", type=click.Path(exists=True, path_type=Path), default=None)
def report(
    hypothesis_id: str | None,
    hardware_class: str | None,
    limit: int,
    root: Path | None,
) -> None:
    """Retro-sync report across past benchmark runs."""
    bench_root = root or _bench_root()
    output = retro_sync_report(
        bench_root / "results",
        hypothesis_id=hypothesis_id,
        hardware_class=hardware_class,
        limit=limit,
    )
    console.print(output)


@main.command(name="dry-run-all")
@click.option("--root", type=click.Path(exists=True, path_type=Path), default=None)
def dry_run_all(root: Path | None) -> None:
    """Validate every sandbox's structure. Used in CI.

    Reports ACTIVE and INACTIVE sandboxes separately. INACTIVE sandboxes
    surface their `blocked_on` reasons so a CI log makes it obvious which
    sandboxes are slot stubs vs running validations.
    """
    bench_root = root or _bench_root()
    sandboxes = (
        list_all_sandboxes(bench_root / "isolation")
        + list_all_sandboxes(bench_root / "combination")
    )
    if not sandboxes:
        console.print("[yellow]No sandboxes found.[/yellow]")
        return

    failed = 0
    active_count = 0
    inactive_count = 0
    for sandbox in sandboxes:
        rel = sandbox.relative_to(bench_root)
        try:
            expected = run_sandbox(
                sandbox,
                hardware_class="ci-validation",
                repeats=1,
                out_dir=bench_root / "results",
                dry_run=True,
            ).expected
            if expected.status == "ACTIVE":
                console.print(f"[green]PASS[/green]    [cyan]ACTIVE  [/cyan] {rel}")
                active_count += 1
            else:
                inactive_count += 1
                blockers = expected.blocked_on or []
                blocker_str = (
                    " · ".join(blockers) if blockers else "no blocked_on listed"
                )
                console.print(
                    f"[green]PASS[/green]    [yellow]INACTIVE[/yellow] {rel}  "
                    f"[dim]blocked: {blocker_str}[/dim]"
                )
        except DryRunError as e:
            console.print(f"[red]FAIL[/red]    [cyan]?       [/cyan] {rel}: {e}")
            failed += 1

    console.print()
    if failed:
        console.print(
            f"[red]{failed} sandbox(es) failed dry-run validation.[/red]"
        )
        sys.exit(1)
    console.print(
        f"[green]All {len(sandboxes)} sandboxes passed[/green] "
        f"([cyan]{active_count} ACTIVE[/cyan], "
        f"[yellow]{inactive_count} INACTIVE slot stubs[/yellow])."
    )


@main.command(name="run-all")
@click.option("--hardware-class", required=True,
              help="e.g. nvidia-rtx-4090-24gb, apple-m4-pro-32gb, cpu-only-32gb")
@click.option("--repeats", type=int, default=3, show_default=True)
@click.option("--out-dir", type=click.Path(path_type=Path), default=None,
              help="Override results output dir (default: bench/results)")
@click.option("--root", type=click.Path(exists=True, path_type=Path), default=None)
@click.option("--continue-on-error", is_flag=True,
              help="Keep running remaining sandboxes when one errors out (default: stop on first error).")
def run_all(
    hardware_class: str,
    repeats: int,
    out_dir: Path | None,
    root: Path | None,
    continue_on_error: bool,
) -> None:
    """Run every ACTIVE sandbox and produce a unified comparison table.

    INACTIVE sandboxes are reported but skipped — slot stubs by design.
    Exit code: 0 if no REFUTED verdicts, 1 if any sandbox REFUTED, 2 if
    any sandbox errored (and --continue-on-error wasn't set).
    """
    bench_root = root or _bench_root()
    out_dir = out_dir or (bench_root / "results")
    sandboxes = (
        list_all_sandboxes(bench_root / "isolation")
        + list_all_sandboxes(bench_root / "combination")
    )
    if not sandboxes:
        console.print("[yellow]No sandboxes found.[/yellow]")
        return

    summaries: list[tuple[Path, object]] = []
    skipped_inactive: list[Path] = []
    errored: list[tuple[Path, str]] = []

    for sandbox in sandboxes:
        rel = sandbox.relative_to(bench_root)
        try:
            expected = load_expected(sandbox)
        except DryRunError as e:
            errored.append((sandbox, f"load_expected: {e}"))
            console.print(f"[red]ERROR[/red] {rel}: {e}")
            if not continue_on_error:
                break
            continue

        if expected.status != "ACTIVE":
            skipped_inactive.append(sandbox)
            console.print(f"[dim yellow]SKIP[/dim yellow]   {rel} (INACTIVE)")
            continue

        console.print(f"[cyan]RUN[/cyan]    {rel} ({expected.hypothesis_id})")
        try:
            summary = run_sandbox(
                sandbox,
                hardware_class=hardware_class,
                repeats=repeats,
                out_dir=out_dir,
                dry_run=False,
            )
            summaries.append((sandbox, summary))
            verdict_color = {
                "CONFIRMED": "green",
                "REFUTED": "red",
                "INCONCLUSIVE": "yellow",
            }[summary.verdict.value]
            console.print(
                f"  -> [{verdict_color}]{summary.verdict.value}[/{verdict_color}] "
                f"primary={summary.primary_median:.3f}"
            )
        except Exception as e:  # noqa: BLE001
            errored.append((sandbox, str(e)))
            console.print(f"[red]ERROR[/red] {rel}: {e}")
            if not continue_on_error:
                break

    # Comparison table
    console.print()
    table = Table(title=f"OCM Bench: comparison on {hardware_class}")
    table.add_column("Sandbox", style="cyan")
    table.add_column("Hypothesis", style="dim")
    table.add_column("Verdict", style="bold")
    table.add_column("Primary median", justify="right")
    table.add_column("Secondary median", justify="right")
    for sandbox, summary in summaries:
        rel = str(sandbox.relative_to(bench_root))
        verdict_color = {
            "CONFIRMED": "green",
            "REFUTED": "red",
            "INCONCLUSIVE": "yellow",
        }[summary.verdict.value]
        table.add_row(
            rel,
            summary.hypothesis_id,
            f"[{verdict_color}]{summary.verdict.value}[/{verdict_color}]",
            f"{summary.primary_median:.3f}",
            f"{summary.secondary_median:.3f}" if summary.secondary_median is not None else "—",
        )
    if summaries:
        console.print(table)

    # Summary
    confirmed = sum(1 for _, s in summaries if s.verdict.value == "CONFIRMED")
    refuted = sum(1 for _, s in summaries if s.verdict.value == "REFUTED")
    inconclusive = sum(1 for _, s in summaries if s.verdict.value == "INCONCLUSIVE")
    console.print(
        f"[green]{confirmed} CONFIRMED[/green]  "
        f"[red]{refuted} REFUTED[/red]  "
        f"[yellow]{inconclusive} INCONCLUSIVE[/yellow]  "
        f"[dim]{len(skipped_inactive)} INACTIVE skipped[/dim]  "
        f"[red]{len(errored)} errored[/red]"
    )

    if errored and not continue_on_error:
        sys.exit(2)
    if refuted:
        sys.exit(1)


@main.command(name="list-inactive")
@click.option("--root", type=click.Path(exists=True, path_type=Path), default=None)
def list_inactive(root: Path | None) -> None:
    """List INACTIVE sandboxes (slot stubs) with their blocked_on reasons.

    Useful for picking up scoped work — pick a sandbox, resolve its blockers,
    flip its status to ACTIVE.
    """
    bench_root = root or _bench_root()
    sandboxes = (
        list_all_sandboxes(bench_root / "isolation")
        + list_all_sandboxes(bench_root / "combination")
    )
    rows: list[tuple[Path, list[str]]] = []
    for sandbox in sandboxes:
        try:
            expected = load_expected(sandbox)
        except DryRunError:
            continue
        if expected.status == "INACTIVE":
            rows.append((sandbox, expected.blocked_on or []))

    if not rows:
        console.print("[green]No INACTIVE sandboxes — all slots active.[/green]")
        return

    table = Table(title=f"OCM Bench: {len(rows)} INACTIVE slot stubs")
    table.add_column("Sandbox", style="yellow")
    table.add_column("Blocked on", style="dim")
    for sandbox, blockers in rows:
        rel = str(sandbox.relative_to(bench_root))
        blocker_str = "\n".join(f"• {b}" for b in blockers) if blockers else "(none listed)"
        table.add_row(rel, blocker_str)
    console.print(table)


if __name__ == "__main__":
    main()
