# OCM Benchmark + Sandbox Framework — Detailed Plan

> **Goal:** A meticulous, scientifically-grounded measurement framework that confirms or refutes every load-bearing claim in the OCM spec. Every tool we adopt is measured in **isolation** (sandbox per tool) and in **combination** (sandbox per stack). Results are versioned, anonymized for evaluation, retro-syncable, and reproducible by anyone with the same hardware class.

**Why this exists:** Research is a hypothesis. Measurement is confirmation. The OCM spec locks in tools (Mem0 over Letta, SGLang for prefix-heavy, EAGLE-3 default-on, Qwen3-30B-A3B as canonical model, Hermes XML+JSON tool format, schema compression, etc.) — *every one of these decisions deserves to be measured against our specific workload before it's blessed at scale*. This framework is the discipline that catches the cases where research-claimed numbers don't reproduce, where vendor-stated benchmarks were cherry-picked, and where combinations behave differently than the sum of their parts.

---

## Architectural principles

### 1. Hypothesis → Sandbox → Measure → Decide
Every benchmark begins with a written hypothesis (`expected.json`):
- The claim being tested (e.g., "EAGLE-3 gives 1.5-2.5× single-user speedup on Llama 3.1 8B chat workload")
- The threshold for acceptance (e.g., "≥1.4× to confirm")
- The threshold for rejection (e.g., "<1.2× falsifies the claim for our use case")
- The decision rule (e.g., "if speedup is 1.2-1.4×, run again with different prompt mix; if still indeterminate, mark as 'inconclusive — do not lock as default'")

Every benchmark output includes the verdict: **CONFIRMED / REFUTED / INCONCLUSIVE**.

### 2. Isolation before combination
A tool is benchmarked **alone first** before being included in any combination test. The reason: if a combination shows 5× speedup, we need to know which component contributed. Without isolation baselines, combination results are uninterpretable.

### 3. Reproducibility
Every benchmark sandbox is a Docker image with pinned versions. Every input is checksummed. Every output is stored as Parquet with full provenance (commit SHA, image digest, timestamp, hardware fingerprint, input checksum, environment variables). Anyone with the same hardware class can `git clone && bench run` and get the same numbers ± measurement noise.

### 4. Anonymization for evaluation
When measurements involve human judgment (e.g., "is output A or B higher quality?"), the evaluator sees only blind labels. The mapping is stored separately; only revealed after results are recorded. This eliminates evaluator bias.

### 5. Retro-sync for regression detection
Every run is keyed by `(hypothesis_id, hardware_class, image_digest, timestamp)`. Querying historical runs by hypothesis_id reveals trends — did our v0.5 stack benchmark drop 15% when we upgraded to v0.7? The framework surfaces these regressions immediately.

### 6. Internal-first, public eventually
The framework's *primary* purpose is to make OCM's design choices defensible. *Secondary* purpose is publication on the OCM website (`/benchmarks`). We do not optimize for public-facing benchmark theater.

---

## Directory structure

```
opencircuitmodel/bench/
├── README.md                                # Methodology
├── bench/                                   # CLI + framework code (Python)
│   ├── __init__.py
│   ├── cli.py                               # `bench run`, `bench list`, `bench report`
│   ├── runner.py                            # Sandbox execution
│   ├── metrics.py                           # Throughput, latency, TTFT, quality
│   ├── eval.py                              # Quality eval harnesses
│   ├── compare.py                           # Statistical comparison + retro-sync
│   ├── anonymize.py                         # Blind-label evaluator inputs
│   └── publish.py                           # Generate /benchmarks page data
├── isolation/
│   ├── inference-engines/
│   │   ├── vllm-q4-llama8b/
│   │   │   ├── docker-compose.yml
│   │   │   ├── bench.py                     # The actual measurement script
│   │   │   ├── workload.jsonl               # Standardized prompts
│   │   │   ├── expected.json                # Hypothesis + thresholds
│   │   │   └── README.md                    # What this measures and why
│   │   ├── sglang-q4-llama8b/
│   │   ├── llama-cpp-q4-llama8b/
│   │   ├── mlx-lm-q4-llama8b/
│   │   ├── tensorrt-llm-fp4-llama8b/        # RTX 5090 only
│   │   ├── vllm-q4-qwen3-30b-a3b/           # The canonical model
│   │   └── llama-cpp-metal-qwen3-30b-a3b/   # Mac Pro 64GB
│   ├── speculative-decoding/
│   │   ├── eagle3-vllm-llama8b/
│   │   ├── eagle3-sglang-llama8b/
│   │   ├── medusa-vllm-llama8b/
│   │   └── lookahead-llama-cpp-llama8b/
│   ├── prefix-caching/
│   │   ├── radix-sglang-shared-system-prompt/
│   │   ├── radix-sglang-multi-turn-chat/
│   │   ├── apc-vllm-shared-system-prompt/
│   │   └── apc-vllm-multi-turn-chat/
│   ├── memory-layers/
│   │   ├── mem0-llama8b-longmemeval/
│   │   ├── letta-llama8b-longmemeval/
│   │   ├── zep-graphiti-llama8b-longmemeval/
│   │   └── plain-rag-llama8b-longmemeval/   # Baseline: plain vector RAG
│   ├── quantization/
│   │   ├── q4-k-m-llama70b-perplexity/
│   │   ├── awq-int4-llama70b-perplexity/
│   │   ├── exl3-llama70b-perplexity/
│   │   └── aqlm-2bit-llama70b-perplexity/
│   ├── tool-formats/
│   │   ├── openai-json-llama8b-bfcl/
│   │   ├── hermes-xml-json-hermes3-8b-bfcl/
│   │   ├── codeact-llama8b-gaia-subset/
│   │   └── schema-compression-llama8b-token-reduction/
│   └── transports/                           # v2+
│       ├── libp2p-residential-nat-success/
│       ├── iroh-residential-nat-success/
│       └── webrtc-with-turn-residential/
├── combination/
│   ├── 01-baseline-vllm-fp16-no-cache/      # The denominator for all multipliers
│   ├── 02-baseline-plus-q4/
│   ├── 03-baseline-plus-q4-plus-batching/
│   ├── 04-baseline-plus-q4-batching-radix/
│   ├── 05-baseline-plus-q4-batching-radix-eagle3/
│   ├── 06-full-stack-llama8b-vllm/          # Canonical v1 NVIDIA stack
│   ├── 07-full-stack-qwen3-30b-a3b-vllm/    # Canonical v1 high-spec NVIDIA
│   ├── 08-full-stack-qwen3-30b-a3b-mlx/     # Canonical v1 Mac high-spec
│   ├── 09-full-stack-with-mem0/             # Stack + persistent memory
│   ├── 10-full-stack-with-mem0-and-mcp/     # Stack + memory + MCP tool calling
│   └── 99-mesh-pd-disaggregation-2-node/    # v2+ mesh: prefill on 5090, decode on Mac
├── workloads/                                # Standardized test inputs
│   ├── chat-singleturn-1k.jsonl             # 1000 single-turn chat prompts
│   ├── chat-multiturn-500.jsonl             # 500 5-turn conversations
│   ├── tool-use-bfcl-v3.jsonl               # Berkeley Function Calling V3
│   ├── long-context-100k.jsonl              # 100K-token retrieval needles
│   ├── agent-tasks-gaia-subset.jsonl        # GAIA subset for agent benchmarking
│   ├── memory-recall-longmemeval.jsonl      # LongMemEval persistent-memory test
│   ├── shared-system-prompt-50-users.jsonl  # Multi-user shared-prefix simulation
│   └── code-tasks-swebench-lite.jsonl       # SWE-bench-lite for code agents
├── eval/                                     # Quality evaluation harnesses
│   ├── mmlu_runner.py                       # Wraps lm-evaluation-harness
│   ├── gsm8k_runner.py                      # Math reasoning
│   ├── tool_call_correctness.py             # JSON validity + intent match
│   ├── memory_recall_score.py               # LongMemEval scoring
│   ├── agent_task_completion.py             # GAIA subset scoring
│   ├── perplexity_runner.py                 # Wikitext-2 perplexity for quantization
│   └── blind_human_eval.py                  # Anonymized side-by-side for human judges
├── runners/
│   ├── docker_runner.py                     # Local Docker execution
│   ├── modal_runner.py                      # Cloud GPU bursts (RTX 4090/5090)
│   └── github_actions_runner.py             # CI integration
├── results/                                  # Versioned, append-only
│   ├── 2026-05-08T14-00-00Z-baseline-vllm-fp16/
│   │   ├── config.toml                      # Full provenance
│   │   ├── outputs.parquet                  # Per-request metrics
│   │   ├── summary.json                     # Aggregated metrics + verdict
│   │   ├── stdout.log
│   │   └── analysis.md                      # Human-readable conclusions
│   └── ...
├── analysis/
│   ├── retro_sync_dashboard.py              # Compare runs across time
│   ├── per_node_multiplier_audit.py         # Validate the 20-30× claim
│   ├── combination_vs_sum_of_parts.py       # Detect non-linear interactions
│   └── regression_detector.py               # Flag drops between runs
└── pyproject.toml                            # Bench tool dependencies
```

---

## Tooling decisions

| Layer | Choice | Why |
|---|---|---|
| **Container runtime** | Docker + docker-compose | Universal, well-supported across macOS/Linux/Windows. Single Dockerfile per sandbox. |
| **Cloud GPU bursting** | Modal (per-run charged, deterministic) | Closest to "click run, get result" for one-off benchmarks; avoid persistent infra |
| **Storage** | Parquet via pyarrow + DuckDB for queries | Columnar, compressible, fast analytical queries. No DB server. |
| **CI integration** | GitHub Actions matrix (Linux + macOS runners; NVIDIA via Modal) | Free for public repos, reproducible, results stored as workflow artifacts |
| **Statistical testing** | scipy + paired t-test / Mann-Whitney U for nonparametric | Standard rigor; avoid p-hacking by pre-declaring tests in `expected.json` |
| **Quality evaluation** | EleutherAI `lm-evaluation-harness` (MMLU, GSM8K) + custom for tool-call / memory | Battle-tested for quality benchmarks; widely cited |
| **Tool-call evaluation** | Berkeley Function Calling Leaderboard v3 dataset + scoring | Industry-standard; published methodology |
| **Memory evaluation** | LongMemEval dataset + scoring (used by Mem0/Zep/Letta papers) | Apples-to-apples comparison with the memory-layer research claims |
| **Throughput / latency** | Custom Python harness with asyncio + httpx; record per-request metrics | Avoid `wrk`/`vegeta` because we need per-request token-level timing |
| **TTFT** | First chunk arrival time on streaming endpoints | Standard production metric |
| **Anonymization** | UUIDs as blind labels; mapping stored separately; only revealed after eval recorded | Eliminates evaluator bias on subjective comparisons |
| **Provenance** | git SHA + Docker image digest + hardware fingerprint + timestamp + workload checksum | Full reproducibility traceability |
| **Dashboard** | DuckDB-backed Astro page on `/benchmarks` (auto-generated from results/) | Public-facing, retro-syncable, no separate dashboard infra |

---

## Hardware classes

Benchmarks are tagged by **hardware class** so retro-sync queries can compare apples-to-apples:

| Class ID | Spec |
|---|---|
| `nvidia-rtx-4060-8gb` | RTX 4060, 8GB VRAM, 16GB+ system RAM |
| `nvidia-rtx-4090-24gb` | RTX 4090, 24GB VRAM, 32GB+ system RAM |
| `nvidia-rtx-5090-32gb` | RTX 5090, 32GB VRAM, 64GB+ system RAM (Blackwell FP4) |
| `apple-m4-base-16gb` | M4, 16GB unified memory |
| `apple-m4-pro-32gb` | M4 Pro, 32GB unified memory |
| `apple-m4-pro-64gb` | M4 Pro, 64GB unified memory |
| `apple-m2-ultra-192gb` | M2 Ultra, 192GB unified memory (workstation) |
| `cpu-only-32gb` | x86-64 CPU, 32GB+ RAM, no GPU |

Every result file declares its hardware class. Comparisons across classes are explicitly flagged as cross-class (illustrative, not authoritative).

---

## Phase 0 deliverables (Weeks 1-2)

These are the bite-sized tasks for the first two weeks of bench framework work.

### Task B0.1: Bootstrap framework scaffold

**Files:**
- Create: `bench/pyproject.toml`, `bench/bench/__init__.py`, `bench/bench/cli.py`, `bench/bench/runner.py`, `bench/bench/metrics.py`

- [ ] **Step 1: pyproject.toml**

```toml
[project]
name = "ocm-bench"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "click>=8.1",
    "httpx>=0.27",
    "pyarrow>=15",
    "duckdb>=0.10",
    "polars>=0.20",
    "pydantic>=2.5",
    "scipy>=1.12",
    "numpy>=1.26",
    "pyyaml>=6.0",
    "tomli>=2.0",
    "tomli-w>=1.0",
    "rich>=13.7",
]

[project.scripts]
bench = "bench.cli:main"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: CLI skeleton in `bench/bench/cli.py`**

```python
import click
from pathlib import Path

@click.group()
def main():
    """OCM benchmark + sandbox framework."""

@main.command()
@click.argument("sandbox_path", type=click.Path(exists=True, path_type=Path))
@click.option("--hardware-class", required=True)
@click.option("--repeats", default=3, type=int)
@click.option("--out-dir", type=click.Path(path_type=Path), default="bench/results")
def run(sandbox_path: Path, hardware_class: str, repeats: int, out_dir: Path):
    """Run a sandbox and record results."""
    from bench.runner import run_sandbox
    run_sandbox(sandbox_path, hardware_class=hardware_class, repeats=repeats, out_dir=out_dir)

@main.command(name="list")
def list_sandboxes():
    """List all available sandboxes."""
    from bench.runner import list_all_sandboxes
    for path in list_all_sandboxes():
        click.echo(str(path))

@main.command()
@click.option("--hypothesis-id")
@click.option("--hardware-class")
@click.option("--limit", default=20, type=int)
def report(hypothesis_id: str | None, hardware_class: str | None, limit: int):
    """Generate retro-sync report for a hypothesis."""
    from bench.compare import retro_sync_report
    click.echo(retro_sync_report(hypothesis_id, hardware_class, limit))

if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Runner skeleton in `bench/bench/runner.py`** (focused on Docker execution + provenance capture)

```python
import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import tomli

def run_sandbox(sandbox_path: Path, *, hardware_class: str, repeats: int, out_dir: Path) -> dict:
    """Execute a sandbox `repeats` times, record provenance + outputs."""
    expected = json.loads((sandbox_path / "expected.json").read_text())
    hypothesis_id = expected["hypothesis_id"]
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    run_dir = out_dir / f"{timestamp}-{hypothesis_id}-{hardware_class}"
    run_dir.mkdir(parents=True, exist_ok=True)

    # Capture provenance
    git_sha = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()
    image_digest = _build_and_digest(sandbox_path)
    provenance = {
        "hypothesis_id": hypothesis_id,
        "hardware_class": hardware_class,
        "git_sha": git_sha,
        "image_digest": image_digest,
        "timestamp": timestamp,
        "repeats": repeats,
        "expected": expected,
    }
    (run_dir / "config.toml").write_text(_to_toml(provenance))

    # Execute repeats
    results = []
    for i in range(repeats):
        proc = subprocess.run(
            ["docker", "compose", "-f", str(sandbox_path / "docker-compose.yml"), "up", "--abort-on-container-exit"],
            cwd=sandbox_path,
            capture_output=True,
            text=True,
            timeout=expected.get("timeout_seconds", 600),
        )
        # Bench scripts inside the container write outputs to a shared volume
        results.append(_collect_outputs(sandbox_path, repeat=i))
        subprocess.run(["docker", "compose", "down"], cwd=sandbox_path, check=False)

    summary = _aggregate(results, expected)
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    return summary

def _build_and_digest(sandbox_path: Path) -> str:
    out = subprocess.check_output(
        ["docker", "compose", "-f", str(sandbox_path / "docker-compose.yml"), "build"],
        cwd=sandbox_path,
        stderr=subprocess.STDOUT,
    )
    # Real implementation: parse `docker images --digests` for the built image
    return hashlib.sha256(out).hexdigest()[:16]  # placeholder

def list_all_sandboxes(root: Path = Path("bench/isolation")) -> list[Path]:
    return [p for p in root.rglob("expected.json")]

def _to_toml(d: dict) -> str:
    import tomli_w
    return tomli_w.dumps(d)

def _collect_outputs(sandbox_path: Path, repeat: int) -> dict:
    # Stub — real impl parses container's mounted output volume
    return {}

def _aggregate(results: list[dict], expected: dict) -> dict:
    # Stub — real impl computes mean ± std, applies thresholds, sets verdict
    return {"verdict": "STUB", "expected": expected}
```

- [ ] **Step 4: Test the scaffold**

```bash
cd opencircuitmodel/bench
pip install -e .
bench --help
bench list  # Will be empty until first sandbox is added
```

- [ ] **Step 5: Commit**

```bash
git add bench/
git commit -m "feat(bench): framework scaffold — CLI + runner + provenance capture"
```

### Task B0.2: First isolation sandbox — vLLM Q4 Llama 8B baseline

**Files:**
- Create: `bench/isolation/inference-engines/vllm-q4-llama8b/{docker-compose.yml,bench.py,expected.json,workload.jsonl,README.md}`

- [ ] **Step 1: `expected.json`**

```json
{
  "hypothesis_id": "vllm-q4-llama8b-singlestream-tps",
  "claim": "vLLM v1 with Q4 (AWQ-INT4) Llama 3.1 8B delivers ~120 tok/s single-stream on RTX 4090",
  "metric": "tokens_per_second_single_stream",
  "thresholds": {
    "confirm_at_least": 100.0,
    "refute_below": 80.0
  },
  "workload": "chat-singleturn-1k.jsonl",
  "source_for_claim": "https://www.databasemart.com/blog/vllm-gpu-benchmark-rtx4090",
  "timeout_seconds": 1800
}
```

- [ ] **Step 2: `docker-compose.yml`**

```yaml
services:
  vllm:
    image: vllm/vllm-openai:v0.7.3
    runtime: nvidia
    ports:
      - "8000:8000"
    environment:
      - HF_TOKEN=${HF_TOKEN}
    command:
      - --model
      - hugging-quants/Meta-Llama-3.1-8B-Instruct-AWQ-INT4
      - --port
      - "8000"
      - --max-model-len
      - "8192"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/v1/models"]
      interval: 10s
      retries: 60
  bench:
    image: python:3.11-slim
    depends_on:
      vllm:
        condition: service_healthy
    volumes:
      - ./:/work
      - ../../../workloads:/workloads:ro
    working_dir: /work
    command: ["sh", "-c", "pip install httpx && python bench.py"]
```

- [ ] **Step 3: `bench.py`**

```python
import asyncio
import json
import time
from pathlib import Path

import httpx

WORKLOAD = Path("/workloads/chat-singleturn-1k.jsonl")
ENDPOINT = "http://vllm:8000/v1/chat/completions"
MODEL = "hugging-quants/Meta-Llama-3.1-8B-Instruct-AWQ-INT4"

async def measure_one(client: httpx.AsyncClient, prompt: str) -> dict:
    t0 = time.monotonic()
    first_token_time = None
    total_tokens = 0
    async with client.stream(
        "POST",
        ENDPOINT,
        json={
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 256,
            "stream": True,
        },
        timeout=120,
    ) as r:
        async for line in r.aiter_lines():
            if not line.startswith("data: "):
                continue
            payload = line[6:]
            if payload == "[DONE]":
                break
            chunk = json.loads(payload)
            delta = chunk["choices"][0]["delta"].get("content", "")
            if delta and first_token_time is None:
                first_token_time = time.monotonic()
            total_tokens += len(delta.split())  # crude; replace with tokenizer
    t_end = time.monotonic()
    return {
        "ttft_seconds": (first_token_time - t0) if first_token_time else None,
        "total_seconds": t_end - t0,
        "output_tokens": total_tokens,
        "tokens_per_second": total_tokens / (t_end - first_token_time) if first_token_time else 0,
    }

async def main():
    prompts = [json.loads(l)["prompt"] for l in WORKLOAD.read_text().splitlines() if l.strip()]
    async with httpx.AsyncClient() as client:
        results = []
        for p in prompts[:50]:  # First 50 for single-stream baseline
            results.append(await measure_one(client, p))
    Path("/work/outputs.json").write_text(json.dumps(results, indent=2))
    print(f"Median tok/s: {sorted(r['tokens_per_second'] for r in results)[len(results)//2]:.1f}")

if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Run it**

```bash
cd opencircuitmodel
bench run bench/isolation/inference-engines/vllm-q4-llama8b --hardware-class nvidia-rtx-4090-24gb --repeats 3
```

Expected: A `bench/results/2026-05-08T...-vllm-q4-llama8b-singlestream-tps-nvidia-rtx-4090-24gb/` directory with `summary.json` containing the verdict.

- [ ] **Step 5: Commit**

```bash
git add bench/isolation/inference-engines/vllm-q4-llama8b
git commit -m "feat(bench): isolation sandbox — vLLM Q4 Llama 8B baseline (claim: ~120 tok/s)"
```

### Task B0.3-B0.5: First batch of isolation sandboxes (parallel)

Repeat the pattern of B0.2 for:

- **B0.3:** llama.cpp Metal Q4 Llama 8B baseline (claim: ~25-30 tok/s on M4 base)
- **B0.4:** SGLang Q4 Llama 8B with RadixAttention (claim: 2.5-5× over vLLM-default on shared-prefix workload)
- **B0.5:** vLLM + EAGLE-3 Q4 Llama 8B (claim: 1.5-2.5× single-user speedup)

Each follows the same 5-step pattern: `expected.json`, `docker-compose.yml`, `bench.py`, run, commit.

### Task B0.6: First memory-layer sandbox — Mem0 vs Letta vs plain RAG on LongMemEval

This is the **most strategically important Phase 0 sandbox** because the spec just changed Letta → Mem0 based on research. We owe ourselves a measurement that confirms or refutes that decision on our hardware with our workload.

**Files:**
- Create: `bench/isolation/memory-layers/{mem0-llama8b-longmemeval,letta-llama8b-longmemeval,plain-rag-llama8b-longmemeval}/`

Each sandbox runs Llama 3.1 8B + the named memory layer through LongMemEval's 500-turn synthetic conversations and scores recall accuracy.

**`expected.json`** for `mem0-llama8b-longmemeval`:

```json
{
  "hypothesis_id": "mem0-llama8b-longmemeval-recall",
  "claim": "Mem0 v3 + Llama 3.1 8B achieves ≥+15pp recall accuracy on LongMemEval vs plain RAG baseline; Mem0 outperforms Letta with same model",
  "metric": "longmemeval_recall_accuracy",
  "thresholds": {
    "confirm_at_least_vs_baseline_pp": 10.0,
    "confirm_at_least_vs_letta_pp": 5.0
  },
  "workload": "memory-recall-longmemeval.jsonl",
  "source_for_claim": "https://mem0.ai/blog/state-of-ai-agent-memory-2026 + Letta engineering blog",
  "timeout_seconds": 7200
}
```

The sandbox:
1. Spins up Mem0 (or Letta) + llama.cpp serving Llama 3.1 8B
2. Replays 500 LongMemEval conversations
3. Records recall accuracy per question
4. Outputs Parquet with per-question correctness

This single benchmark validates (or refutes) the highest-stakes spec change of v0.2.

### Task B0.7: First combination sandbox — full v1 NVIDIA stack baseline

Path: `bench/combination/06-full-stack-llama8b-vllm/`

What it measures: vLLM + Q4 + RadixAttention + EAGLE-3 + 50-user shared-prefix workload, all together.

Expected per stack-up math from research synthesis: ~15× aggregate vs naive vLLM-FP16-no-cache baseline (combination 01).

The verdict — does the full stack actually achieve 15× over baseline 01? — is **the load-bearing measurement of the entire OCM thesis.** If it doesn't reproduce, the spec is wrong, and we fix it before locking decisions in user-facing code.

### Task B0.8: GitHub Actions integration

**Files:**
- Create: `.github/workflows/bench.yml`

The workflow runs the full isolation suite on:
- Linux + CPU-only (every PR — fast, validates framework health)
- macOS + Metal (nightly via self-hosted runner if available, else weekly via GitHub macOS runner)
- NVIDIA RTX 4090 / 5090 (weekly via Modal)

Results are uploaded as workflow artifacts and published to the `/benchmarks` page on the website.

### Task B0.9: Anonymization layer for human eval

**Files:**
- Create: `bench/bench/anonymize.py`

For combination sandboxes that produce subjective comparisons (e.g., "is the response with Mem0 better than the response with plain RAG?"), the framework:
1. Generates outputs with each tool
2. Assigns blind UUID labels (mapping stored separately)
3. Presents shuffled side-by-side to evaluators
4. Records evaluator choice
5. Reveals mapping after ≥20 evaluations recorded

This eliminates evaluator bias when ranking quality.

### Task B0.10: Retro-sync dashboard

**Files:**
- Create: `bench/analysis/retro_sync_dashboard.py`, `bench/bench/publish.py`

Dashboard queries DuckDB across all `bench/results/` and produces:
- Per-hypothesis time series (any regression detected?)
- Per-hardware-class capacity ladder (have we improved on RTX 4090 over time?)
- Combination-vs-sum-of-parts analysis (do stacked tools deliver multiplied benefits or do they interfere?)

Output: Markdown + JSON consumed by the website's `/benchmarks` page.

### Phase 0 verification gate

- [ ] `bench list` shows ≥10 isolation sandboxes
- [ ] `bench run` works end-to-end on at least one sandbox per hardware class we own
- [ ] First combination sandbox runs and produces a verdict
- [ ] At least 1 sandbox has CONFIRMED status (research-claimed number reproduces)
- [ ] At least 1 sandbox shows interesting variance from research claim (REFUTED or INCONCLUSIVE) — a feature, not a bug — and the spec is updated accordingly
- [ ] Retro-sync dashboard produces a valid markdown report from results/

---

## Phase 1+ deliverables (Weeks 3+)

After Phase 0 establishes the framework, additional sandboxes are added incrementally as the v1 stack is integrated:

- **Phase 1:** Mem0 / vLLM / llama.cpp combination sandbox (does our v1 stack hit its target on real hardware?)
- **Phase 2:** OpenAI-compat shim overhead sandbox (how much does our HTTP layer cost?)
- **Phase 2:** MCP tool-calling correctness sandbox (does our adapter introduce errors?)
- **Phase 3:** End-to-end installer + first-chat smoke benchmark (the user-facing experience metric)
- **Phase 3:** Quality benchmarks (MMLU, GSM8K, BFCL v3) on Qwen3-30B-A3B vs Llama 3.1 8B (model-pick justification)

---

## Honesty principles

- **No cherry-picked numbers.** Median-of-3 minimum; std-dev reported.
- **No hidden methodology.** Every benchmark sandbox has a README explaining what's measured and what's NOT.
- **No moving goalposts.** `expected.json` is locked at sandbox creation; results are scored against the original hypothesis.
- **REFUTED is celebrated.** When a benchmark refutes a research claim, that's a successful framework run, not a failure. The framework is doing its job.
- **INCONCLUSIVE is a valid verdict.** When data is noisy or the threshold is borderline, we don't force a binary outcome.
- **Every published number is reproducible.** If we publish "OCM v1 stack achieves 15× per node," anyone can `git clone && bench run combination/06-full-stack-llama8b-vllm` and verify.

---

## Risk callouts

| Risk | Likelihood | Mitigation |
|---|---|---|
| Bench framework is slow to iterate (each sandbox takes hours to write) | Medium | Template-driven sandbox creation; first 5 are hand-built, then a `bench scaffold` command generates new ones |
| Modal cloud GPU costs balloon | Low-Medium | Hard-cap monthly Modal spend ($200/mo at start); local hardware first, cloud only for hardware classes we don't own |
| Reproducibility breaks across Docker versions | Low | Pin Docker image digests; document Docker version in provenance |
| Quality benchmarks (MMLU, GSM8K) take many hours | High | Run quality benchmarks weekly, not per-PR; sample subsets for fast feedback |
| Bench framework grows into its own product | Medium | Internal-first principle. No public-facing features beyond `/benchmarks` page until v1 ships. |

---

## Tool ecosystem we're standing on the shoulders of

The bench framework borrows heavily, originally writes very little:

| Component | Borrowed from |
|---|---|
| Quality benchmarks (MMLU, GSM8K, etc.) | `lm-evaluation-harness` (EleutherAI) |
| Tool-calling benchmarks | Berkeley Function Calling Leaderboard v3 |
| Memory benchmarks | LongMemEval dataset (Mem0/Zep papers) |
| Agent benchmarks | GAIA subset (Princeton HAL) |
| Code agent benchmarks | SWE-bench Lite |
| Container orchestration | Docker + docker-compose |
| Cloud GPU bursting | Modal |
| Statistical comparison | scipy.stats |
| Storage / queries | Parquet (pyarrow) + DuckDB |
| CI | GitHub Actions |

Our original code is the **runner**, **anonymization layer**, **provenance capture**, **retro-sync dashboard**, and **per-hypothesis verdict logic**. ~3-5K lines.
