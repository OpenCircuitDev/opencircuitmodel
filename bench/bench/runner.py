"""Sandbox execution. Supports --dry-run validation without invoking Docker."""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import yaml
from pydantic import ValidationError

from .metrics import ExpectedJson, RunResult, SandboxSummary, Verdict, decide_verdict


class DryRunError(ValueError):
    """Raised when sandbox structure fails dry-run validation."""


def find_sandbox_files(sandbox_path: Path, *, active: bool = True) -> dict[str, Path]:
    """Locate the files a sandbox must have.

    ACTIVE sandboxes need all four (expected.json, docker-compose.yml, bench.py,
    README.md) since they execute end-to-end.

    INACTIVE sandboxes (slot stubs committed before their underlying tech is
    ready) need only expected.json + README.md.
    """
    required = {
        "expected": sandbox_path / "expected.json",
        "readme": sandbox_path / "README.md",
    }
    if active:
        required["compose"] = sandbox_path / "docker-compose.yml"
        required["bench"] = sandbox_path / "bench.py"
    missing = [name for name, path in required.items() if not path.exists()]
    if missing:
        state = "ACTIVE" if active else "INACTIVE"
        raise DryRunError(
            f"sandbox {sandbox_path} ({state}) is missing required files: {', '.join(missing)}"
        )
    return required


def load_expected(sandbox_path: Path) -> ExpectedJson:
    """Load and validate expected.json against the schema.

    Reads expected.json before checking the rest of the file set so the
    sandbox's `status` can gate file requirements.
    """
    expected_path = sandbox_path / "expected.json"
    if not expected_path.exists():
        raise DryRunError(f"sandbox {sandbox_path} is missing expected.json")
    raw = json.loads(expected_path.read_text())
    try:
        expected = ExpectedJson(**raw)
    except ValidationError as e:
        raise DryRunError(f"expected.json schema invalid: {e}") from e
    # Now enforce the file set appropriate for the sandbox's status.
    find_sandbox_files(sandbox_path, active=(expected.status == "ACTIVE"))
    return expected


def validate_compose(sandbox_path: Path) -> None:
    """Verify docker-compose.yml parses as YAML and declares at least one service.

    Skips silently for INACTIVE sandboxes — they don't ship a compose file.
    """
    expected_path = sandbox_path / "expected.json"
    raw_expected = json.loads(expected_path.read_text())
    if raw_expected.get("status", "ACTIVE") != "ACTIVE":
        return
    files = find_sandbox_files(sandbox_path, active=True)
    raw = files["compose"].read_text()
    try:
        parsed = yaml.safe_load(raw)
    except yaml.YAMLError as e:
        raise DryRunError(f"docker-compose.yml is not valid YAML: {e}") from e
    if not isinstance(parsed, dict) or "services" not in parsed:
        raise DryRunError("docker-compose.yml must declare 'services' at top level")
    if not parsed["services"]:
        raise DryRunError("docker-compose.yml has empty 'services' section")


def list_all_sandboxes(root: Path) -> list[Path]:
    """Walk the bench tree and return every directory containing expected.json."""
    return sorted(p.parent for p in root.rglob("expected.json"))


def dry_run_sandbox(sandbox_path: Path) -> ExpectedJson:
    """Validate sandbox structure without invoking Docker. Returns parsed expected."""
    expected = load_expected(sandbox_path)
    validate_compose(sandbox_path)
    return expected


def run_sandbox(
    sandbox_path: Path,
    *,
    hardware_class: str,
    repeats: int = 3,
    out_dir: Path,
    dry_run: bool = False,
) -> SandboxSummary:
    """Execute a sandbox `repeats` times. With dry_run, only validate structure."""
    expected = dry_run_sandbox(sandbox_path)

    if dry_run:
        return SandboxSummary(
            hypothesis_id=expected.hypothesis_id,
            hardware_class=hardware_class,
            timestamp_utc=datetime.now(UTC).isoformat(),
            expected=expected,
            runs=[],
            primary_median=0.0,
            primary_std=None,
            verdict=Verdict.INCONCLUSIVE,
            verdict_reason="DRY_RUN: structure valid, no measurement performed",
        )

    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")
    run_dir = out_dir / f"{timestamp}-{expected.hypothesis_id}-{hardware_class}"
    run_dir.mkdir(parents=True, exist_ok=True)

    runs: list[RunResult] = []
    for i in range(repeats):
        result = _execute_compose(sandbox_path, expected, repeat=i, out_dir=run_dir)
        runs.append(result)

    primary_values = sorted(r.primary_value for r in runs)
    primary_median = primary_values[len(primary_values) // 2]
    primary_std = _std(primary_values) if len(primary_values) > 1 else None

    secondary_values = [r.secondary_value for r in runs if r.secondary_value is not None]
    secondary_median = (
        sorted(secondary_values)[len(secondary_values) // 2]
        if secondary_values
        else None
    )
    secondary_std = _std(secondary_values) if len(secondary_values) > 1 else None

    verdict, reason = decide_verdict(primary_median, expected, secondary_median)

    summary = SandboxSummary(
        hypothesis_id=expected.hypothesis_id,
        hardware_class=hardware_class,
        timestamp_utc=timestamp,
        expected=expected,
        runs=runs,
        primary_median=primary_median,
        primary_std=primary_std,
        secondary_median=secondary_median,
        secondary_std=secondary_std,
        verdict=verdict,
        verdict_reason=reason,
    )
    (run_dir / "summary.json").write_text(summary.model_dump_json(indent=2))
    return summary


def _execute_compose(
    sandbox_path: Path,
    expected: ExpectedJson,
    *,
    repeat: int,
    out_dir: Path,
) -> RunResult:
    """Run docker-compose for one repeat. Production implementation hook."""
    try:
        proc = subprocess.run(
            ["docker", "compose", "-f", str(sandbox_path / "docker-compose.yml"),
             "up", "--abort-on-container-exit", "--exit-code-from", "bench"],
            cwd=str(sandbox_path),
            capture_output=True,
            text=True,
            timeout=expected.timeout_seconds,
            check=False,
        )
        (out_dir / f"stdout-{repeat}.log").write_text(proc.stdout)
        (out_dir / f"stderr-{repeat}.log").write_text(proc.stderr)
    finally:
        subprocess.run(
            ["docker", "compose", "-f", str(sandbox_path / "docker-compose.yml"), "down"],
            cwd=str(sandbox_path),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )

    output_path = sandbox_path / "outputs.json"
    if not output_path.exists():
        raise RuntimeError(
            f"sandbox bench.py did not produce outputs.json at {output_path}"
        )
    payload = json.loads(output_path.read_text())
    return RunResult(
        hypothesis_id=expected.hypothesis_id,
        repeat_index=repeat,
        primary_value=float(payload["primary_value"]),
        secondary_value=(
            float(payload["secondary_value"])
            if payload.get("secondary_value") is not None
            else None
        ),
        duration_seconds=float(payload.get("duration_seconds", 0.0)),
        raw_path=str(output_path),
    )


def _std(values: list[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    return (sum((v - mean) ** 2 for v in values) / (n - 1)) ** 0.5
