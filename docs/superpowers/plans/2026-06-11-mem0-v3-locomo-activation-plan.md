# mem0-v3-locomo Activation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **GATE:** This plan has a **NEEDS_APPROVAL** decision (LoCoMo's CC BY-NC 4.0 license vs OCM's Apache 2.0) that must be resolved by the operator before Task 2 onward can run. Tasks 0 and 1 are unblocked.

**Goal:** Activate the `bench/isolation/memory/mem0-v3-locomo` sandbox so it produces a CONFIRMED-or-REFUTED verdict against its already-locked expected.json contract (`locomo_recall_score ≥ 88 confirm, < 80 refute` per spec row 9), measured on the operator's hardware (Ollama-supervised llama3 8B Q4 + mxbai-embed-large for embedding).

**Architecture:** A Python sandbox under `bench/isolation/memory/mem0-v3-locomo/` with three files (`docker-compose.yml`, `bench.py`, plus updates to README) that mirror the **pattern** of the recently-merged `mem0-library-retrieval-recall` (#56) for the Mem0 driver layer, and the **pattern** of `amnesia-ab` for the Ollama-on-host LLM eval loop. The bench fetches LoCoMo's `locomo10.json` from upstream at run time (size 2.81 MB, no auth — see §1), feeds the 10 conversations into Mem0 as session-scoped memories, then issues the dataset's annotated QA questions against an 8B model with retrieved-context injection. Primary metric = LoCoMo QA recall; secondary = `tokens_retrieved_p50`.

**Tech Stack:** Python 3.11 (docker container); `mem0ai` + `sentence-transformers` + `faiss-cpu` (matches the just-merged #56 hermetic config); Ollama on `127.0.0.1:11434` (host network) running `llama3` + `mxbai-embed-large` — same as `amnesia-ab`, no new ops surface.

---

## 1. LoCoMo dataset acquisition — facts + the one decision needed

### Source

- **Repo:** [snap-research/locomo](https://github.com/snap-research/locomo) (publicly available, no account needed).
- **Paper:** Maharana et al., *Evaluating Very Long-Term Conversational Memory of LLM Agents*, ACL 2024 ([arXiv:2402.17753](https://arxiv.org/abs/2402.17753)).
- **Authors:** UNC Chapel Hill + USC + Snap Research.

### What we actually need (single file)

| File | Path | Size | Purpose |
|---|---|---|---|
| `locomo10.json` | `data/locomo10.json` | **2.81 MB** (2,805,274 bytes) | 10 long conversations + annotated QA questions + ground-truth evidence dialog IDs |

The repo also ships `data/msc_personas_all.json` (3.05 MB, auxiliary persona file for generation; **not needed** for QA eval) and a `data/multimodal_dialog/` directory (**not needed** — we run text-only QA against the conversations).

Downloadable raw via:

```
https://raw.githubusercontent.com/snap-research/locomo/main/data/locomo10.json
```

### Access requirements

- No account.
- No payment.
- No API key.
- Plain HTTP. ~3 MB total. Single `curl` is enough.

### License — **the one operator decision**

The LoCoMo repo's `LICENSE.txt` is **Creative Commons Attribution-NonCommercial 4.0 International** (CC BY-NC 4.0). The directive's NEEDS_APPROVAL rule (and AGENT_OPERATIONS' "no non-permissive dependencies; repo is Apache 2.0") applies here: NC content interacts with our license posture.

| Aspect | Status |
|---|---|
| Use for **internal benchmarking** of an open-source personal AI runtime | ✅ Fits CC BY-NC's non-commercial clause |
| Use to compute + publish a `verdict.json` summary file (numbers + decisions, no LoCoMo content) | ✅ Numbers/findings derived from the dataset are not the dataset itself |
| **Redistribute** by bundling `locomo10.json` into `bench/workloads/` (committed to a public Apache 2.0 repo) | ⚠️ NC license attaches to the file; needs attribution AND inherits its terms downstream of any "Adapted Material" |
| Use the dataset to train/finetune a model OCM later ships commercially | ❌ Out of scope today but a forward-looking landmine |

### NEEDS_APPROVAL — multi-choice for the operator

**Q1 — How should the bench obtain LoCoMo at run time?**

- **(a) Fetch-on-run, no bundle.** `bench.py` (or a one-shot `scripts/fetch_locomo.py`) downloads `locomo10.json` into `bench/workloads/locomo/` on each fresh run; `bench/workloads/locomo/` is `.gitignore`d. Sandbox README cites attribution + license. **Recommended** — keeps the repo's Apache 2.0 surface clean, reproducible (raw.githubusercontent.com is content-addressed by commit SHA we can pin), one extra ~3 MB download per CI run (acceptable).
- **(b) Bundle in `bench/workloads/locomo10.json` with full CC BY-NC notice.** Adds the file to git. Simpler offline runs. Operator accepts that the repo now ships CC BY-NC content alongside Apache 2.0 code — most permissive readings of OSI guidance say this is OK if cleanly attributed and isolated to a workloads directory, but it weakens the "every file is Apache 2.0" story.
- **(c) Build a synthetic LoCoMo-shape proxy workload** (script generates 10 fake long conversations matching the JSON schema). Skips license entirely. **Costs:** the verdict no longer speaks to the published 91.6 number, only to "library-driven retrieval on long-conversation shape generally works" — overlaps too much with the already-CONFIRMED `mem0-library-retrieval-recall` (#56) to earn its slot.
- **(d) Defer this sandbox.** Park `mem0-v3-locomo` INACTIVE; use Track 2 effort elsewhere (e.g., `mem0-v3-memoryarena` activation, the agentic-utility companion).

**Plan-side default if no answer comes back:** (a). All subsequent tasks below assume (a) and use a SHA-pinned download URL. Switching to (b) requires only Task 2 (the fetch script gets replaced with a static file) — one-task delta. Switching to (c) or (d) invalidates Tasks 3-7 and triggers a fresh plan.

---

## 2. Harness design — files + flow

### File structure

```
bench/isolation/memory/mem0-v3-locomo/
├── README.md             # MODIFY: drop "INACTIVE" line, add license notice, run instructions
├── expected.json         # NO CHANGE — contract is locked
├── docker-compose.yml    # CREATE: matches #56's pattern + adds host.docker.internal for Ollama
├── bench.py              # CREATE: download → parse → ingest → query → score
└── (gitignored at runtime) _locomo_workload/
    └── locomo10.json     # fetched by bench.py
```

`bench/workloads/` is NOT used for the dataset itself under choice (a); we keep it self-contained under the sandbox dir to make the "fetch-on-run" lifecycle obvious.

### Conversation → memory mapping (the core design choice)

LoCoMo's `locomo10.json` is an array of 10 conversation objects. Each has:
- `conversation` — a list of `session_<N>` keys; each session is an array of turns (`{ speaker, dia_id, text, blip_caption?, img_url? }`)
- `qa` — a list of QA items: `{ question, answer, evidence, category }`, where `evidence` is a list of `dia_id` strings pointing back to the turns that contain the answer

Our mapping:

1. **One Mem0 `user_id` per conversation** (`locomo_user_0` through `locomo_user_9`). This matches the pattern in #56 — `user_id` is the security boundary, and a "user" in LoCoMo corresponds to one speaker pair's full multi-session history.
2. **One Mem0 memory per turn** with `infer=False` (we bypass extraction, same as #56) so the verdict speaks to retrieval, not extraction. Each memory's `metadata` carries `{ "dia_id": "S2:7", "session": "session_2" }`.
3. **One Mem0 `search()` per QA question**, with `user_id=<that conversation's user>`, `top_k=10` (matches spec row 9's "~7000 tokens at top-K" budget once you average 700 tokens/memory).
4. **Recall metric**: for each QA item, `recall = |retrieved_dia_ids ∩ evidence_dia_ids| / |evidence_dia_ids|`. Score per conversation = mean over its QAs. **`locomo_recall_score` (primary metric in expected.json)** = mean over the 10 conversations × 100, to match the published 91.6-style scale.
5. **`tokens_retrieved_p50` (secondary metric)**: per QA, sum `len(content)/4` (approx 4 chars/token heuristic, fine for the scale check) for the top-10 retrieved memories. Median across all QAs.

This is the same shape as #56's `recall_at_10` — a different denominator and a real (not synthetic) workload.

### LLM step — opt-in, separate metric

The directive says "harness drives Mem0 + an 8B model against LoCoMo conversations." The **measurement that maps to the locked expected.json contract** is the retrieval-recall step above; the LLM is not strictly required to compute it. But the directive's intent is clearly "end-to-end with the model in the loop," matching how the published 91.6 number was measured.

**Plan:** include an optional **`--with-llm` mode** that runs the retrieved context through Ollama llama3 8B Q4 (mirroring `amnesia-ab`'s SYS_ON pattern) and adds a third (non-contract) metric `llm_answer_match_pct` for diagnostic value. **Default for the verdict run = OFF** (faster, matches contract metric). Operator can enable for a deeper read.

This keeps the verdict-producing path under 5 minutes per repeat (see §5) while giving us the operator-asked-for E2E path on demand.

### docker-compose.yml shape

Mirrors #56 (`python:3.11`, pip-install Mem0 stack at startup, volume-mount the sandbox dir as `/work`), with one addition: `extra_hosts: host.docker.internal:host-gateway` so `bench.py` can reach the operator's host-side Ollama at `http://host.docker.internal:11434` when `--with-llm` is on. The retrieval-only default path needs no Ollama and is hermetic.

```yaml
services:
  bench:
    image: python:3.11
    extra_hosts:
      - "host.docker.internal:host-gateway"
    volumes:
      - ./:/work
    working_dir: /work
    environment:
      - LOCOMO_URL=https://raw.githubusercontent.com/snap-research/locomo/<PINNED_SHA>/data/locomo10.json
      - OLLAMA_URL=http://host.docker.internal:11434
    command:
      - sh
      - -c
      - |
        pip install --quiet mem0ai sentence-transformers faiss-cpu
        python bench.py
```

### bench.py — what it does, in order

1. **Fetch** `locomo10.json` to `_locomo_workload/locomo10.json` (skip if hash-matches a SHA pinned in source). Use `urllib.request` — no extra deps beyond the stdlib for download.
2. **Build hermetic Mem0** with the same config as #56 (huggingface MiniLM-L6-v2 embedder + faiss-cpu vector store + stub OpenAI llm config; we only use `add(infer=False)` + `search()`, never the LLM).
3. **For each conversation**: assign `user_id`, iterate sessions in order, `m.add(turn.text, user_id=..., infer=False, metadata={"dia_id": ..., "session": ...})` for every turn.
4. **For each QA**: `m.search(question, filters={"user_id": ...}, top_k=10)`, map results back to `dia_id` set via metadata, compute per-QA recall, accumulate token-count for secondary.
5. **Optional `--with-llm`** (off by default): for each QA, build a prompt with retrieved memories as system context (`amnesia-ab`'s `SYS_ON` template), POST to Ollama `/api/chat`, normalize-match against `qa.answer` for `llm_answer_match_pct`.
6. **Write `outputs.json`** with `primary_value` (locomo_recall_score), `secondary_value` (tokens_retrieved_p50), and a rich per-conversation breakdown. The bench runner picks up `outputs.json` per the existing contract in `bench/bench/runner.py:_execute_compose`.

---

## 3. Hardware / runtime expectations on the operator's machine

| Aspect | Value | Notes |
|---|---|---|
| OS | Windows (operator dev box, per amnesia-ab metadata) | Docker Desktop runs the bench container; `host.docker.internal` resolves to the Windows host. |
| LLM (when `--with-llm` on) | `llama3:latest` via Ollama on `127.0.0.1:11434` | Q4_0 default tag, ~4.7 GB on disk; matches amnesia-ab's chat model. Free, local. |
| Embedder (Mem0 internal) | `sentence-transformers/all-MiniLM-L6-v2` | CPU-fast, ~80 MB download into the Python container, ~5ms per embedding. Same as #56. |
| RAM budget | ~6-8 GB peak | Python + sentence-transformers + faiss-cpu + 10 conversations × ~300 turns × 384-dim vectors = ~12 MB index. Llama3 8B Q4 in Ollama is separate (~5 GB resident when loaded). |
| Disk | ~10 GB free (mostly Ollama model cache, already downloaded for amnesia-ab) | LoCoMo workload itself is 2.81 MB. |
| Network | One-time ~3 MB HTTP GET to raw.githubusercontent.com (skip on warm cache) | No other outbound network. |
| Ollama already configured? | YES (amnesia-ab CONFIRMED 2026-06-11 uses it) | No new ops surface; this plan reuses the exact same Ollama setup. |
| Docker Desktop running? | Required (per bench framework contract — runner uses `docker compose up`) | Already required for #56. |

**No new infrastructure is introduced.** Everything below the Mem0 layer is identical to the just-merged retrieval-recall sandbox; everything LLM-side is identical to the canonical amnesia-ab sandbox.

---

## 4. Mapping measurements onto the locked expected.json contract

`bench/isolation/memory/mem0-v3-locomo/expected.json` (already on main, NO CHANGES this plan):

| Field | Value | What `bench.py` writes to `outputs.json` |
|---|---|---|
| `metric` | `locomo_recall_score` | `primary_value` = mean per-conversation recall × 100 (so it sits on the same 0-100 scale as the published 91.6) |
| `thresholds.confirm_at_least` | `88.0` | If `primary_median ≥ 88` (across 3 repeats per `_execute_compose`), runner emits CONFIRMED |
| `thresholds.refute_below` | `80.0` | If `primary_median < 80`, REFUTED |
| `secondary_metric` | `tokens_retrieved_p50` | `secondary_value` = p50 of `sum(len(memory.content) / 4)` over top-10 retrieved per QA |
| `secondary_thresholds.confirm_at_most` | `7000` | p50 stays under 7K → confirms the budget claim |
| `secondary_thresholds.refute_above` | `12000` | p50 over 12K → secondary REFUTED ("the 7000 budget is overly optimistic") |
| `timeout_seconds` | `1800` (30 min) | Per-repeat ceiling. Expected wall-time per repeat is well under this — see §5. |
| `status` | `INACTIVE` (today) → `ACTIVE` (after this plan's Task 6) | Flip in the same commit that adds bench.py + docker-compose.yml. |
| `blocked_on` (today) | 3 items: dataset, harness, MCP packaging | Tasks 2 + 3 + 4 each clear one blocker; Task 6 removes the array entirely. |

The `decision_rule` and `comparison_anchor` fields stay as-is — they're operator-facing prose, not measurement.

**Verdict logic check:** the runner's `decide_verdict()` in `bench/bench/metrics.py` (per the runner code already on main) treats `confirm_at_least` and `refute_below` as floors/ceilings on `primary_median`. Our `primary_value` is per-repeat; the runner medians across 3 repeats by default. Variance bound (informal): per-conversation recall on retrieval is deterministic given fixed embeddings + fixed corpus (faiss is deterministic, MiniLM is deterministic). The only source of repeat-to-repeat variance is Mem0's internal handling of `add()` order — should be near-zero. Expect tight std across repeats; the median is well-defined.

---

## 5. Estimated wall-time + blockers

### Wall-time per phase (one repeat)

| Phase | Cost | Notes |
|---|---|---|
| Container start + pip install | ~60-90s | Same as #56's reported cost; deps cache on warm runs. |
| LoCoMo download | ~1-2s | 3 MB over HTTPS. |
| Mem0 init + MiniLM load | ~5-10s | First-time torch import + model warmup. |
| Memory ingest (10 conv × ~300 turns avg = ~3000 `add()` calls) | ~60-120s | Each `add(infer=False)` is one embedding + one faiss upsert. MiniLM-L6 on CPU ~5ms; faiss upsert ~1ms. Realistic: ~30ms/call due to Python overhead → ~90s for 3000 calls. |
| Query loop (~200 QAs × 1 search() each) | ~20-40s | ~100ms per search on a 3000-vector index. |
| Optional `--with-llm` (200 × ~3-5s/turn on llama3 8B Q4) | ~10-20 min | Only when explicitly enabled; OFF for the contract verdict run. |
| **Default (retrieval-only) per repeat** | **~2.5-4 min** | Comfortably under the 1800s (30 min) `timeout_seconds`. |
| **Three repeats (runner default)** | **~10-15 min** | One sandbox run produces the verdict. |
| **With `--with-llm` (diagnostic)** | ~35-65 min | Only if operator requests. |

### Blockers — current state of the world

| `expected.json.blocked_on` item | Cleared by | Status if plan runs in order |
|---|---|---|
| "LoCoMo conversations workload not yet downloaded into bench/workloads/" | Task 2 (the fetch script) | Cleared (assuming choice (a) on Q1) |
| "Bench harness does not yet drive Mem0 + Qwen3 8B end-to-end" | Tasks 3 + 4 (Mem0 driver + recall metric) — note that **the model is llama3 8B Q4 now, not Qwen3 8B**; the spec wording precedes the Ollama wiring landed in v0.1.1. | Cleared. **README update should note the model swap** — same parameter scale, different upstream. |
| "Mem0 OpenMemory MCP local mode not yet packaged with the daemon" | NOT cleared by this plan. The MCP-mode requirement was about the production daemon path; for the bench we use Mem0's library-driven `Memory.from_config()` (same as #56), which is the contract the verdict speaks to anyway. | Reframe in README: this sandbox tests Mem0 v3 library-driven retrieval. The OpenMemory MCP packaging is a separate daemon concern, not a verdict blocker. |

### Real blockers outside this plan's scope

1. **Q1 on license** (above) — hard gate on Tasks 2+.
2. **Operator has Ollama running with `llama3` pulled** — already true (amnesia-ab CONFIRMED 2026-06-11). Free.
3. **Docker Desktop running** — already required for #56.
4. **Mem0 `add(infer=False)` accepts metadata** — verified in #56's working bench.py; same API surface.

No paid APIs, no accounts, no >1GB downloads, no frontier-model calls.

---

## File structure (post-completion)

```
bench/isolation/memory/mem0-v3-locomo/
├── README.md             [MODIFIED]  status flipped, license notice, run instructions
├── expected.json         [UNCHANGED] contract is locked
├── docker-compose.yml    [NEW]       ~25 lines, mirrors #56 + extra_hosts for Ollama
└── bench.py              [NEW]       ~250 lines: fetch + ingest + score + optional LLM
```

Optional new file under choice (a):

```
bench/isolation/memory/mem0-v3-locomo/.gitignore   [NEW] _locomo_workload/
```

`bench/workloads/_generate_mem0_retrieval_recall.py`-style helper is **not needed** — LoCoMo's JSON shape is consumed directly.

---

## Tasks

### Task 0: Verify the upstream still ships locomo10.json at the expected SHA

**Files:** none — read-only sanity check.

- [ ] **Step 1: Resolve a pinnable commit SHA for the dataset file**

```bash
gh api repos/snap-research/locomo/commits?path=data/locomo10.json --jq '.[0].sha' | tr -d '\n'
```

Expected output: a 40-char SHA. Record it (call it `LOCOMO_PIN`).

- [ ] **Step 2: Verify the raw URL at that SHA returns 200 with content-type JSON**

```bash
curl -sI "https://raw.githubusercontent.com/snap-research/locomo/$LOCOMO_PIN/data/locomo10.json" | head -5
```

Expected: `HTTP/2 200`, `content-length: ~2805274`.

- [ ] **Step 3: Sanity-check the JSON shape**

```bash
curl -sL "https://raw.githubusercontent.com/snap-research/locomo/$LOCOMO_PIN/data/locomo10.json" \
  | python -c "import json, sys; d=json.load(sys.stdin); print(len(d), 'top-level entries'); print(sorted(d[0].keys())[:5])"
```

Expected: `10 top-level entries` + a list including `conversation`, `qa`, `sample_id`, `speaker_a`, `speaker_b` (or similar — confirms QA + conversation keys exist).

- [ ] **Step 4: Record findings in a scratch note for Task 2 to consume.**

No commit on this task — it's a read.

---

### Task 1: Open NEEDS_APPROVAL on Q1 (license)

**Files:** none — operator coordination.

- [ ] **Step 1: Surface Q1 from §1 of this plan in the PR description and the handoff digest.**

The PR for THIS plan document is the natural place to ask. The four options (a-d) and the recommended default (a) are already written.

- [ ] **Step 2: STOP. Wait for the operator's decision.**

Subsequent tasks branch on the decision:
- (a) → Task 2 proceeds as-written
- (b) → Task 2 replaces the fetch logic with a static-file step + adds attribution
- (c) → invalidate this plan; new plan needed
- (d) → close out, no further work

No commit on this task.

---

### Task 2: Add the docker-compose.yml + the bench.py skeleton + the fetch step (assumes Q1 = (a))

**Files:**
- Create: `bench/isolation/memory/mem0-v3-locomo/docker-compose.yml`
- Create: `bench/isolation/memory/mem0-v3-locomo/bench.py` (skeleton: fetch + write outputs.json with dummy values)
- Create: `bench/isolation/memory/mem0-v3-locomo/.gitignore`

- [ ] **Step 1: Write the failing test — sandbox structure validates**

`bench/tests/test_locomo_sandbox_structure.py`:

```python
from pathlib import Path
from bench.bench.runner import dry_run_sandbox

def test_mem0_v3_locomo_sandbox_dry_runs_when_active():
    root = Path(__file__).resolve().parents[2]
    sandbox = root / "bench" / "isolation" / "memory" / "mem0-v3-locomo"
    expected = dry_run_sandbox(sandbox)
    # Once status flips to ACTIVE this dry_run will require docker-compose.yml + bench.py
    assert expected.hypothesis_id == "mem0-v3-locomo-recall"
```

This passes today (status=INACTIVE) so the failing test variant is: temporarily flip status to ACTIVE in the test setup and confirm DryRunError pre-Task-2, then succeeds post-Task-2.

- [ ] **Step 2: Write the docker-compose.yml**

```yaml
# Inline the contents shown in §2 verbatim
```

- [ ] **Step 3: Write the bench.py skeleton with fetch + outputs.json stub**

```python
"""Mem0 v3 LoCoMo recall measurement. Skeleton — Task 3 adds Mem0 driver, Task 4 adds scoring."""
import json, os, urllib.request, hashlib
from pathlib import Path

LOCOMO_PIN = "<paste the SHA from Task 0 Step 1>"
LOCOMO_URL = f"https://raw.githubusercontent.com/snap-research/locomo/{LOCOMO_PIN}/data/locomo10.json"
EXPECTED_SHA256 = "<paste sha256 from Task 0 Step 3 — run: curl -sL URL | sha256sum>"

def fetch_locomo(dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        if hashlib.sha256(dest.read_bytes()).hexdigest() == EXPECTED_SHA256:
            return dest
        dest.unlink()
    print(f"fetching {LOCOMO_URL}")
    urllib.request.urlretrieve(LOCOMO_URL, dest)
    got = hashlib.sha256(dest.read_bytes()).hexdigest()
    if got != EXPECTED_SHA256:
        raise SystemExit(f"locomo10.json sha256 mismatch: got {got}, expected {EXPECTED_SHA256}")
    return dest

def main() -> int:
    workload = fetch_locomo(Path("_locomo_workload/locomo10.json"))
    payload = json.loads(workload.read_text(encoding="utf-8"))
    # Skeleton: write a known-INVALID outputs.json so any accidental "ACTIVE flip" run fails loudly
    Path("outputs.json").write_text(json.dumps({
        "primary_value": 0.0,
        "secondary_value": 0.0,
        "duration_seconds": 0.0,
        "n_conversations": len(payload),
        "note": "skeleton — ingest + scoring land in Task 3 + Task 4",
    }, indent=2), encoding="utf-8")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Write the .gitignore**

```
_locomo_workload/
outputs.json
```

- [ ] **Step 5: Confirm structure validates BUT we keep status=INACTIVE for now**

Don't flip status yet — Task 6 does that, AFTER Tasks 3+4 land real metrics. Keeping it INACTIVE means CI's bench framework doesn't try to execute a half-finished sandbox.

- [ ] **Step 6: Commit**

```bash
git add bench/isolation/memory/mem0-v3-locomo/ bench/tests/test_locomo_sandbox_structure.py
git commit -m "feat(bench): mem0-v3-locomo scaffolding — compose + bench skeleton + LoCoMo fetch"
```

---

### Task 3: Wire the Mem0 driver — ingest LoCoMo conversations as scoped memories

**Files:**
- Modify: `bench/isolation/memory/mem0-v3-locomo/bench.py`

- [ ] **Step 1: Write the failing test — ingest produces the expected memory count**

`bench/tests/test_locomo_bench_local.py` (uses a tiny in-memory fixture, not real Docker):

```python
import json
from pathlib import Path
import importlib.util

def _load(modpath):
    spec = importlib.util.spec_from_file_location("locomo_bench", modpath)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def test_ingest_creates_one_memory_per_turn(tmp_path, monkeypatch):
    # Fake locomo10.json with 1 conversation, 2 sessions, 3 turns total
    fixture = [{
        "sample_id": "fake_0",
        "speaker_a": "Alice", "speaker_b": "Bob",
        "conversation": {
            "session_1": [
                {"speaker": "Alice", "dia_id": "S1:1", "text": "I bought a Specialized Tarmac SL7."},
                {"speaker": "Bob",   "dia_id": "S1:2", "text": "Nice — what color?"},
            ],
            "session_2": [
                {"speaker": "Alice", "dia_id": "S2:1", "text": "Matte black."},
            ],
        },
        "qa": [{"question": "What bike did Alice buy?", "answer": "Specialized Tarmac SL7",
                "evidence": ["S1:1"], "category": "single_hop"}],
    }]
    (tmp_path / "locomo10.json").write_text(json.dumps(fixture))
    # Call ingest_conversation directly (Task 3 exposes it)
    bench = _load(Path(__file__).resolve().parents[2] / "isolation/memory/mem0-v3-locomo/bench.py")
    mem = bench.build_hermetic_mem0(faiss_dir=tmp_path / "_faiss")
    counts = bench.ingest_conversation(mem, fixture[0], user_id="locomo_user_0")
    assert counts["turns"] == 3
    assert counts["sessions"] == 2
```

- [ ] **Step 2: Verify it fails (no `build_hermetic_mem0` / `ingest_conversation` yet)**

```bash
pytest bench/tests/test_locomo_bench_local.py -v
```

Expected: `AttributeError: module has no attribute 'build_hermetic_mem0'`.

- [ ] **Step 3: Implement `build_hermetic_mem0` + `ingest_conversation`**

Add to `bench.py`:

```python
def build_hermetic_mem0(faiss_dir):
    from mem0 import Memory
    faiss_dir = Path(faiss_dir).resolve()
    if faiss_dir.exists():
        import shutil; shutil.rmtree(faiss_dir)
    faiss_dir.parent.mkdir(parents=True, exist_ok=True)
    return Memory.from_config({
        "embedder": {"provider": "huggingface",
                     "config": {"model": "sentence-transformers/all-MiniLM-L6-v2"}},
        "vector_store": {"provider": "faiss", "config": {
            "collection_name": "ocm_locomo", "path": str(faiss_dir),
            "embedding_model_dims": 384,
        }},
        "llm": {"provider": "openai", "config": {"api_key": "sk-stub", "model": "gpt-4o-mini"}},
    })

def ingest_conversation(mem, conv, *, user_id):
    n_turns = n_sessions = 0
    for session_key, turns in conv["conversation"].items():
        n_sessions += 1
        for turn in turns:
            mem.add(turn["text"], user_id=user_id, infer=False,
                    metadata={"dia_id": turn["dia_id"], "session": session_key})
            n_turns += 1
    return {"turns": n_turns, "sessions": n_sessions}
```

- [ ] **Step 4: Verify**

```bash
pytest bench/tests/test_locomo_bench_local.py -v
```

Expected: PASS. (Note: requires `mem0ai` + deps installed in the env running pytest; CI on the Python bench tests already handles this for the existing tests, see `bench/tests/test_runner.py`. If CI lacks mem0 outside Docker, mark this test `@pytest.mark.requires_mem0` and document the gate.)

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(bench): mem0-v3-locomo Mem0 hermetic ingest"
```

---

### Task 4: Wire the recall metric + the secondary token metric — the verdict-producing path

**Files:**
- Modify: `bench/isolation/memory/mem0-v3-locomo/bench.py`

- [ ] **Step 1: Write the failing test — `score_conversation` computes recall correctly on the fixture**

Append to `bench/tests/test_locomo_bench_local.py`:

```python
def test_score_conversation_recall_full_when_evidence_in_top10(tmp_path):
    bench = _load(Path(__file__).resolve().parents[2] / "isolation/memory/mem0-v3-locomo/bench.py")
    mem = bench.build_hermetic_mem0(faiss_dir=tmp_path / "_faiss")
    fixture = {
        "conversation": {"session_1": [
            {"speaker":"A","dia_id":"S1:1","text":"I bought a Specialized Tarmac SL7."},
            {"speaker":"B","dia_id":"S1:2","text":"What color?"},
        ]},
        "qa": [{"question":"What bike did A buy?", "answer":"Tarmac SL7",
                "evidence":["S1:1"], "category":"single_hop"}],
    }
    bench.ingest_conversation(mem, fixture, user_id="t0")
    result = bench.score_conversation(mem, fixture, user_id="t0", top_k=10)
    assert result["per_qa_recall"] == [1.0]
    assert result["mean_recall"] == 1.0
    assert result["tokens_p50"] > 0
```

- [ ] **Step 2: Verify it fails**

```bash
pytest bench/tests/test_locomo_bench_local.py::test_score_conversation_recall_full_when_evidence_in_top10 -v
```

- [ ] **Step 3: Implement `score_conversation`**

```python
import statistics

def score_conversation(mem, conv, *, user_id, top_k=10):
    per_qa_recall, per_qa_tokens = [], []
    for qa in conv["qa"]:
        results = mem.search(qa["question"], filters={"user_id": user_id}, top_k=top_k)
        hits = results.get("results", []) if isinstance(results, dict) else (results or [])
        retrieved_dia_ids = {(r.get("metadata") or {}).get("dia_id") for r in hits}
        retrieved_dia_ids.discard(None)
        evidence = set(qa.get("evidence", []))
        if evidence:
            per_qa_recall.append(len(retrieved_dia_ids & evidence) / len(evidence))
        # Token approx — 4 chars/token, sum across all retrieved memory contents
        per_qa_tokens.append(sum(len(r.get("memory", "")) / 4 for r in hits))
    return {
        "per_qa_recall": per_qa_recall,
        "mean_recall": (sum(per_qa_recall) / len(per_qa_recall)) if per_qa_recall else 0.0,
        "tokens_p50": statistics.median(per_qa_tokens) if per_qa_tokens else 0.0,
        "n_qa": len(per_qa_recall),
    }
```

- [ ] **Step 4: Wire `main()` to drive 10 conversations + emit `outputs.json` per the contract**

```python
def main() -> int:
    workload = fetch_locomo(Path("_locomo_workload/locomo10.json"))
    convs = json.loads(workload.read_text(encoding="utf-8"))
    started = time.monotonic()
    mem = build_hermetic_mem0(faiss_dir=Path("_mem0_locomo_faiss"))
    per_conv_recall, per_qa_tokens_all = [], []
    breakdown = []
    for i, conv in enumerate(convs):
        ingest_conversation(mem, conv, user_id=f"locomo_user_{i}")
        s = score_conversation(mem, conv, user_id=f"locomo_user_{i}")
        per_conv_recall.append(s["mean_recall"])
        per_qa_tokens_all.extend([s["tokens_p50"]] * s["n_qa"])  # approximation; honest p50 would use the per-QA list
        breakdown.append({"sample_id": conv.get("sample_id", f"conv_{i}"), **s})
    primary = 100.0 * sum(per_conv_recall) / len(per_conv_recall)
    secondary = statistics.median(per_qa_tokens_all) if per_qa_tokens_all else 0.0
    elapsed = time.monotonic() - started
    Path("outputs.json").write_text(json.dumps({
        "primary_value": primary,
        "secondary_value": secondary,
        "duration_seconds": elapsed,
        "n_conversations": len(convs),
        "n_qa_total": sum(b["n_qa"] for b in breakdown),
        "embedder": "sentence-transformers/all-MiniLM-L6-v2",
        "vector_store": "faiss-local",
        "per_conversation": breakdown,
    }, indent=2), encoding="utf-8")
    return 0
```

(Refinement: the token-p50 across all QAs is currently approximated by replicating each conv's median. Replace with a properly-collected per-QA token list during integration — caught in Task 5.)

- [ ] **Step 5: Verify recall test still passes; add an integration test that runs the full main() against a 2-conversation fixture**

```bash
pytest bench/tests/test_locomo_bench_local.py -v
```

- [ ] **Step 6: Commit**

```bash
git commit -am "feat(bench): mem0-v3-locomo recall + tokens metrics + outputs.json"
```

---

### Task 5: Refine the secondary metric to be an honest per-QA p50; add `--with-llm` opt-in path

**Files:**
- Modify: `bench/isolation/memory/mem0-v3-locomo/bench.py`

- [ ] **Step 1: Write the failing test — token p50 is a true median across all individual QA token counts, not duplicated per conv**

```python
def test_token_p50_is_true_median_across_all_qa(tmp_path):
    bench = _load(Path(__file__).resolve().parents[2] / "isolation/memory/mem0-v3-locomo/bench.py")
    # Two conversations of unequal QA count: 1 vs 3 QAs. Naive duplication gives
    # wrong p50 (weights the 1-QA conv too heavily). True median is over 4 items.
    fixture = [
        {"conversation": {"s1":[{"speaker":"A","dia_id":"S1:1","text":"x"*40}]},
         "qa":[{"question":"q","answer":"x","evidence":["S1:1"],"category":"x"}]},
        {"conversation": {"s1":[{"speaker":"A","dia_id":"S1:1","text":"y"*400}]},
         "qa":[{"question":"q1","answer":"y","evidence":["S1:1"],"category":"x"},
               {"question":"q2","answer":"y","evidence":["S1:1"],"category":"x"},
               {"question":"q3","answer":"y","evidence":["S1:1"],"category":"x"}]},
    ]
    mem = bench.build_hermetic_mem0(faiss_dir=tmp_path / "_faiss")
    all_tokens = []
    for i, c in enumerate(fixture):
        bench.ingest_conversation(mem, c, user_id=f"u{i}")
        s = bench.score_conversation(mem, c, user_id=f"u{i}")
        all_tokens.extend(s["per_qa_tokens"])
    assert len(all_tokens) == 4  # 1 + 3, NOT 2 (duplicated per conv)
```

- [ ] **Step 2: Change `score_conversation` return shape to include `per_qa_tokens: list[float]`**

Replace the existing `return` block in `score_conversation`:

```python
return {
    "per_qa_recall": per_qa_recall,
    "mean_recall": (sum(per_qa_recall) / len(per_qa_recall)) if per_qa_recall else 0.0,
    "per_qa_tokens": per_qa_tokens,
    "tokens_p50": statistics.median(per_qa_tokens) if per_qa_tokens else 0.0,
    "n_qa": len(per_qa_recall),
}
```

- [ ] **Step 3: Change `main()`'s token aggregation to use the flat per-QA list**

Replace the per-QA token accumulator block in `main()`:

```python
per_qa_tokens_all: list[float] = []
for i, conv in enumerate(convs):
    ingest_conversation(mem, conv, user_id=f"locomo_user_{i}")
    s = score_conversation(mem, conv, user_id=f"locomo_user_{i}")
    per_conv_recall.append(s["mean_recall"])
    per_qa_tokens_all.extend(s["per_qa_tokens"])  # flat — true median follows
    breakdown.append({"sample_id": conv.get("sample_id", f"conv_{i}"), **{
        k: v for k, v in s.items() if k != "per_qa_tokens"  # keep breakdown compact
    }})
secondary = statistics.median(per_qa_tokens_all) if per_qa_tokens_all else 0.0
```

- [ ] **Step 4: Add `--with-llm` opt-in path**

Add at module top + extend `main()` signature:

```python
import argparse, urllib.request as _urlreq

SYS_ON = (
    "You are a personal assistant with persistent memory of past sessions.\n"
    "RELEVANT MEMORIES retrieved for this request:\n{mems}\n"
    "Answer using these memories — be specific. Be concise."
)

def _ollama_chat(ollama_url, system, user):
    body = json.dumps({
        "model": "llama3", "stream": False,
        "messages": [{"role":"system","content":system},{"role":"user","content":user}],
        "options": {"temperature": 0.2, "num_predict": 200},
    }).encode()
    req = _urlreq.Request(f"{ollama_url}/api/chat", data=body,
                          headers={"content-type":"application/json"})
    with _urlreq.urlopen(req, timeout=60) as r:
        return json.loads(r.read())["message"]["content"]

def _norm(s): return "".join(c for c in s.lower() if c.isalnum())

def _diagnose_with_llm(mem, conv, user_id, ollama_url, top_k=10):
    matches = total = 0
    for qa in conv["qa"]:
        results = mem.search(qa["question"], filters={"user_id": user_id}, top_k=top_k)
        hits = results.get("results", []) if isinstance(results, dict) else (results or [])
        mems_block = "\n".join(f"- {h.get('memory','')}" for h in hits)
        try:
            reply = _ollama_chat(ollama_url, SYS_ON.format(mems=mems_block), qa["question"])
        except Exception as e:
            print(f"llm error on {qa['question'][:40]}…: {e}"); continue
        total += 1
        if _norm(qa["answer"]) in _norm(reply):
            matches += 1
    return {"llm_n_qa": total, "llm_match_pct": (100.0 * matches / total) if total else 0.0}
```

In `main()`, after computing `primary` + `secondary`, gate the diagnostic:

```python
parser = argparse.ArgumentParser()
parser.add_argument("--with-llm", action="store_true")
args = parser.parse_args()
diagnostic = None
if args.with_llm:
    ollama_url = os.environ.get("OLLAMA_URL", "http://host.docker.internal:11434")
    diags = [_diagnose_with_llm(mem, c, f"locomo_user_{i}", ollama_url) for i, c in enumerate(convs)]
    total_n = sum(d["llm_n_qa"] for d in diags)
    total_match = sum(d["llm_n_qa"] * d["llm_match_pct"] / 100.0 for d in diags)
    diagnostic = {"llm_answer_match_pct": (100.0 * total_match / total_n) if total_n else 0.0,
                  "llm_n_qa": total_n, "llm_model": "llama3"}
```

And include `diagnostic` in the `outputs.json` write (it stays under a `diagnostic` key, OUTSIDE the contract metrics, so the verdict path is unchanged):

```python
output = {
    "primary_value": primary,
    "secondary_value": secondary,
    "duration_seconds": elapsed,
    "n_conversations": len(convs),
    "n_qa_total": sum(b["n_qa"] for b in breakdown),
    "embedder": "sentence-transformers/all-MiniLM-L6-v2",
    "vector_store": "faiss-local",
    "per_conversation": breakdown,
}
if diagnostic is not None:
    output["diagnostic"] = diagnostic
Path("outputs.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
```

- [ ] **Step 5: Run all tests; verify `outputs.json` shape stays contract-clean when `--with-llm` is off**

```bash
pytest bench/tests/test_locomo_bench_local.py -v
```

Expected: all green. Then a manual integration ping (operator may run separately) to verify `--with-llm` against a live Ollama doesn't break the no-LLM verdict path.

- [ ] **Step 6: Commit**

```bash
git commit -am "feat(bench): mem0-v3-locomo true per-QA token p50 + optional --with-llm diagnostic"
```

---

### Task 6: Flip status to ACTIVE, update README, clear `blocked_on`, regenerate coverage/metrics docs

**Files:**
- Modify: `bench/isolation/memory/mem0-v3-locomo/expected.json` (status: INACTIVE → ACTIVE, blocked_on: [] )
- Modify: `bench/isolation/memory/mem0-v3-locomo/README.md` (remove INACTIVE line, add LoCoMo attribution + license notice, replace "Qwen3 8B" with "llama3 8B Q4 via Ollama", add run instructions)
- Modify: `docs/coverage.md` (regenerated)
- Modify: `docs/metrics.md` (regenerated)

- [ ] **Step 1: Flip the status field + clear blocked_on**

```bash
# Edit expected.json directly
```

- [ ] **Step 2: Update README.md** — license notice + run section:

```markdown
## Dataset

LoCoMo (Maharana et al., ACL 2024), licensed CC BY-NC 4.0. We download
`locomo10.json` from the [official snap-research/locomo repo](https://github.com/snap-research/locomo)
on each run and do not redistribute it. Use is non-commercial benchmarking of
OCM's library-driven retrieval pattern (spec row 9).

## Run

The bench framework runs this sandbox via `docker compose up` per the standard contract.
Manual one-off:

    cd bench/isolation/memory/mem0-v3-locomo
    docker compose run --rm bench

With the optional LLM-in-the-loop diagnostic (requires Ollama with `llama3` pulled
on the host):

    OLLAMA_URL=http://host.docker.internal:11434 docker compose run --rm bench python bench.py --with-llm
```

- [ ] **Step 3: Regenerate coverage + metrics docs (CI rejects stale)**

```bash
python -m bench.cli coverage --root bench --write docs/coverage.md
python -m bench.cli dashboard --history bench/history.jsonl --write docs/metrics.md
```

- [ ] **Step 4: Commit**

```bash
git add bench/ docs/
git commit -m "feat(bench): activate mem0-v3-locomo sandbox; regen coverage + metrics"
```

---

### Task 7: Run the verdict

**Files:** none modified — measurement only.

- [ ] **Step 1: Operator runs**

```bash
python -m bench.cli run --root bench --sandbox memory/mem0-v3-locomo --repeats 3 --hardware-class operator-dev-box
```

- [ ] **Step 2: Inspect the `summary.json` verdict + `history.jsonl` row.**

- [ ] **Step 3: Append the verdict + run-ID to the sandbox README.** (Pattern from amnesia-ab.)

- [ ] **Step 4: Commit history row + README verdict line.**

```bash
git commit -am "data(bench): mem0-v3-locomo verdict <CONFIRMED|REFUTED|INCONCLUSIVE>"
```

---

## Self-review against the directive

- [x] **§1 LoCoMo acquisition:** source (snap-research/locomo), exact filename (`data/locomo10.json`), exact size (2.81 MB / 2,805,274 bytes), exact license (CC BY-NC 4.0), no accounts/payments, NEEDS_APPROVAL flagged with 4-option multi-choice.
- [x] **§2 Harness design:** files mapped (compose + bench.py + README delta), explicit reuse of #56's hermetic Mem0 config (huggingface MiniLM + faiss-cpu + stub LLM, `infer=False`) and amnesia-ab's Ollama-via-`host.docker.internal` pattern. Conversation→memory mapping decision explained.
- [x] **§3 Hardware:** Windows + Ollama 11434 + llama3 8B Q4 (not Qwen3 8B — README correction flagged in Task 6) + mxbai-embed-large (only for the optional `--with-llm` path; the verdict path uses Mem0's internal embedder).
- [x] **§4 expected.json contract:** no changes; field-by-field mapping shows where each comes from (`primary_value` ← `mean per-conv recall × 100`, etc.).
- [x] **§5 wall-time + blockers:** ~2.5-4 min per repeat (retrieval-only), ~10-15 min for the 3-repeat verdict run; blockers list reconciled (the OpenMemory MCP `blocked_on` item is a daemon-side packaging concern, not a verdict blocker — README clarifies).
- [x] **SMALL deliverable:** one plan document, no execution.
- [x] **PR-GATED:** branch + PR.
- [x] **NEEDS_APPROVAL is multi-choice.**
