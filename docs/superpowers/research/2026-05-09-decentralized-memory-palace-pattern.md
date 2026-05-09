# Decentralized Memory Palace — Pattern Analysis + OCM Architecture

**Date:** 2026-05-09
**Trigger:** User observation that the existing OCR Memory Palace pattern (git-backed structured knowledge store) is essentially "external memory storage as a service for AI agents," and asking whether OCM's mesh could generalize this to a decentralized variant.
**Strategic significance:** This is a candidate **third network-effect lever** for OCM, alongside the two already locked in spec v0.3 (skill federation via DSPy GEPA artifacts; inference compute sharing via mesh peers). Memory Palace federation operates on a different axis — *human-readable structured knowledge artifacts* rather than compiled programs or raw compute.

---

## 1. The pattern, observed in the wild

Brand's existing setup at `~/Dropbox/OCR/Open_Circuit/ocr-memory-palace/` (synced to `github.com/OpenCircuitDev/ocr-memory-palace`, private) is a working production example of the pattern. It demonstrates:

| Property | How OCR Memory Palace expresses it |
|---|---|
| **Versioned** | Git history; every change is a commit with timestamp + author |
| **Distributed** | Every clone has the full history; Dropbox + GitHub are mirrors, not single-points-of-failure |
| **Queryable** | Standard tools work: `grep`, `find`, file-tree navigation, GitHub search |
| **Structured taxonomy** | `protocols/`, `feedback/`, `knowledge/`, `planning/{designs,taps,research}/`, `sessions/`, `handoff/` — each directory has a defined purpose |
| **Cross-session persistent** | Survives agent restarts, conversation resets, local disk wipes |
| **Cross-agent shareable** | Multiple Claude Code sessions, different agents, different machines all read/write the same palace |
| **Index + content** | `MEMORY.md` is the canonical index (~150 char one-liners); detail lives in topic files |
| **Cited references** | Cross-references between palace nodes via relative paths; agents cite palace nodes rather than hallucinating |
| **Issue tracking integrated** | GitHub Issues with labels (`gap:open`, `priority:high`, `phase:0.5`, `comp:animation`) for ongoing work tracking |
| **Authenticated edits** | Push requires GitHub credentials; commits attribute authorship |
| **Time-travel** | `git log` + `git show <SHA>:<path>` lets agents see what was known on a specific date |

**The non-obvious thing this does for AI agents:** it *externalizes the entire problem of long-term coherent memory* into a substrate that agents can manipulate with the same tools they use for code. The agent doesn't need to "remember" — it queries the palace. The agent doesn't need to "decide what to write down" — there are protocols for that. The agent's working context stays small; the palace stays consistent.

This is **exactly what OCM's spec v0.3 calls for at the agent layer** (Mem0 v3 + library-driven retrieval + sub-context lookup). Brand's Memory Palace is a *concrete instance* of this pattern, scaled up from "single-conversation memory" to "all-of-Brand's-projects-and-history memory."

## 2. Prior art in the OSS / commercial landscape

Existing tools that occupy adjacent slots:

| Project | What it does | License | Mesh-ready? |
|---|---|---|---|
| **GitHub** (substrate, not project) | Git hosting + Issues + search + auth | proprietary backend, git is open | Centralized hosting; git itself is decentralized |
| **Obsidian** | Local-first markdown notes with `[[wikilinks]]`, plugins | proprietary core, OSS plugin ecosystem | Sync is paid + closed-source; vault is local |
| **Logseq** | Local-first knowledge graph, markdown + outliner | AGPLv3 | Local-first; sync via git or Logseq Sync (paid) |
| **Foam** | VS Code-based PKM with wikilinks | MIT | Local-first; users sync via git themselves |
| **Anytype** | Local-first p2p notes with object graph | "Any Source Available" (not OSI-approved) | Native p2p sync (closest to "decentralized memory palace") |
| **Earthstar** | P2P data store for personal projects | LGPL | P2P, encrypted, replicated |
| **OrbitDB** | Distributed peer-to-peer database (CRDT, IPFS) | MIT | True p2p, IPFS-backed |
| **Iroh-blobs** | Content-addressed blob store on iroh transport | Apache 2.0 + MIT | OCM's mesh transport already plans iroh |
| **Cline "Memory Bank"** | Markdown files agent reads at session start | Apache 2.0 | Local-only; pattern proposal is interesting |
| **Aider repo map** | Compressed codebase view (PageRank + tree-sitter) | Apache 2.0 | Local-only; locked in OCM v0.3 spec for code context |
| **MCP `memory` servers** | Various reference implementations of MCP servers exposing notes/memory | Apache 2.0 (mostly) | Single-user; pattern-instructive |
| **Letta archival memory** | Tool-driven memory the agent calls into | Apache 2.0 | Single-user; already de-prioritized for OCM v1 (small-model reliability issue) |
| **Mem0 + OpenMemory MCP** | Library-driven retrieval, MCP server | Apache 2.0 | Single-user; locked in OCM v0.3 spec for v1 |
| **Notion** | Hosted hierarchical notes | proprietary | Centralized; not mesh-compatible |
| **Roam Research** | Hosted block-graph knowledge base | proprietary | Centralized |

**Verdict on prior art:** No existing OSS project occupies the slot OCM would create — *agent-driven, mesh-distributed, content-addressed, structured knowledge palace with privacy controls*. The closest neighbors are Anytype (proprietary-license, not mesh-OCM-aligned) and OrbitDB (mesh-compatible but not agent-aware). **OCM has whitespace here.**

## 3. Why GitHub-style (git + structured markdown) is the right substrate

Three properties git brings that no other substrate does cleanly:

1. **Content-addressable + signable.** Every commit has a SHA; commits can be GPG-signed. Translates to "every palace node has a verifiable provenance — you can prove who said what, when."
2. **Three-way merge under divergence.** When two contributors edit the same palace node simultaneously, git's merge algorithm + manual conflict resolution gives a deterministic resolution path. CRDTs (Automerge, Yjs) auto-merge but can produce surprising results; git is more conservative and auditable.
3. **The `.gitignore` model for privacy.** Trivially split "what's in my palace" into "private (don't publish)" and "public (mesh-replicated)" — same primitive that solves "secrets don't leak into git."

Two properties markdown adds that no other format does:

1. **Human-readable AND machine-parseable.** The agent reads it as text; the human reviews it as text; the agent edits it as text. No format-impedance.
2. **Frontmatter for metadata + body for content.** Each palace node can have machine-queryable metadata (`type:`, `tags:`, `created:`, `expires:`, `confidence:`) without sacrificing the readability of the body.

GitHub-as-hub adds:

3. **Discovery + search at scale.** GitHub's search across public repos lets agents *find* relevant palaces beyond their explicit subscriptions.
4. **Issues + PRs + discussions** as ambient social fabric for collaborative palace curation.

**Decentralization caveat:** GitHub itself is centralized. But the *substrate* (git + markdown) is fully decentralized. OCM can use GitHub as the discovery + hosting layer for v3, and migrate to peer-to-peer git replication (iroh-blobs + git CRDT, or Radicle) in v4+ if/when that becomes critical.

## 4. The user's specific architectural insight, made precise

> "The Memory Palace utilizes ... external memory storage system where in essence we have a decentralized one of that."

Translated: **OCM should expose a Memory Palace primitive to every user, mesh-replicated, with privacy controls, integrated with the existing Mem0 layer.**

The architecture splits into three layers:

```
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 3 — Mesh Memory Palace (v3+, this design)                │
│  Per-user git-backed palace; selectively published over the      │
│  mesh; cross-user retrieval via subscription + search            │
│  Substrate: git over GitHub (v3) -> iroh-blobs + git CRDT (v4+) │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │ publishes curated knowledge
                              │
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 2 — Local Mem0 episodic memory (v1, locked)              │
│  Per-user, per-machine, library-driven retrieval                 │
│  Substrate: SQLite + sqlite-vec, OpenMemory MCP                 │
│  Privacy: 100% local; nothing leaves the machine                │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │ accumulates conversation
                              │
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 1 — Agent working context (per-turn)                     │
│  Llama 3.1 8B / Qwen3-30B-A3B 32K-128K window                  │
│  Whatever the model holds in immediate attention                │
└─────────────────────────────────────────────────────────────────┘
```

The Memory Palace is **layer 3** — the slowest-moving, most-curated, mesh-shareable layer. Mem0 stays as **layer 2** for raw episodic memory that the user might never want to publish (PII-rich, conversational, transient). The agent's working context is **layer 1** as already designed.

The interaction model: every layer-N retrieval can pull from layer-N+1 transparently (via tools or library hooks). The agent's working context can fetch from Mem0 (which can fetch from the palace), but **the palace never pulls from Mem0** — that direction would be a privacy leak. The information arrow points strictly upward (palace → Mem0 → working) for retrieval, and strictly downward (working → user-curated publish to palace; never to Mem0 from palace) for write.

## 5. What gets stored in the palace vs. Mem0

Brand's existing OCR Memory Palace is the reference. It contains:

| Type | Belongs in palace | Belongs in Mem0 only |
|---|---|---|
| **Protocols** (iron laws, pre-action gates, repeated patterns) | ✅ Yes | — |
| **Feedback** (durable corrections + confirmations) | ✅ Yes — distilled, not raw | — |
| **Project state** (decisions, deadlines, structures) | ✅ Yes (curated) | — |
| **Reference** (URLs, external system pointers, system maps) | ✅ Yes | — |
| **Session checkpoints** (what was achieved, what's next) | ✅ Yes | — |
| **Designs / TAPs / research** | ✅ Yes | — |
| **Handoff docs** | ✅ Yes | — |
| **Raw conversation transcripts** | ❌ No | ✅ Yes |
| **PII-rich episodic memory** | ❌ No | ✅ Yes (or local-only encrypted) |
| **Transient working state** | ❌ No | ✅ Yes (or just discard) |
| **Tentative / unconfirmed beliefs** | ❌ Maybe (with `confidence: low` frontmatter) | ✅ Yes |
| **Personal credentials / secrets** | ❌ Never | ❌ Never (local-only encrypted at most) |

The palace is *what you'd be willing to write down on a publicly-archived index card*. Mem0 is *the rest*.

## 6. Privacy model

Three concentric privacy zones per OCM user:

```
┌──────────────────────────────────────────────────────────┐
│  ZONE A — Local-only Mem0 (100% private)                 │
│  Episodic conversation, PII, raw history                 │
│  Never crosses the machine boundary                      │
└──────────────────────────────────────────────────────────┘

      ┌────────────────────────────────────────────┐
      │  ZONE B — Personal palace (local + git)    │
      │  Curated knowledge; published to YOUR git  │
      │  repo (private or public, your choice)     │
      │  Versioned; you control who has read access│
      └────────────────────────────────────────────┘

            ┌────────────────────────────────────┐
            │  ZONE C — Mesh-shared palace nodes │
            │  Explicitly tagged for mesh        │
            │  publication; replicated across    │
            │  subscribed peers                  │
            │  Signed; immutable once published  │
            └────────────────────────────────────┘
```

Default: everything Mem0 sees stays in Zone A. The user must *explicitly* curate something into Zone B (their personal palace) — protocols are written, references are catalogued, etc. *Zone B → Zone C is a separate publish step* (frontmatter `mesh: public` opt-in, or a manual `palace publish <node>` CLI command).

This matches the user's existing OCR Memory Palace exactly: it's a deliberate authoring step to add a feedback note or a protocol — not an automatic spillover from conversation memory.

## 7. Concrete v3+ architecture

### Substrate
- **Storage:** local git repo at `~/.ocm/palace/` per user
- **Hosting (v3):** user-owned GitHub repo (e.g., `github.com/<user>/ocm-palace`); OCM daemon syncs via standard git push/pull
- **Hosting (v4+):** iroh-blobs content-addressed replication so users without GitHub can still publish; git history streams over the mesh transport
- **Discovery:** OCM mesh maintains a *palace registry* — a small DHT mapping `user_id → palace_url`; users opt in to register
- **Subscription:** explicit; user runs `palace subscribe @alice` to add Alice's palace to their retrieval pool

### Retrieval surface (MCP tools the agent can call)

| Tool name | Behavior |
|---|---|
| `palace_search(query, scope)` | Fuzzy + semantic search across `local`, `subscribed`, or `discoverable` (DHT) scope. Returns ranked list of palace node paths + snippets. |
| `palace_read(path, scope)` | Fetch a specific palace node's full content. Local first, then subscribed peers. |
| `palace_write(path, content, metadata)` | Author a new node in user's local palace. Defaults to `mesh: private`; user must explicitly opt to publish. |
| `palace_publish(path)` | Promote a local node to Zone C (mesh-replicated). Signs the commit; pushes to the user's hosting + iroh-blobs replicas. |
| `palace_subscribe(user_or_url)` | Add another user's palace to the retrieval pool. Idempotent. |
| `palace_unsubscribe(user)` | Remove. |
| `palace_history(path)` | `git log` for a specific node. Useful for "what did this protocol say a month ago?" |

### Indexing
- Each palace has a top-level `MEMORY.md` (one-line index of all nodes) — **same convention Brand's OCR Memory Palace uses**
- Frontmatter on every node provides machine-queryable metadata
- Optional: semantic-embedding index per palace, refreshed on push (gives `palace_search` a vector backend without requiring full Mem0)

### Integration with existing OCM stack
- **Mem0 OpenMemory MCP** continues to serve Layer 2 (local episodic). Unchanged.
- **Mem0 retrieval pipeline** can be extended with a "palace fallback" — if Mem0's local store doesn't return high-confidence results, query the palace next. Configurable per-query.
- **DSPy GEPA skills** (locked v2+ feature) can be *cited from the palace* — e.g., a palace node says "for entity extraction tasks, use `dspy://alice/entity-skill@sha:abc123`", and the agent dereferences the skill artifact via the existing skill federation layer
- **Reciprocity ledger** (locked v3 feature) can grant "palace publish quota" or "palace subscribe quota" as a contribution credit

### Privacy / authentication
- Every palace commit signed with the user's OCM keypair (existing in v3 reciprocity ledger work)
- `palace publish` always rewrites commits to be signed before pushing
- Subscribed peers can verify signatures on every node they retrieve
- The `mesh: public` frontmatter is the *gate* — nodes without it never replicate, even if the local git repo gets pushed somewhere

## 8. Bench-framework hypotheses (sandboxes to add)

Following the discipline of [`2026-05-09-bench-sandbox-additions-from-research.md`](../plans/2026-05-09-bench-sandbox-additions-from-research.md), the Memory Palace feature gets validated by sandboxes that confirm or refute its core claims:

```json
{
  "hypothesis_id": "palace-vs-mem0-recall-on-shared-knowledge",
  "claim": "Llama 3.1 8B Q4 with Mem0 + Memory Palace (subscribed to a curated 100-node palace) outperforms plain Mem0 by >=15pp on a benchmark where the answer requires citing structured knowledge (e.g., an OCM-protocols-recall test set of 50 questions)",
  "metric": "protocol_recall_accuracy_pct_delta",
  "thresholds": {"confirm_at_least": 15.0, "refute_below": 5.0},
  "workload": "ocm-protocols-recall-50q.jsonl",
  "comparison_anchor": "mem0-only-no-palace",
  "timeout_seconds": 3600
}
```

```json
{
  "hypothesis_id": "palace-search-latency-vs-corpus-size",
  "claim": "Palace search across 5 subscribed peers' palaces (each 200-1000 nodes) returns top-5 results in <=2s p50 with relevance MRR >=0.7 against a hand-labeled gold set",
  "metric": "search_latency_p50_ms",
  "thresholds": {"confirm_at_most": 2000, "refute_above": 5000},
  "secondary_metric": "mrr_at_5",
  "secondary_thresholds": {"confirm_at_least": 0.7, "refute_below": 0.5},
  "workload": "palace-search-gold-200q.jsonl",
  "timeout_seconds": 1800
}
```

```json
{
  "hypothesis_id": "palace-publish-signature-verification",
  "claim": "100% of palace nodes published with the OCM keypair pass signature verification on retrieval; 100% of nodes with tampered content fail; 0 false positives or false negatives across 1000 randomized publish/retrieve pairs",
  "metric": "signature_verification_correctness_pct",
  "thresholds": {"confirm_at_least": 100.0, "refute_below": 99.5},
  "workload": "palace-tamper-test-1000pairs.jsonl",
  "timeout_seconds": 1200
}
```

```json
{
  "hypothesis_id": "palace-subscription-knowledge-compounding",
  "claim": "An OCM user with their own 50-node palace, subscribed to 4 other users' palaces (total ~250 nodes), shows >=+25pp accuracy on a multi-domain agent task benchmark vs. solo-user baseline (just their own 50 nodes)",
  "metric": "multi_domain_agent_task_accuracy_pp_delta",
  "thresholds": {"confirm_at_least": 25.0, "refute_below": 10.0},
  "workload": "multi-domain-agent-tasks-100q.jsonl",
  "comparison_anchor": "solo-palace-baseline",
  "decision_rule": "If the multi-subscription delta is >=25pp, palace federation is the third confirmed network-effect lever. If <10pp, the lever exists but is weak; revisit the curation incentives."
}
```

These four sandboxes together test: (a) palace > no-palace on knowledge-recall tasks, (b) cross-mesh search latency is acceptable, (c) the cryptographic privacy layer actually holds, and (d) federation produces measurable knowledge-compounding effects.

## 9. v3+ implementation sketch

**Phase v3.5 (after v3 reciprocity ledger lands):**

1. **Local palace** — `~/.ocm/palace/` git repo initialized at first run; `MEMORY.md` template seeded
2. **Local-only retrieval** — `palace_search` and `palace_read` MCP tools available to agent
3. **CLI** — `ocm palace {init,write,publish,subscribe,unsubscribe,search,history}` mirrors the MCP surface for power users
4. **Frontmatter convention** — published as a spec doc; tooling validates frontmatter on `palace_write`

**Phase v4 (federated phase):**

5. **GitHub auto-sync** — daemon pushes user palace to a chosen GitHub repo on `palace_publish`; pulls subscribed palaces nightly
6. **Subscription registry** — small DHT on iroh transport mapping `user_id → {github_url, iroh_blob_root, public_key}`
7. **Cryptographic signature verification** — every retrieved node validates against the publishing user's known key; tamper detection
8. **`mesh: public` frontmatter enforcement** — daemon refuses to publish a node missing or denying the flag

**Phase v5 (peer-to-peer phase):**

9. **iroh-blobs replication** — for users without GitHub, content-addressed blob storage on the OCM mesh; git history streams as a sequence of blobs
10. **Privacy-preserving discovery** — encrypted indices so users can search across palaces without revealing what they searched for (this is research-grade; flagged as v5+ stretch)

## 10. Open research questions

- **Sybil resistance for palace publishing.** A malicious user could publish 1000 fake palaces to pollute search results. The reciprocity ledger's stake/trust signals (locked for v3) partially address this. Need to specifically design "palace reputation" signals.
- **Granular per-node access control.** Currently the model is binary (`mesh: public` or not). Real users may want palaces shared with *specific* other users (private mesh group). Worth designing in v4+ but not gating on it.
- **Conflict resolution at scale.** Two users edit the same protocol node simultaneously — git's three-way merge works for code, but markdown semantic merges sometimes need human review. CRDT-based merge (Automerge / Yjs) is an alternative but adds complexity.
- **Index freshness.** When a subscribed palace updates, when does the local search index refresh? Push notification? Polling? On-query lazy refresh?
- **Discovery beyond explicit subscription.** Should there be a "discoverable" pool of palaces for serendipitous knowledge finding? If so, how to spam-protect it?
- **Memory poisoning defense.** A subscribed palace could be a "honey pot" of subtly wrong knowledge designed to mislead the consuming agent. Cryptographic signatures prevent forgery but not authentic-but-wrong content. Need *trust signals* for content quality (votes, age, citation count, reciprocity-stake-weighted).
- **Storage costs at scale.** A palace with 10K nodes × ~10KB average node = ~100MB per user. Replicated across 10 subscribers = ~1GB peer storage. Bandwidth and disk are non-trivial; needs garbage collection / archival policy.

## 11. Bottom line for OCM

**Recommendation: lock the Memory Palace as OCM's third network-effect lever, scheduled for v3.5+.**

This adds a third structural advantage to OCM that no closed-cloud system can match:

| Lever | Layer | Status |
|---|---|---|
| Inference compute sharing | Hardware | Locked, v2+ |
| Skill federation (DSPy GEPA artifacts) | Programs | Locked, v2+ |
| **Memory Palace federation** | **Knowledge** | **Proposed, v3.5+** |

Each operates on a different axis of agent capability. Stacked, they compound: a contributor running OCM today gets faster inference (v2 mesh), better skills (v3 skill federation), AND access to the curated knowledge of every other contributor (v3.5+ palace federation). Frontier closed AI matches none of these structurally — closed models share weights but not user-curated knowledge.

The closest existing prior art is Brand's own OCR Memory Palace pattern. Generalizing that working pattern to the OCM mesh is **the directly architecturally-correct move** — we already know it works at single-user scale; we're just removing the "single-user" constraint while adding privacy + cryptographic provenance.

The single most important thing to do *now*, while v1/v2/v3 are still being built, is **maintain the discipline of OCM's own dev memory palace** (`docs/superpowers/{specs,plans,research,protocols}/`) as a *reference implementation*. Every research note, every spec revision, every plan file we commit is OCM dogfooding the pattern at the project level. By the time v3.5 ships, we'll have ~500+ palace nodes worth of working examples in the public OCM repo, demonstrating the pattern lives.

## Sources

- Brand's OCR Memory Palace: `~/Dropbox/OCR/Open_Circuit/ocr-memory-palace/` (synced to `github.com/OpenCircuitDev/ocr-memory-palace`, private)
- Brand's `BF_Workspace/CLAUDE.md` documenting the Memory Palace conventions
- [Iroh-blobs (content-addressed blob store on iroh transport)](https://github.com/n0-computer/iroh-blobs)
- [Automerge (CRDT-based merge for collaborative editing)](https://automerge.org/)
- [Anytype (closest commercial prior art for p2p notes)](https://anytype.io/)
- [OrbitDB (IPFS-backed distributed database)](https://github.com/orbitdb/orbitdb)
- [Earthstar (p2p data store for personal projects)](https://earthstar-project.org/)
- [Cline Memory Bank pattern](https://docs.cline.bot/improving-your-prompting-skills/cline-memory-bank)
- [GitHub Memory MCP servers](https://github.com/modelcontextprotocol/servers)
- Reference: spec v0.3 locked decisions 9 (Mem0), 23 (DSPy GEPA skill federation)
