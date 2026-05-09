# OCM Frontend

SvelteKit + adapter-static UI served by the OCM Tauri daemon. Talks to the
daemon's OpenAI-compat HTTP API at `http://127.0.0.1:7300/v1/*`.

## Dev

```bash
npm install
npm run dev   # http://localhost:5173
```

The dev server proxies `/v1/*` to `127.0.0.1:7300`, so you need the OCM
daemon running. Without it, the UI loads but the model picker reports
"daemon unreachable" and chat requests fail.

## Build

```bash
npm run build  # writes static bundle to ./build/
npm run check  # svelte-check + tsc
```

Tauri picks the `build/` output up automatically via `tauri.conf.json`'s
`frontendDist` field; you don't need to copy files manually.

## Stack

- **SvelteKit 2** + **Svelte 5** with runes
- **adapter-static** (no Node runtime in production)
- **Tailwind CSS v4** (Vite plugin)
- **TypeScript 5**

## Layout

```
src/
  app.html         HTML shell
  app.css          Tailwind v4 entry + theme tokens
  routes/
    +layout.ts     SSR off, prerender on, trailingSlash always
    +layout.svelte App chrome (header)
    +page.svelte   Chat panel + model picker
  lib/
    api.ts         /v1/models, /v1/chat/completions (incl. SSE stream)
    types.ts       Wire types mirrored from crates/ocm-api
static/
  favicon.svg
```

## Connecting to the daemon

The daemon ships with `retrieval_top_k=5` and Mem0-backed retrieval enabled,
so chat messages get library-driven memory context injected before the model
runs. The frontend is unaware of memory — it just sends messages and renders
streaming tokens.
