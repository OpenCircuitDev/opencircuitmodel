"""Structural smoke test — the mem0-v3-locomo sandbox validates correctly
regardless of its ACTIVE/INACTIVE status.
"""

from pathlib import Path

from bench.runner import load_expected


def test_mem0_v3_locomo_sandbox_loads_expected():
    root = Path(__file__).resolve().parents[2]
    sandbox = root / "bench" / "isolation" / "memory" / "mem0-v3-locomo"
    expected = load_expected(sandbox)
    assert expected.hypothesis_id == "mem0-v3-locomo-recall"
    # Files required for ACTIVE status must be present when status == ACTIVE
    if expected.status == "ACTIVE":
        assert (sandbox / "docker-compose.yml").exists()
        assert (sandbox / "bench.py").exists()
