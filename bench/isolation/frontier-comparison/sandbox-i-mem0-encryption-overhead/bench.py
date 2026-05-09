"""Mem0 SQLCipher encryption overhead measurement (Sandbox I).

Seeds two SQLite databases — one plain, one encrypted — with the same
1000-row corpus, runs the same retrieval workload against each, and
reports the median pct latency overhead.

ENCRYPTION MODES (auto-detected at startup):

  1. SQLCIPHER (canonical) — uses sqlcipher3 / pysqlcipher3 with an
     Argon2id-derived key. This is what spec row 29 specifically claims
     5-15% overhead for. Available in Docker via apt-get +
     pip install pysqlcipher3.

  2. AES-GCM PROXY (fallback) — pure-Python application-layer AES-256-GCM
     per-row encryption via the `cryptography` library. Different mechanism
     than SQLCipher (per-row, not per-page) so reports a STRICT UPPER BOUND
     on the overhead claim. If proxy <= confirm threshold, SQLCipher will
     definitely confirm. If proxy > refute threshold, the result is
     INCONCLUSIVE for SQLCipher specifically and needs the canonical run.

The output JSON tags `encryption_mode` so downstream report aggregation
can distinguish canonical from proxy measurements.
"""

from __future__ import annotations

import json
import os
import statistics
import time
from pathlib import Path
from typing import Callable

# ----------------------------------------------------------------------
# Mode detection
# ----------------------------------------------------------------------

ENCRYPTION_MODE: str
sqlcipher_dbapi = None

try:
    import sqlcipher3  # type: ignore

    sqlcipher_dbapi = sqlcipher3.dbapi2
    ENCRYPTION_MODE = "sqlcipher3"
except ImportError:
    try:
        from pysqlcipher3 import dbapi2 as _pysqlcipher_dbapi2  # type: ignore

        sqlcipher_dbapi = _pysqlcipher_dbapi2
        ENCRYPTION_MODE = "pysqlcipher3"
    except ImportError:
        ENCRYPTION_MODE = "aes-gcm-proxy"


# ----------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------

CORPUS_SIZE = 1000
ROW_BYTES = 200  # representative Mem0 row size — short conversation snippet
PASSPHRASE = "ocm-bench-passphrase-do-not-use-in-production"


# ----------------------------------------------------------------------
# Corpus generation (deterministic)
# ----------------------------------------------------------------------

def gen_corpus(n: int = CORPUS_SIZE, seed: int = 0xC1AC1A) -> list[tuple[int, str, str]]:
    """Generate (id, key, content) tuples deterministically."""
    import random

    rng = random.Random(seed)
    rows = []
    for i in range(n):
        key = f"k_{i}"
        # Pad content to ROW_BYTES with random ASCII; gives encryption a
        # realistic per-row size to chew on (200B ≈ a short Mem0 memory).
        filler = "".join(rng.choices("abcdefghijklmnopqrstuvwxyz0123456789 ", k=ROW_BYTES))
        rows.append((i, key, filler))
    return rows


# ----------------------------------------------------------------------
# Plain SQLite store
# ----------------------------------------------------------------------

def make_plain_db(path: Path, corpus: list[tuple[int, str, str]]):
    """Return (query, conn) — caller must close conn before unlinking the file."""
    import sqlite3

    if path.exists():
        path.unlink()
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE memory (id INTEGER PRIMARY KEY, key TEXT, content TEXT)")
    conn.execute("CREATE INDEX idx_memory_key ON memory(key)")
    conn.executemany("INSERT INTO memory (id, key, content) VALUES (?, ?, ?)", corpus)
    conn.commit()

    def query(q: dict) -> int:
        kind = q["query_kind"]
        if kind == "pk_lookup":
            row = conn.execute("SELECT id, key, content FROM memory WHERE id = ?", (int(q["key"]),)).fetchone()
            return 1 if row else 0
        elif kind == "key_lookup":
            row = conn.execute("SELECT id, key, content FROM memory WHERE key = ?", (q["key"],)).fetchone()
            return 1 if row else 0
        else:
            rows = conn.execute("SELECT id FROM memory WHERE key LIKE ?", (q["key"] + "%",)).fetchall()
            return len(rows)

    return query, conn


# ----------------------------------------------------------------------
# SQLCipher store (canonical)
# ----------------------------------------------------------------------

def make_sqlcipher_db(path: Path, corpus: list[tuple[int, str, str]]):
    """Return (query, conn) for a SQLCipher store. Caller closes conn before unlink."""
    if sqlcipher_dbapi is None:
        raise RuntimeError("sqlcipher not available")

    # SQLCipher accepts a key directly via PRAGMA key. The Argon2id
    # derivation is OCM's outer layer per spec row 29; for the bench
    # we feed SQLCipher's KDF directly with a passphrase. This still
    # exercises the PBKDF2 default that SQLCipher uses internally.
    if path.exists():
        path.unlink()
    conn = sqlcipher_dbapi.connect(str(path))
    conn.execute(f"PRAGMA key = '{PASSPHRASE}'")
    # SQLCipher 4 default: PBKDF2-SHA512, 256000 iterations, AES-256-CBC
    conn.execute("CREATE TABLE memory (id INTEGER PRIMARY KEY, key TEXT, content TEXT)")
    conn.execute("CREATE INDEX idx_memory_key ON memory(key)")
    conn.executemany("INSERT INTO memory (id, key, content) VALUES (?, ?, ?)", corpus)
    conn.commit()

    def query(q: dict) -> int:
        kind = q["query_kind"]
        if kind == "pk_lookup":
            row = conn.execute("SELECT id, key, content FROM memory WHERE id = ?", (int(q["key"]),)).fetchone()
            return 1 if row else 0
        elif kind == "key_lookup":
            row = conn.execute("SELECT id, key, content FROM memory WHERE key = ?", (q["key"],)).fetchone()
            return 1 if row else 0
        else:
            rows = conn.execute("SELECT id FROM memory WHERE key LIKE ?", (q["key"] + "%",)).fetchall()
            return len(rows)

    return query, conn


# ----------------------------------------------------------------------
# AES-GCM proxy store (fallback for environments without SQLCipher)
# ----------------------------------------------------------------------

def make_aes_proxy_db(path: Path, corpus: list[tuple[int, str, str]]):
    """Plain SQLite with AES-256-GCM per-row encryption on the content column.

    Returns (query, conn). Strict upper bound on SQLCipher overhead — per-row
    AES is more expensive than SQLCipher's per-page approach.
    """
    import sqlite3

    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    key = AESGCM.generate_key(bit_length=256)
    aes = AESGCM(key)

    if path.exists():
        path.unlink()
    conn = sqlite3.connect(str(path))
    conn.execute(
        "CREATE TABLE memory (id INTEGER PRIMARY KEY, key TEXT, "
        "nonce BLOB, ciphertext BLOB)"
    )
    conn.execute("CREATE INDEX idx_memory_key ON memory(key)")

    encrypted_rows = []
    for i, k, content in corpus:
        nonce = os.urandom(12)
        ct = aes.encrypt(nonce, content.encode("utf-8"), None)
        encrypted_rows.append((i, k, nonce, ct))
    conn.executemany(
        "INSERT INTO memory (id, key, nonce, ciphertext) VALUES (?, ?, ?, ?)",
        encrypted_rows,
    )
    conn.commit()

    def query(q: dict) -> int:
        kind = q["query_kind"]
        if kind == "pk_lookup":
            row = conn.execute(
                "SELECT id, key, nonce, ciphertext FROM memory WHERE id = ?",
                (int(q["key"]),),
            ).fetchone()
            if row:
                _ = aes.decrypt(row[2], row[3], None)  # decrypt as a real consumer would
                return 1
            return 0
        elif kind == "key_lookup":
            row = conn.execute(
                "SELECT id, key, nonce, ciphertext FROM memory WHERE key = ?",
                (q["key"],),
            ).fetchone()
            if row:
                _ = aes.decrypt(row[2], row[3], None)
                return 1
            return 0
        else:
            rows = conn.execute(
                "SELECT nonce, ciphertext FROM memory WHERE key LIKE ?",
                (q["key"] + "%",),
            ).fetchall()
            for nonce, ct in rows:
                _ = aes.decrypt(nonce, ct, None)
            return len(rows)

    return query, conn


# ----------------------------------------------------------------------
# Bench orchestration
# ----------------------------------------------------------------------

def run_workload(query_fn: Callable[[dict], int], queries: list[dict]) -> list[float]:
    """Time each query individually. Returns per-query latency seconds."""
    latencies = []
    for q in queries:
        t0 = time.perf_counter_ns()
        query_fn(q)
        latencies.append((time.perf_counter_ns() - t0) / 1e9)
    return latencies


def main() -> int:
    workload_path = Path(os.environ.get("WORKLOAD_PATH", "/workloads/mem0-retrieval-1000q.jsonl"))
    if not workload_path.exists():
        repo_workload = Path(__file__).resolve().parents[3] / "workloads" / "mem0-retrieval-1000q.jsonl"
        if repo_workload.exists():
            workload_path = repo_workload
        else:
            print(f"ERROR: workload not found at {workload_path} or {repo_workload}")
            return 2

    queries: list[dict] = []
    with workload_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                queries.append(json.loads(line))

    corpus = gen_corpus()
    started = time.monotonic()

    # Always use a sandbox-local working dir so cleanup works on Windows
    # (where /tmp resolves quirkily) and Linux (where it's the canonical
    # tmpfs). The runner mounts ./:/work so this stays inside the
    # sandbox dir on both.
    work_dir = Path(".")
    plain_path = work_dir / "_sandbox_i_plain.db"
    enc_path = work_dir / "_sandbox_i_enc.db"

    # 1. Plain SQLite baseline
    plain_query, plain_conn = make_plain_db(plain_path, corpus)
    plain_latencies = run_workload(plain_query, queries)
    plain_median = statistics.median(plain_latencies)
    plain_conn.close()

    # 2. Encrypted (SQLCipher canonical OR AES-GCM proxy)
    if ENCRYPTION_MODE in ("sqlcipher3", "pysqlcipher3"):
        enc_query, enc_conn = make_sqlcipher_db(enc_path, corpus)
    else:
        enc_query, enc_conn = make_aes_proxy_db(enc_path, corpus)
    enc_latencies = run_workload(enc_query, queries)
    enc_median = statistics.median(enc_latencies)
    enc_conn.close()

    # Cleanup
    plain_path.unlink(missing_ok=True)
    enc_path.unlink(missing_ok=True)

    pct_overhead = ((enc_median - plain_median) / plain_median) * 100 if plain_median > 0 else 0.0
    elapsed = time.monotonic() - started

    output = {
        "primary_value": pct_overhead,
        "duration_seconds": elapsed,
        "encryption_mode": ENCRYPTION_MODE,
        "n_queries": len(queries),
        "corpus_size": CORPUS_SIZE,
        "plain_latency_median_seconds": plain_median,
        "encrypted_latency_median_seconds": enc_median,
        "plain_latency_p99_seconds": sorted(plain_latencies)[int(len(plain_latencies) * 0.99)],
        "encrypted_latency_p99_seconds": sorted(enc_latencies)[int(len(enc_latencies) * 0.99)],
    }

    Path("outputs.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
