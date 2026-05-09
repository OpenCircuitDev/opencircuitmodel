"""Generate a synthetic retrieval workload for the mem0-encryption sandbox.

Each line is one query record:
  {"id": int, "query_kind": str, "key": str, "expected_match": bool}

The sandbox seeds an SQLite (or SQLCipher) database with a fixed corpus of
~1000 small text rows, then runs each query as an indexed lookup or LIKE scan
against that corpus. Encrypted vs unencrypted timing differences come from
the SQLCipher (or AES-GCM proxy) layer, NOT from the query semantics —
queries are kept simple on purpose.

Run from repo root:
  python bench/workloads/_generate_mem0_retrieval_workload.py \
      > bench/workloads/mem0-retrieval-1000q.jsonl
"""

from __future__ import annotations

import json
import random
import sys


CORPUS_SIZE = 1000
QUERY_KINDS = ["pk_lookup", "key_lookup", "like_scan"]


def main() -> int:
    rng = random.Random(0xC1AC1A)  # deterministic
    queries: list[dict] = []
    for i in range(CORPUS_SIZE):
        kind = rng.choice(QUERY_KINDS)
        if kind == "pk_lookup":
            target = rng.randrange(CORPUS_SIZE)
            queries.append({"id": i, "query_kind": kind, "key": str(target), "expected_match": True})
        elif kind == "key_lookup":
            # key field has format "k_<n>" for n in 0..CORPUS_SIZE
            target = rng.randrange(CORPUS_SIZE)
            queries.append({"id": i, "query_kind": kind, "key": f"k_{target}", "expected_match": True})
        else:  # like_scan
            # 95% of queries match a real prefix; 5% miss to exercise miss path
            if rng.random() < 0.95:
                prefix = f"k_{rng.randrange(0, 9)}"  # matches ~10% of corpus
                queries.append({"id": i, "query_kind": kind, "key": prefix, "expected_match": True})
            else:
                queries.append({"id": i, "query_kind": kind, "key": "zzz_nomatch", "expected_match": False})

    sys.stdout.reconfigure(encoding="utf-8")
    for q in queries:
        print(json.dumps(q))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
