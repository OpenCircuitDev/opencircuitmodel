# OCM Website Plan — `ocm.shortcircuit.bot`

> **Goal:** Public face of OCM. Lives at `ocm.shortcircuit.bot` as a sibling subdomain in the Short Circuit ecosystem. Astro + Tailwind + SQLite (matches existing siblings: ColexForge, Toolbox, Materials, Command Center, Accounting). Port 4308.
> **Code lives at:** `OCR-Forge/workspaces/OCM/` (sibling to `ShortCircuit/`)
> **Deployment:** Railway (auto-deploy on `main` push) — same as siblings

The website is **not** an MVP-blocker for v1 daemon work. It can ship before, alongside, or after v1. Its purpose is to set expectations, recruit beta contributors, document the project transparently, and publish benchmarks.

---

## Site map

| Path | Purpose | Priority | Data source |
|---|---|---|---|
| `/` | Landing — hero pitch, status badge, 3-line "how it works", call-to-action | P0 | Static |
| `/docs` | Quickstart, API ref, MCP setup, client integrations | P0 | Markdown files in repo |
| `/roadmap` | v1 → v6 timeline with status badges per phase | P0 | SQLite (admin-editable) |
| `/research` | Links + summaries of the 4 research streams + tool-landscape synthesis | P0 | Static (rendered from research/ markdown in opencircuitmodel repo) |
| `/benchmarks` | Live benchmark results from the bench framework | P1 | DuckDB-imported Parquet from opencircuitmodel/bench/results |
| `/models` | Curated model registry (Qwen3-30B-A3B, Llama 8B, etc.) with hardware reqs | P1 | JSON manifest synced from opencircuitmodel repo |
| `/contribute` | "Run a contributor node" pitch + hardware calculator + Discord/GitHub links | P1 | Static + small client-side calculator |
| `/contribute/calculator` | Interactive: "I have an [M4 Mac Mini base / RTX 4090 / etc.] — what tier am I?" | P1 | Client-side JS |
| `/download` | Cross-platform installer links (after v1 release) | P2 | Latest GitHub release artifacts |
| `/blog` | Build-in-public posts | P2 | Markdown |
| `/admin` | Internal dashboard — manage roadmap status, blog posts, contributor list | P3 | SQLite + auth |
| `/api/*` | Same admin/API endpoints as Short Circuit siblings (auth, content management) | P3 | Astro endpoints |

P0 = launch-day must. P1 = nice-to-have for launch. P2 = post-launch. P3 = internal only.

---

## Stack — exactly matches Short Circuit siblings

| Layer | Choice | Reason |
|---|---|---|
| Framework | Astro 5.x | Matches siblings; SSR via @astrojs/node; static-island UX is fast |
| Styling | Tailwind 3.x + @tailwindcss/typography | Matches siblings |
| DB | SQLite via better-sqlite3 + Drizzle ORM | Matches siblings; no separate DB server |
| Auth | bcryptjs + sc_session cookie | **Cross-subdomain SSO** — sign in to Short Circuit = signed in to OCM admin |
| Deploy | Railway, auto-deploy on `main` push to `OpenCircuitDev/OCM-Website` | Matches siblings |
| Port | **4308** (next free; 4307 is Accounting) | Per Short Circuit ecosystem port plan |
| Cross-nav | `PlatformNav.astro` shared component (added to all siblings) | Existing pattern |

**No deviation from sibling pattern.** This minimizes maintenance cost — Brand can apply patches across all subdomain projects without per-project context switching.

---

## Phase 0 deliverables (Weeks 1-2)

### Task W0.1: Scaffold Astro project from sibling template

- [ ] **Step 1: Copy ShortCircuit's structure**

```bash
cp -r "C:/Users/brand/Dropbox/OCR/Open_Circuit/OCR-Forge/workspaces/ShortCircuit/" \
      "C:/Users/brand/Dropbox/OCR/Open_Circuit/OCR-Forge/workspaces/OCM/"
cd "C:/Users/brand/Dropbox/OCR/Open_Circuit/OCR-Forge/workspaces/OCM/"
rm -rf node_modules dist .git data/*.db
```

- [ ] **Step 2: Initialize as new repo + change package metadata**

```bash
git init -b main
# Edit package.json: name: "ocm-website", port: 4308 in dev script
# Edit astro.config.mjs: change site URL to https://ocm.shortcircuit.bot
# Edit tailwind.config.mjs: keep theme but rename color palette to OCM brand
# Edit src/lib/db/schema.ts: keep core tables (users, sessions, projects, project_tasks, project_notes), drop J-4.2-specific tables (j5_phases, j5_media, j5_build_log)
```

- [ ] **Step 3: Replace homepage content (`src/pages/index.astro`)**

The new homepage should pull hero copy from the OCM repo's README (cross-link, not duplicate).

- [ ] **Step 4: Local dev**

```bash
npm install
npm run dev  # → http://localhost:4308
```

- [ ] **Step 5: Initial commit**

```bash
git add .
git commit -m "chore: scaffold OCM website from Short Circuit sibling template"
```

### Task W0.2: Branding + theme

**Files:**
- Modify: `src/components/Layout.astro`, `tailwind.config.mjs`, `src/styles/global.css`

OCM visual identity:
- Wordmark: "OpenCircuitModel" (uppercase letters O-C-M can be highlighted)
- Color palette: pull from Short Circuit's circuit-board metaphor (greens / blacks / accents) but distinct enough that OCM and Short Circuit don't visually blur
- Typography: same family as Short Circuit siblings for ecosystem coherence

(Concrete color choices: leave to a separate visual-design pass; don't block engineering.)

### Task W0.3: PlatformNav cross-subdomain integration

- [ ] **Step 1: Add OCM to ShortCircuit's `src/components/PlatformNav.astro`**

In `OCR-Forge/workspaces/ShortCircuit/src/components/PlatformNav.astro`, add an OCM entry to the subdomains list with the URL `https://ocm.shortcircuit.bot`.

- [ ] **Step 2: Mirror PlatformNav into OCM's `src/components/PlatformNav.astro`**

Same component, same content. When users sign in to ShortCircuit, the `sc_session` cookie covers `.shortcircuit.bot` so they're signed into OCM admin too.

- [ ] **Step 3: Test SSO**

Sign in at shortcircuit.bot/login → visit ocm.shortcircuit.bot/admin → should be authenticated.

### Task W0.4: P0 pages — landing, docs, roadmap, research

- [ ] **W0.4a: `/` landing**

Hero (extracted from README): "A free, open-source personal AI agent that lives on your machine, remembers everything, and grows in capability as the mesh grows."

Status badge: "Pre-v1 — design + research phase. v1 alpha targeted Q3 2026."

3-card "how it works" row.

CTA: "Read the design spec" → links to GitHub spec; "Join the contributor list" → links to Discord.

- [ ] **W0.4b: `/docs`**

Initially: minimal. Just the README rendered + links to the spec, plan, and research files in the GitHub repo. Once v1 ships, this expands to a real quickstart.

- [ ] **W0.4c: `/roadmap`**

Phase grid (v1 / v2 / v3 / v4 / v5 / v6) with status badges (planned / in-progress / shipped). Status is editable via `/admin` UI (SQLite-backed, like Short Circuit's `j5_phases`).

- [ ] **W0.4d: `/research`**

Cards for each of the 4 research streams + the synthesis. Each card: title, ~150-word summary, "Read full report" link to GitHub. **The full reports live in the opencircuitmodel repo, not the website repo.** The website is a viewer.

### Task W0.5: Deploy to Railway

- [ ] **Step 1: Create new GitHub repo `OpenCircuitDev/OCM-Website`** (private, matches Short Circuit pattern)

```bash
gh repo create OpenCircuitDev/OCM-Website --private --description "ocm.shortcircuit.bot website" --source=. --remote=origin --push
```

- [ ] **Step 2: Connect to Railway** (manual step in Railway dashboard) — auto-deploy on push to main

- [ ] **Step 3: DNS — add ocm.shortcircuit.bot CNAME** (manual step in DNS provider)

- [ ] **Step 4: Verify** `https://ocm.shortcircuit.bot` resolves to the deployed Astro app

---

## Phase 1 deliverables (Weeks 3-6)

### Task W1.1: `/benchmarks` page wired to bench framework

The bench framework writes results as Parquet to `opencircuitmodel/bench/results/`. The website ingests these on build:

- A nightly GitHub Action in OCM-Website pulls latest results from opencircuitmodel via git-submodule or HTTP
- An Astro build step uses DuckDB-WASM (or DuckDB CLI in the build) to query Parquet and emit JSON
- The page renders the JSON as charts (Chart.js or similar — matches sibling tooling)

What's shown:
- Per-hypothesis verdict table (CONFIRMED / REFUTED / INCONCLUSIVE)
- Per-hardware-class throughput ladder
- Stack-up math validation (does the claimed multiplier reproduce?)
- Time-series for any regression detection

### Task W1.2: `/models` page wired to model registry

The OCM repo has `crates/ocm-models/registry.json`. The website renders it:
- Table of curated models (Qwen3-30B-A3B, Llama 3.1 8B, Qwen3 8B, BitNet 2B, etc.)
- Per-model: file size, min RAM, recommended hardware, source URL, SHA256
- Filter: "what runs on my hardware?"

### Task W1.3: `/contribute/calculator` interactive tool

Client-side JS calculator:
- Input: hardware (preset list — M4 base/Pro, RTX 4060/4090/5090, Linux+CUDA, etc.) + RAM + always-on (Y/N)
- Output: Tier this contributor falls into (high-spec / mid-spec / mostly-receiver), expected concurrent users supported, recommended models to host

This converts the "minimum-contributor math" from the master plan into a self-service experience for prospective contributors.

---

## Phase 2 deliverables (Weeks 7-10)

### Task W2.1: Blog scaffolding + first build-in-public posts

Markdown-based blog (matches Short Circuit pattern). First posts:
1. "Why OpenCircuitModel exists" — the manifesto
2. "The math: 5 contributors, 150-300 testers, top-tier outcomes" — the contributor sizing analysis
3. "How we benchmark every tool we adopt" — the bench framework methodology
4. "Letta vs Mem0: why we changed our minds in 24 hours" — the research-driven spec revision case study

### Task W2.2: `/download` page (post-v1-release)

Pulls latest GitHub release from `OpenCircuitDev/opencircuitmodel`. Displays per-OS installer with checksums + GPG signature (when v4 codesigning lands).

---

## Phase 3 deliverables (Weeks 11-12, launch prep)

### Task W3.1: Launch-day polish + Show HN draft

- Hero refined for launch
- Press kit (logo, screenshots, 1-line / 50-word / 200-word descriptions)
- Show HN post draft in `OCM-Website/launch/show-hn-draft.md`
- r/LocalLLaMA post draft
- r/selfhosted post draft

### Task W3.2: Analytics + privacy

- Plausible or self-hosted Umami analytics (no Google Analytics — privacy thesis)
- Privacy policy explicitly stating: no tracking cookies, no third-party JS, all data ingestion is anonymized

---

## Cross-repo coordination

The website lives in **a separate repo** (`OCM-Website`, private, Astro/Tailwind/SQLite) from OCM core (`opencircuitmodel`, public, Rust/Python/Svelte). They coordinate via:

- **Git submodule** of opencircuitmodel inside OCM-Website (pinned to a known-good SHA, bumped manually)
  - Used to read research markdown for /research page
  - Used to read bench results for /benchmarks page
  - Used to read model registry for /models page
- **GitHub Actions** in OCM-Website nightly bumps the submodule pin to opencircuitmodel main HEAD
- **No code dependency** the other direction — opencircuitmodel doesn't know the website exists

This separation keeps the OCM core repo lean (no website noise in the core repo's PRs) while allowing the website to surface OCM's content automatically.

---

## Success criteria

| Phase | Pass criteria |
|---|---|
| Phase 0 | Site live at `ocm.shortcircuit.bot`. /, /docs, /roadmap, /research all render. SSO with Short Circuit works. |
| Phase 1 | /benchmarks shows real bench data. /models reflects current registry. /contribute/calculator gives accurate tier recommendations. |
| Phase 2 | First 4 build-in-public blog posts live. /download wired to release artifacts. |
| Phase 3 | Show HN post drafted. Press kit complete. Analytics active. |

---

## Risk callouts

| Risk | Likelihood | Mitigation |
|---|---|---|
| Bench framework data structure changes after we wire /benchmarks | High | Stable contract (`summary.json` schema) declared in the bench framework plan; website queries that contract |
| Railway deployment hiccups | Low | Same pattern as 6 sibling projects already deployed; Brand has experience |
| DNS for `ocm.shortcircuit.bot` | Low | Same DNS provider as siblings; CNAME pattern proven |
| Cross-subdomain SSO breaks | Low-Medium | Test it explicitly in Phase 0 gate; share-cookie config matches Short Circuit's |
| Website content drifts from spec/research | Medium | Submodule + auto-pull pattern keeps content in sync; manual review at each phase gate |

---

## Tasks ready to start in Phase 0

- W0.1: Scaffold from ShortCircuit template
- W0.2: Branding + theme
- W0.3: PlatformNav SSO
- W0.4: P0 pages (landing / docs / roadmap / research)
- W0.5: Deploy to Railway

Estimated effort: **20-30 hours** of focused work. Doable in 1-2 weeks parallel to v1 daemon work.
