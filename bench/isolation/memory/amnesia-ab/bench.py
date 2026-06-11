"""amnesia-ab framework entrypoint — delegates to the Node runner (run.mjs).

This sandbox's harness is JavaScript because the measurement is pure HTTP
against an Ollama daemon, and run.mjs is the exact artifact that produced the
committed first CONFIRMED result (results/run-2026-06-11T20-32-21.json).
bench.py exists so the framework's ACTIVE-sandbox contract (compose + bench)
holds; it delegates rather than re-implementing, so there is ONE harness.

Requires: a reachable Ollama daemon (default http://127.0.0.1:11434, override
with OLLAMA_URL) with `llama3` and `mxbai-embed-large` pulled, plus Node 18+.
Host-dependency pattern matches vllm-q4-llama8b (which needs a host GPU).
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

if __name__ == "__main__":
    sys.exit(subprocess.call(["node", os.path.join(HERE, "run.mjs")]))
