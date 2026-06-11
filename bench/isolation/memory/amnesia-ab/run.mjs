/**
 * amnesia-ab — the cheapest discriminating test of OCM's central loop.
 *
 * ARM A (memory ON):  task -> embed (mxbai-embed-large) -> cosine top-5 memories -> inject -> llama3 8B Q4
 * ARM B (memory OFF): identical prompt, no memories.
 *
 * Metrics (see expected.json hypothesis contract):
 *   memory_on_fact_recall_pct   primary   confirm >=70, refute <50
 *   retrieval_hit_rate_pct      secondary confirm >=80, refute <60
 *   memory_off_fact_recall_pct  sanity    must be <=25 or the corpus is guessable (run INVALID)
 *
 * Run: node run.mjs   (Ollama on 127.0.0.1:11434 with llama3 + mxbai-embed-large)
 */
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const OLLAMA = process.env.OLLAMA_URL || 'http://127.0.0.1:11434';
const CHAT_MODEL = 'llama3';
const EMBED_MODEL = 'mxbai-embed-large';
const TOP_K = 5;

const { memories, tasks } = JSON.parse(readFileSync(join(HERE, 'corpus.json'), 'utf8'));

async function embed(text, isQuery = false) {
  const prompt = isQuery ? `Represent this sentence for searching relevant passages: ${text}` : text;
  const r = await fetch(`${OLLAMA}/api/embeddings`, {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ model: EMBED_MODEL, prompt }),
  });
  if (!r.ok) throw new Error(`embed ${r.status}`);
  return (await r.json()).embedding;
}

function cosine(a, b) {
  let dot = 0, na = 0, nb = 0;
  for (let i = 0; i < a.length; i++) { dot += a[i] * b[i]; na += a[i] * a[i]; nb += b[i] * b[i]; }
  return dot / (Math.sqrt(na) * Math.sqrt(nb));
}

async function generate(system, user) {
  const t0 = Date.now();
  const r = await fetch(`${OLLAMA}/api/chat`, {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      model: CHAT_MODEL, stream: false,
      messages: [{ role: 'system', content: system }, { role: 'user', content: user }],
      options: { temperature: 0.2, num_predict: 300 },
    }),
  });
  if (!r.ok) throw new Error(`chat ${r.status}`);
  const j = await r.json();
  return { text: j.message?.content || '', ms: Date.now() - t0 };
}

// fact matching: lowercase, strip spaces/commas/periods so "$1,400"≈"1400", "Sunday 2am"≈"sunday, 2 AM"
const norm = (s) => s.toLowerCase().replace(/[ ,.]/g, '');
const containsFact = (output, fact) => norm(output).includes(norm(fact));

const SYS_ON = (mems) =>
  `You are a personal assistant with persistent memory of past working sessions.\n` +
  `RELEVANT MEMORIES retrieved for this request:\n${mems.map((m) => `- ${m.text}`).join('\n')}\n` +
  `Answer using these memories — be specific with names and numbers. Be concise.`;
const SYS_OFF = `You are a personal assistant. Answer the request. Be concise.`;

console.log(`[1/3] embedding ${memories.length} memories…`);
const memVecs = [];
for (const m of memories) memVecs.push({ ...m, vec: await embed(m.text) });

console.log(`[2/3] running ${tasks.length} tasks × 2 arms…`);
const results = [];
for (const task of tasks) {
  const qVec = await embed(task.prompt, true);
  const top = memVecs
    .map((m) => ({ m, score: cosine(qVec, m.vec) }))
    .sort((a, b) => b.score - a.score)
    .slice(0, TOP_K);
  const topIds = top.map((t) => t.m.id);
  const sourceHits = task.source_ids.filter((id) => topIds.includes(id)).length;
  const retrievalHit = sourceHits >= Math.min(2, task.source_ids.length);

  const on = await generate(SYS_ON(top.map((t) => t.m)), task.prompt);
  const off = await generate(SYS_OFF, task.prompt);

  const onFacts = task.key_facts.filter((f) => containsFact(on.text, f));
  const offFacts = task.key_facts.filter((f) => containsFact(off.text, f));

  const row = {
    task: task.id, project: task.project,
    retrieval: { topIds, sourceHits, of: task.source_ids.length, hit: retrievalHit },
    on: { factsFound: onFacts, recall: onFacts.length / task.key_facts.length, ms: on.ms, text: on.text },
    off: { factsFound: offFacts, recall: offFacts.length / task.key_facts.length, ms: off.ms, text: off.text },
  };
  results.push(row);
  console.log(
    `  ${task.id}: retrieval ${sourceHits}/${task.source_ids.length}${retrievalHit ? ' HIT' : ' MISS'}` +
    ` | ON ${onFacts.length}/${task.key_facts.length} (${(on.ms / 1000).toFixed(1)}s)` +
    ` | OFF ${offFacts.length}/${task.key_facts.length} (${(off.ms / 1000).toFixed(1)}s)`
  );
}

console.log('[3/3] scoring…');
const pct = (xs) => (100 * xs.reduce((a, b) => a + b, 0)) / xs.length;
const onRecall = pct(results.map((r) => r.on.recall));
const offRecall = pct(results.map((r) => r.off.recall));
const hitRate = pct(results.map((r) => (r.retrieval.hit ? 1 : 0)));
const onMs = results.map((r) => r.on.ms).sort((a, b) => a - b)[Math.floor(results.length / 2)];
const offMs = results.map((r) => r.off.ms).sort((a, b) => a - b)[Math.floor(results.length / 2)];

const sane = offRecall <= 25;
let verdict;
if (!sane) verdict = 'INVALID (corpus guessable — OFF arm exceeded 25% recall)';
else if (onRecall >= 70 && hitRate >= 80) verdict = 'CONFIRMED';
else if (onRecall < 50) verdict = 'REFUTED (fact-usage: 8B cannot use injected memories)';
else if (hitRate < 60) verdict = 'REFUTED (retrieval failed at toy scale)';
else verdict = 'MIXED (between thresholds — investigate failure rows)';

const summary = {
  sandbox: 'amnesia-ab', ranAt: new Date().toISOString(),
  hardware: 'operator dev box (Windows, Ollama CPU/GPU local)', chatModel: 'llama3 8B Q4_0', embedModel: EMBED_MODEL,
  memory_on_fact_recall_pct: +onRecall.toFixed(1),
  memory_off_fact_recall_pct: +offRecall.toFixed(1),
  retrieval_hit_rate_pct: +hitRate.toFixed(1),
  latency_ms_p50: { on: onMs, off: offMs },
  verdict,
};

mkdirSync(join(HERE, 'results'), { recursive: true });
const stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
writeFileSync(join(HERE, 'results', `run-${stamp}.json`), JSON.stringify({ summary, results }, null, 2));

console.log('\n========== AMNESIA A/B SUMMARY ==========');
console.log(JSON.stringify(summary, null, 2));
console.log(`details: results/run-${stamp}.json`);
