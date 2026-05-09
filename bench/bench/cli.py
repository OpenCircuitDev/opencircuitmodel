"""OCM bench CLI: `bench list`, `bench run`, `bench report`."""

from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from .compare import retro_sync_report
from .runner import DryRunError, list_all_sandboxes, run_sandbox

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
    """Validate every sandbox's structure. Used in CI."""
    bench_root = root or _bench_root()
    sandboxes = (
        list_all_sandboxes(bench_root / "isolation")
        + list_all_sandboxes(bench_root / "combination")
    )
    if not sandboxes:
        console.print("[yellow]No sandboxes found.[/yellow]")
        return

    failed = 0
    for sandbox in sandboxes:
        try:
            run_sandbox(
                sandbox,
                hardware_class="ci-validation",
                repeats=1,
                out_dir=bench_root / "results",
                dry_run=True,
            )
            console.print(f"[green]PASS[/green] {sandbox.relative_to(bench_root)}")
        except DryRunError as e:
            console.print(f"[red]FAIL[/red] {sandbox.relative_to(bench_root)}: {e}")
            failed += 1

    if failed:
        console.print(f"\n[red]{failed} sandbox(es) failed dry-run validation.[/red]")
        sys.exit(1)
    console.print(f"\n[green]All {len(sandboxes)} sandboxes passed dry-run validation.[/green]")


if __name__ == "__main__":
    main()
