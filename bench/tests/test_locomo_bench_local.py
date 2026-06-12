"""Unit tests for mem0-v3-locomo bench.py functions.

Mem0-dependent tests require mem0ai + sentence-transformers + faiss-cpu and
are marked `requires_mem0`.  They also skip on Python 3.12+ locally because
sentence-transformers → pyarrow crashes on Python 3.13 (Windows).  The real
verdict runs in Docker (Python 3.11) where all deps are installed cleanly.

Run locally on Python 3.11 with mem0ai installed:
    cd bench && pytest tests/test_locomo_bench_local.py -v -m requires_mem0
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Skip guard: these tests need mem0ai importable. A version gate was wrong twice
# over — CI runs py3.11 WITHOUT mem0 installed (failed), and a future py3.12-
# compatible mem0 would be skipped needlessly. Gate on availability, not version.
# ---------------------------------------------------------------------------
def _mem0_available() -> bool:
    try:
        import mem0  # noqa: F401
        return True
    except Exception:
        return False


_skip_py312 = pytest.mark.skipif(
    not _mem0_available(),
    reason="mem0ai not importable in this environment; the full path runs in the sandbox Docker (py 3.11 + pip install)",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_bench():
    modpath = (
        Path(__file__).resolve().parents[1]
        / "isolation" / "memory" / "mem0-v3-locomo" / "bench.py"
    )
    spec = importlib.util.spec_from_file_location("locomo_bench", modpath)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


FIXTURE_CONV = {
    "sample_id": "fake_0",
    "conversation": {
        "speaker_a": "Alice",
        "speaker_b": "Bob",
        "session_1_date_time": "2024-01-01T10:00:00",
        "session_1": [
            {"speaker": "Alice", "dia_id": "D1:1", "text": "I bought a Specialized Tarmac SL7."},
            {"speaker": "Bob",   "dia_id": "D1:2", "text": "Nice — what color?"},
        ],
        "session_2": [
            {"speaker": "Alice", "dia_id": "D2:1", "text": "Matte black."},
        ],
    },
    "qa": [
        {
            "question": "What bike did Alice buy?",
            "answer": "Specialized Tarmac SL7",
            "evidence": ["D1:1"],
            "category": "single_hop",
        }
    ],
}


# ---------------------------------------------------------------------------
# Test: session key regex — no mem0 dependency, runs on all Python versions
# ---------------------------------------------------------------------------

def test_session_regex_only_matches_pure_session_keys():
    """Verify the _SESSION_RE pattern selects only bare session_N keys."""
    bench = _load_bench()
    pattern = bench._SESSION_RE
    assert pattern.match("session_1")
    assert pattern.match("session_10")
    assert not pattern.match("session_1_date_time")
    assert not pattern.match("speaker_a")
    assert not pattern.match("session_summary")


# ---------------------------------------------------------------------------
# Mem0-dependent tests (require Python 3.11 + mem0ai)
# ---------------------------------------------------------------------------

@pytest.mark.requires_mem0
@_skip_py312
def test_ingest_skips_non_session_keys_and_counts_turns(tmp_path):
    bench = _load_bench()
    mem = bench.build_hermetic_mem0(faiss_dir=tmp_path / "_faiss")
    stats = bench.ingest_conversation(mem, FIXTURE_CONV, user_id="locomo_user_0")
    # 2 sessions (session_1 + session_2), 3 turns total
    # speaker_a, speaker_b, session_1_date_time must be skipped
    assert stats["turns"] == 3
    assert stats["sessions"] == 2


@pytest.mark.requires_mem0
@_skip_py312
def test_score_conversation_recall_full_when_evidence_in_top10(tmp_path):
    bench = _load_bench()
    mem = bench.build_hermetic_mem0(faiss_dir=tmp_path / "_faiss")
    bench.ingest_conversation(mem, FIXTURE_CONV, user_id="t0")
    result = bench.score_conversation(mem, FIXTURE_CONV, user_id="t0", top_k=10)
    assert result["per_qa_recall"] == [1.0]
    assert result["mean_recall"] == 1.0
    assert result["tokens_p50"] > 0
    assert len(result["per_qa_tokens"]) == 1


@pytest.mark.requires_mem0
@_skip_py312
def test_token_p50_is_true_flat_list_across_conversations(tmp_path):
    """True flat median: 1-QA conv + 3-QA conv must give 4 items, not 2."""
    bench = _load_bench()
    conv_a = {
        "conversation": {"session_1": [
            {"speaker": "A", "dia_id": "D1:1", "text": "x" * 40},
        ]},
        "qa": [{"question": "q", "answer": "x", "evidence": ["D1:1"], "category": "x"}],
    }
    conv_b = {
        "conversation": {"session_1": [
            {"speaker": "A", "dia_id": "D1:1", "text": "y" * 400},
        ]},
        "qa": [
            {"question": "q1", "answer": "y", "evidence": ["D1:1"], "category": "x"},
            {"question": "q2", "answer": "y", "evidence": ["D1:1"], "category": "x"},
            {"question": "q3", "answer": "y", "evidence": ["D1:1"], "category": "x"},
        ],
    }
    mem = bench.build_hermetic_mem0(faiss_dir=tmp_path / "_faiss")
    all_tokens: list[float] = []
    for i, c in enumerate([conv_a, conv_b]):
        bench.ingest_conversation(mem, c, user_id=f"u{i}")
        s = bench.score_conversation(mem, c, user_id=f"u{i}")
        all_tokens.extend(s["per_qa_tokens"])
    # Must have 1 + 3 = 4 items (not 2 from per-conv duplication)
    assert len(all_tokens) == 4
