"""Mem0 library-driven retrieval — recall@k measurement.

Tests the SEARCH layer of Mem0 specifically, NOT the LLM-driven memory
extraction layer (`add(infer=True)` is bypassed via `infer=False`). This
isolates retrieval quality from extraction quality so the verdict speaks
to spec row 9's "library-driven retrieval" claim directly.

Workload:
  bench/workloads/mem0-retrieval-recall-corpus.jsonl  (39 facts across 4 users)
  bench/workloads/mem0-retrieval-recall.jsonl         (39 queries with ground truth)

Hermetic config:
  - embedder: huggingface (sentence-transformers/all-MiniLM-L6-v2) — no API key
  - vector_store: faiss (local file-backed) — no server needed
  - llm: stub OpenAI config (never actually called because infer=False)

Output:
  primary_value:   recall@10 across all queries (fraction where ALL expected
                   memory_ids appear in the top-10 retrieved set)
  secondary_value: cross-user-leak rate (fraction of queries where retrieval
                   returned a memory belonging to a DIFFERENT user — should be
                   exactly 0.0 if Mem0's user_id isolation works)
"""

from __future__ import annotations

import json
import os
import shutil
import statistics
import time
from pathlib import Path

# Mem0 lazy import — bench.py is supposed to fail loudly if the env doesn't
# have it, not at module-load time
def _import_mem0():
    from mem0 import Memory
    return Memory


def main() -> int:
    workloads = Path(os.environ.get("WORKLOADS_DIR", "/workloads"))
    if not workloads.exists():
        # Local dev fallback
        repo_workloads = Path(__file__).resolve().parents[3] / "workloads"
        if repo_workloads.exists():
            workloads = repo_workloads
        else:
            print(f"ERROR: workloads dir not found at {workloads} or {repo_workloads}")
            return 2

    corpus_path = workloads / "mem0-retrieval-recall-corpus.jsonl"
    queries_path = workloads / "mem0-retrieval-recall.jsonl"
    if not corpus_path.exists() or not queries_path.exists():
        print(f"ERROR: workload files missing under {workloads}")
        return 2

    Memory = _import_mem0()
    started = time.monotonic()

    # Hermetic config — local files only, no external services.
    # Use absolute path because Mem0's faiss provider does
    # os.makedirs(os.path.dirname(path)) which fails on Windows when
    # dirname() returns an empty string for a relative-no-dir path.
    faiss_path = (Path.cwd() / "_mem0_bench_faiss").resolve()
    if faiss_path.exists():
        shutil.rmtree(faiss_path)
    faiss_path.parent.mkdir(parents=True, exist_ok=True)

    config = {
        "embedder": {
            "provider": "huggingface",
            "config": {"model": "sentence-transformers/all-MiniLM-L6-v2"},
        },
        "vector_store": {
            "provider": "faiss",
            "config": {
                "collection_name": "ocm_bench",
                "path": str(faiss_path),
                "embedding_model_dims": 384,  # MiniLM-L6-v2 dim
            },
        },
        "llm": {
            "provider": "openai",
            "config": {"api_key": "sk-stub-not-used", "model": "gpt-4o-mini"},
        },
    }

    m = Memory.from_config(config)

    # Seed memories — bypass LLM extraction with infer=False
    # We track our memory_id (workload field) -> Mem0's internal ID via metadata
    workload_id_to_mem0_id: dict[int, str] = {}
    with corpus_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            result = m.add(
                rec["content"],
                user_id=rec["user_id"],
                infer=False,
                metadata={"workload_memory_id": rec["memory_id"]},
            )
            # Mem0 returns various shapes across versions; normalize
            results = result.get("results", []) if isinstance(result, dict) else result
            if results and isinstance(results, list) and isinstance(results[0], dict):
                workload_id_to_mem0_id[rec["memory_id"]] = results[0].get("id", "")

    # Run queries
    queries: list[dict] = []
    with queries_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                queries.append(json.loads(line))

    n_queries = len(queries)
    n_recall_hits = 0  # all expected ids found in top-10
    n_cross_user_leaks = 0
    per_query: list[dict] = []
    top_k = 10

    for q in queries:
        # Mem0 v2 API: user_id passed via filters, not as a direct kwarg
        results = m.search(
            q["query"],
            filters={"user_id": q["user_id"]},
            top_k=top_k,
        )
        retrieved = results.get("results", []) if isinstance(results, dict) else results

        # Map back to workload memory_ids via metadata
        retrieved_workload_ids: list[int] = []
        retrieved_user_ids: list[str] = []
        for r in retrieved or []:
            md = r.get("metadata") or {}
            if "workload_memory_id" in md:
                retrieved_workload_ids.append(md["workload_memory_id"])
            retrieved_user_ids.append(r.get("user_id", q["user_id"]))

        expected_ids = set(q["expected_memory_ids"])
        retrieved_set = set(retrieved_workload_ids)
        recall_hit = expected_ids.issubset(retrieved_set)
        if recall_hit:
            n_recall_hits += 1

        # Cross-user leak: any retrieved memory belongs to a different user?
        wrong_user = any(uid != q["user_id"] for uid in retrieved_user_ids if uid)
        if wrong_user:
            n_cross_user_leaks += 1

        per_query.append({
            "query_id": q["query_id"],
            "user_id": q["user_id"],
            "expected": list(expected_ids),
            "retrieved": retrieved_workload_ids,
            "recall_hit": recall_hit,
            "cross_user_leak": wrong_user,
        })

    recall_at_k = n_recall_hits / n_queries if n_queries else 0.0
    cross_user_leak_rate = n_cross_user_leaks / n_queries if n_queries else 0.0
    elapsed = time.monotonic() - started

    # Cleanup
    if faiss_path.exists():
        shutil.rmtree(faiss_path)

    output = {
        "primary_value": recall_at_k,
        "secondary_value": cross_user_leak_rate,
        "duration_seconds": elapsed,
        "n_queries": n_queries,
        "n_memories": len(workload_id_to_mem0_id),
        "top_k": top_k,
        "n_recall_hits": n_recall_hits,
        "n_cross_user_leaks": n_cross_user_leaks,
        "embedder": "sentence-transformers/all-MiniLM-L6-v2",
        "vector_store": "faiss-local",
        "failed_queries": [
            q for q in per_query if not q["recall_hit"]
        ],
    }

    Path("outputs.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
