"""Mem0 v3 LoCoMo recall measurement.

Measures Mem0's library-driven retrieval (NOT LLM-driven extraction) on the
LoCoMo long-conversation QA benchmark.  The verdict path is retrieval-only
(fast, hermetic, no Ollama required).  Pass --with-llm to additionally run an
end-to-end Ollama diagnostic.

Dataset (fetched at run time, never bundled):
  LoCoMo — Maharana et al., ACL 2024 (arXiv:2402.17753)
  License: CC BY-NC 4.0  |  snap-research/locomo on GitHub
  We download locomo10.json at run time and do NOT redistribute it.

Hermetic config (mirrors mem0-library-retrieval-recall / sandbox #56):
  embedder   : huggingface (sentence-transformers/all-MiniLM-L6-v2) — no key
  vector_store: faiss (local file-backed) — no server needed
  llm        : stub OpenAI config (add(infer=False) — never called)

Primary output:
  locomo_recall_score  : mean per-conversation recall × 100  (0-100 scale)
  tokens_retrieved_p50 : median per-QA token count (true flat median)

Optional diagnostic (--with-llm):
  llm_answer_match_pct : fraction of QAs where Ollama llama3 reply contains
                         the ground-truth answer substring
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import statistics
import time
import urllib.request as _urlreq
from pathlib import Path

# ---------------------------------------------------------------------------
# Dataset constants — pinned to a specific upstream commit for reproducibility
# ---------------------------------------------------------------------------

LOCOMO_PIN = "cbfbc1dba6bc53d00625212a0f22d55ffee7c1fc"
LOCOMO_URL = (
    "https://raw.githubusercontent.com/snap-research/locomo"
    f"/{LOCOMO_PIN}/data/locomo10.json"
)
EXPECTED_SHA256 = "79fa87e90f04081343b8c8debecb80a9a6842b76a7aa537dc9fdf651ea698ff4"

_SESSION_RE = re.compile(r"^session_\d+$")

# ---------------------------------------------------------------------------
# LLM diagnostic constants (only used when --with-llm is on)
# ---------------------------------------------------------------------------

SYS_ON = (
    "You are a personal assistant with persistent memory of past sessions.\n"
    "RELEVANT MEMORIES retrieved for this request:\n{mems}\n"
    "Answer using these memories — be specific. Be concise."
)


# ---------------------------------------------------------------------------
# Step 1 — fetch dataset
# ---------------------------------------------------------------------------


def fetch_locomo(dest: Path) -> Path:
    """Download locomo10.json to *dest*, skipping if SHA256 already matches."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        if hashlib.sha256(dest.read_bytes()).hexdigest() == EXPECTED_SHA256:
            print(f"[fetch] cache hit: {dest}")
            return dest
        dest.unlink()
    url = os.environ.get("LOCOMO_URL", LOCOMO_URL)
    print(f"[fetch] downloading {url}")
    _urlreq.urlretrieve(url, dest)
    got = hashlib.sha256(dest.read_bytes()).hexdigest()
    if got != EXPECTED_SHA256:
        raise SystemExit(
            f"locomo10.json SHA256 mismatch: got {got}, expected {EXPECTED_SHA256}"
        )
    print(f"[fetch] ok ({dest.stat().st_size:,} bytes)")
    return dest


# ---------------------------------------------------------------------------
# Step 2 — hermetic Mem0 instance
# ---------------------------------------------------------------------------


def build_hermetic_mem0(faiss_dir: Path):
    """Build a fresh Mem0 instance backed by a local faiss index.

    Mirrors the config from mem0-library-retrieval-recall (#56).
    """
    from mem0 import Memory  # lazy import — loud failure if env lacks it

    faiss_dir = Path(faiss_dir).resolve()
    if faiss_dir.exists():
        shutil.rmtree(faiss_dir)
    faiss_dir.parent.mkdir(parents=True, exist_ok=True)

    return Memory.from_config(
        {
            "embedder": {
                "provider": "huggingface",
                "config": {"model": "sentence-transformers/all-MiniLM-L6-v2"},
            },
            "vector_store": {
                "provider": "faiss",
                "config": {
                    "collection_name": "ocm_locomo",
                    "path": str(faiss_dir),
                    "embedding_model_dims": 384,
                },
            },
            "llm": {
                "provider": "openai",
                "config": {"api_key": "sk-stub-not-used", "model": "gpt-4o-mini"},
            },
        }
    )


# ---------------------------------------------------------------------------
# Step 3 — ingest one conversation
# ---------------------------------------------------------------------------


def ingest_conversation(mem, conv: dict, *, user_id: str) -> dict:
    """Ingest all turns of one LoCoMo conversation into Mem0.

    Each turn becomes one memory (infer=False — bypasses extraction).
    Metadata carries dia_id and session key for recall mapping.

    Session keys are filtered to match `session_\\d+$` so date-time strings
    and speaker fields inside the conversation dict are skipped.
    """
    n_turns = n_sessions = 0
    for session_key, turns in conv["conversation"].items():
        if not _SESSION_RE.match(session_key):
            continue  # skip 'speaker_a', 'session_1_date_time', etc.
        if not isinstance(turns, list):
            continue
        n_sessions += 1
        for turn in turns:
            mem.add(
                turn["text"],
                user_id=user_id,
                infer=False,
                metadata={"dia_id": turn["dia_id"], "session": session_key},
            )
            n_turns += 1
    return {"turns": n_turns, "sessions": n_sessions}


# ---------------------------------------------------------------------------
# Step 4 — score one conversation (recall + token metrics)
# ---------------------------------------------------------------------------


def score_conversation(mem, conv: dict, *, user_id: str, top_k: int = 10) -> dict:
    """Compute LoCoMo recall + token metrics for one conversation.

    Returns per_qa_recall (list) and per_qa_tokens (list) so the caller can
    aggregate across conversations with correct flat-list medians.
    """
    per_qa_recall: list[float] = []
    per_qa_tokens: list[float] = []

    for qa in conv.get("qa", []):
        results = mem.search(
            qa["question"],
            filters={"user_id": user_id},
            top_k=top_k,
        )
        hits = (
            results.get("results", [])
            if isinstance(results, dict)
            else (results or [])
        )

        # Map retrieved hits back to dia_ids via metadata
        retrieved_dia_ids: set[str] = set()
        for r in hits:
            md = r.get("metadata") or {}
            did = md.get("dia_id")
            if did:
                retrieved_dia_ids.add(did)

        evidence = set(qa.get("evidence", []))
        if evidence:
            per_qa_recall.append(
                len(retrieved_dia_ids & evidence) / len(evidence)
            )

        # Token approximation: 4 chars ≈ 1 token (heuristic for scale check)
        per_qa_tokens.append(
            sum(len(r.get("memory", "")) / 4.0 for r in hits)
        )

    return {
        "per_qa_recall": per_qa_recall,
        "mean_recall": (
            sum(per_qa_recall) / len(per_qa_recall) if per_qa_recall else 0.0
        ),
        "per_qa_tokens": per_qa_tokens,
        "tokens_p50": (
            statistics.median(per_qa_tokens) if per_qa_tokens else 0.0
        ),
        "n_qa": len(per_qa_recall),
    }


# ---------------------------------------------------------------------------
# Step 5 — optional LLM diagnostic
# ---------------------------------------------------------------------------


def _ollama_chat(ollama_url: str, system: str, user: str) -> str:
    body = json.dumps(
        {
            "model": "llama3",
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "options": {"temperature": 0.2, "num_predict": 200},
        }
    ).encode()
    req = _urlreq.Request(
        f"{ollama_url}/api/chat",
        data=body,
        headers={"content-type": "application/json"},
    )
    with _urlreq.urlopen(req, timeout=60) as r:
        return json.loads(r.read())["message"]["content"]


def _norm(s: str) -> str:
    return "".join(c for c in s.lower() if c.isalnum())


def _diagnose_with_llm(
    mem, conv: dict, user_id: str, ollama_url: str, top_k: int = 10
) -> dict:
    """Run optional end-to-end LLM diagnostic (not in verdict contract)."""
    matches = total = 0
    for qa in conv.get("qa", []):
        results = mem.search(
            qa["question"],
            filters={"user_id": user_id},
            top_k=top_k,
        )
        hits = (
            results.get("results", [])
            if isinstance(results, dict)
            else (results or [])
        )
        mems_block = "\n".join(f"- {h.get('memory', '')}" for h in hits)
        try:
            reply = _ollama_chat(
                ollama_url,
                SYS_ON.format(mems=mems_block),
                qa["question"],
            )
        except Exception as e:
            print(f"[llm] error on '{qa['question'][:40]}…': {e}")
            continue
        total += 1
        if _norm(qa["answer"]) in _norm(reply):
            matches += 1
    return {
        "llm_n_qa": total,
        "llm_match_pct": (100.0 * matches / total) if total else 0.0,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Mem0 v3 LoCoMo recall bench")
    parser.add_argument(
        "--with-llm",
        action="store_true",
        help="Run optional Ollama LLM diagnostic (not part of verdict contract)",
    )
    args = parser.parse_args()

    workload = fetch_locomo(Path("_locomo_workload/locomo10.json"))
    convs: list[dict] = json.loads(workload.read_text(encoding="utf-8"))

    started = time.monotonic()
    faiss_dir = Path("_mem0_locomo_faiss")
    mem = build_hermetic_mem0(faiss_dir)

    per_conv_recall: list[float] = []
    all_per_qa_tokens: list[float] = []  # flat — true median over all QAs
    breakdown: list[dict] = []

    for i, conv in enumerate(convs):
        user_id = f"locomo_user_{i}"
        ingest_stats = ingest_conversation(mem, conv, user_id=user_id)
        score = score_conversation(mem, conv, user_id=user_id)

        per_conv_recall.append(score["mean_recall"])
        all_per_qa_tokens.extend(score["per_qa_tokens"])

        breakdown.append(
            {
                "sample_id": conv.get("sample_id", f"conv_{i}"),
                "mean_recall": score["mean_recall"],
                "n_qa": score["n_qa"],
                "n_turns": ingest_stats["turns"],
                "n_sessions": ingest_stats["sessions"],
                "tokens_p50": score["tokens_p50"],
            }
        )
        print(
            f"[conv {i}] recall={score['mean_recall']:.3f} "
            f"qa={score['n_qa']} turns={ingest_stats['turns']}"
        )

    # Primary: mean over 10 conversations × 100 (0-100 scale, matches published 91.6)
    primary = 100.0 * sum(per_conv_recall) / len(per_conv_recall)
    # Secondary: true flat p50 over every individual QA's token count
    secondary = statistics.median(all_per_qa_tokens) if all_per_qa_tokens else 0.0
    elapsed = time.monotonic() - started

    output: dict = {
        "primary_value": primary,
        "secondary_value": secondary,
        "duration_seconds": elapsed,
        "n_conversations": len(convs),
        "n_qa_total": sum(b["n_qa"] for b in breakdown),
        "embedder": "sentence-transformers/all-MiniLM-L6-v2",
        "vector_store": "faiss-local",
        "per_conversation": breakdown,
    }

    if args.with_llm:
        ollama_url = os.environ.get("OLLAMA_URL", "http://host.docker.internal:11434")
        print(f"[llm] running LLM diagnostic against {ollama_url}...")
        diags = [
            _diagnose_with_llm(mem, c, f"locomo_user_{i}", ollama_url)
            for i, c in enumerate(convs)
        ]
        total_n = sum(d["llm_n_qa"] for d in diags)
        total_match = sum(d["llm_n_qa"] * d["llm_match_pct"] / 100.0 for d in diags)
        output["diagnostic"] = {
            "llm_answer_match_pct": (
                100.0 * total_match / total_n if total_n else 0.0
            ),
            "llm_n_qa": total_n,
            "llm_model": "llama3",
        }

    # Cleanup faiss index — keeps the sandbox dir clean between runs
    if faiss_dir.exists():
        shutil.rmtree(faiss_dir)

    Path("outputs.json").write_text(
        json.dumps(output, indent=2), encoding="utf-8"
    )
    print(
        f"\n[result] locomo_recall_score={primary:.2f} "
        f"tokens_p50={secondary:.0f} "
        f"elapsed={elapsed:.1f}s"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
