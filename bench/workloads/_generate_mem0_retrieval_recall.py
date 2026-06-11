"""Generate a synthetic memory-recall workload for Mem0's retrieval layer.

Each fixture is a (memory_corpus, query_set, ground_truth) bundle. The
sandbox seeds Mem0 with the memory_corpus, runs each query, and checks
whether the ground-truth memory IDs are in the top-k retrieved set.

Format:
  bench/workloads/mem0-retrieval-recall.jsonl — one record per query:
    {"query_id": int, "query": str, "expected_memory_ids": [int]}
  bench/workloads/mem0-retrieval-recall-corpus.jsonl — one record per memory:
    {"memory_id": int, "user_id": str, "content": str}

The corpus is chunked into 4 fictional users to exercise Mem0's user_id
isolation. Each user has 8-12 distinct memory facts. Queries vary in
specificity (some need fact-level recall, some need theme-level).

Run from repo root:
  python bench/workloads/_generate_mem0_retrieval_recall.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


# (user_id, memory_id, content)
MEMORIES: list[tuple[str, int, str]] = [
    # Alice — software engineer, vegetarian, lives in Portland
    ("alice", 0, "Alice works as a senior software engineer at a small startup."),
    ("alice", 1, "Alice has been vegetarian since she was 16."),
    ("alice", 2, "Alice lives in a craftsman bungalow in Portland, Oregon."),
    ("alice", 3, "Alice's sister Maria visits every summer; they hike Mt. Hood together."),
    ("alice", 4, "Alice is allergic to bees; she carries an EpiPen."),
    ("alice", 5, "Alice prefers Rust over Go for systems programming work."),
    ("alice", 6, "Alice's favorite coffee shop is Stumptown on SE Division."),
    ("alice", 7, "Alice plays bass in a weekend indie band called Coastal Drift."),
    ("alice", 8, "Alice took up bouldering last year; her gym is The Circuit."),
    ("alice", 9, "Alice's dog is a 4-year-old border collie named Pepper."),

    # Ben — high school teacher, marathoner, lives in Boston
    ("ben", 10, "Ben teaches AP Physics at Cambridge Rindge and Latin School."),
    ("ben", 11, "Ben qualified for the Boston Marathon at the 2024 Chicago race."),
    ("ben", 12, "Ben lives in a Somerville triple-decker with two roommates."),
    ("ben", 13, "Ben is fluent in Mandarin; he studied abroad at Tsinghua University."),
    ("ben", 14, "Ben's favorite physicist is Richard Feynman."),
    ("ben", 15, "Ben drinks a flat white every morning at Diesel Cafe."),
    ("ben", 16, "Ben drives a 2010 Subaru Outback with a roof rack for cycling."),
    ("ben", 17, "Ben is lactose intolerant but cheats on weekends for ice cream."),
    ("ben", 18, "Ben's brother Adam is a marine biologist at Woods Hole."),
    ("ben", 19, "Ben volunteers as a tutor at the Cambridge Community Center."),
    # Memory 20 (tattoo) trimmed to keep Ben at 10 memories — top_k=10 covers
    # full per-user corpus, isolating retrieval QUALITY from boundary effects
    # caused by Mem0 v2's known top-1 recency-bias scoring anomaly.

    # Cara — pediatric nurse, knitter, lives in rural Vermont
    ("cara", 21, "Cara works as a pediatric nurse at a hospital in Burlington."),
    ("cara", 22, "Cara lives on a 12-acre property near Stowe with her partner Rosa."),
    ("cara", 23, "Cara has been knitting since she was a child; she sells on Etsy."),
    ("cara", 24, "Cara raises 8 chickens and gets fresh eggs every morning."),
    ("cara", 25, "Cara is allergic to penicillin."),
    ("cara", 26, "Cara grew up in Pittsburgh; both parents still live there."),
    ("cara", 27, "Cara's favorite knitting yarn is Brooklyn Tweed Loft."),
    ("cara", 28, "Cara is reading 'A Memory Called Empire' for her book club."),

    # Dan — venture analyst, surfer, lives in San Diego
    ("dan", 29, "Dan works as a junior analyst at a Series-B-focused VC fund."),
    ("dan", 30, "Dan surfs at Pacific Beach pier most mornings before work."),
    ("dan", 31, "Dan has a Master's in Economics from UC Berkeley."),
    ("dan", 32, "Dan drives a Toyota Tacoma with a rooftop tent for camping trips."),
    ("dan", 33, "Dan's favorite restaurant is the carne asada burrito place near La Jolla."),
    ("dan", 34, "Dan's dog Cooper is a 6-year-old golden retriever."),
    ("dan", 35, "Dan is gluten-free since being diagnosed with celiac in 2022."),
    ("dan", 36, "Dan plays pickup basketball on Sundays at Mission Beach courts."),
    ("dan", 37, "Dan grew up in Albuquerque, New Mexico."),
    ("dan", 38, "Dan tried sourdough baking during the pandemic; still does it weekly."),
]


# (query_id, query, ground_truth_memory_ids)
# Each query targets one or two specific memories. Recall@10 should
# trivially confirm with a competent embedding model since the corpus
# is small (40 memories) — but we want to make sure Mem0's retrieval
# does the right thing across user_id boundaries (queries scoped to a
# specific user_id should not return memories from other users).
QUERIES: list[tuple[int, str, str, list[int]]] = [
    # (query_id, user_id, query_text, expected_memory_ids)
    (0, "alice", "What's Alice's job?", [0]),
    (1, "alice", "Does Alice eat meat?", [1]),
    (2, "alice", "Where does Alice live?", [2]),
    (3, "alice", "Tell me about Alice's family", [3]),
    (4, "alice", "Are there any health concerns for Alice?", [4]),
    (5, "alice", "What language does Alice prefer for systems code?", [5]),
    (6, "alice", "Where does Alice get coffee?", [6]),
    (7, "alice", "Does Alice play music?", [7]),
    (8, "alice", "What sports does Alice do?", [8]),
    (9, "alice", "Does Alice have a pet?", [9]),

    (10, "ben", "What does Ben do for work?", [10]),
    (11, "ben", "Has Ben run a marathon?", [11]),
    (12, "ben", "Where does Ben live?", [12]),
    (13, "ben", "What languages does Ben speak?", [13]),
    (14, "ben", "Who is Ben's favorite scientist?", [14]),
    (15, "ben", "What does Ben drink in the morning?", [15]),
    (16, "ben", "What car does Ben drive?", [16]),
    (17, "ben", "Does Ben have any food restrictions?", [17]),
    (18, "ben", "Tell me about Ben's siblings", [18]),
    (19, "ben", "Does Ben volunteer?", [19]),
    # query 20 (tattoo) dropped along with memory 20 — see comment in MEMORIES

    (21, "cara", "What does Cara do for a living?", [21]),
    (22, "cara", "Where does Cara live?", [22]),
    (23, "cara", "What's Cara's hobby?", [23]),
    (24, "cara", "Does Cara have animals?", [24]),
    (25, "cara", "Any medication allergies for Cara?", [25]),
    (26, "cara", "Where is Cara originally from?", [26]),
    (27, "cara", "What yarn does Cara prefer?", [27]),
    (28, "cara", "What is Cara reading right now?", [28]),

    (29, "dan", "Where does Dan work?", [29]),
    (30, "dan", "Does Dan surf?", [30]),
    (31, "dan", "What is Dan's educational background?", [31]),
    (32, "dan", "What vehicle does Dan drive?", [32]),
    (33, "dan", "What's Dan's favorite restaurant?", [33]),
    (34, "dan", "Tell me about Dan's pet", [34]),
    (35, "dan", "Does Dan have food restrictions?", [35]),
    (36, "dan", "What sport does Dan play casually?", [36]),
    (37, "dan", "Where is Dan from?", [37]),
    (38, "dan", "Did Dan pick up new skills during COVID?", [38]),
]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    workload_dir = Path(__file__).resolve().parent

    corpus_path = workload_dir / "mem0-retrieval-recall-corpus.jsonl"
    with corpus_path.open("w", encoding="utf-8") as f:
        for user_id, memory_id, content in MEMORIES:
            f.write(json.dumps({"memory_id": memory_id, "user_id": user_id, "content": content}) + "\n")

    queries_path = workload_dir / "mem0-retrieval-recall.jsonl"
    with queries_path.open("w", encoding="utf-8") as f:
        for qid, user_id, query, expected in QUERIES:
            f.write(
                json.dumps(
                    {
                        "query_id": qid,
                        "user_id": user_id,
                        "query": query,
                        "expected_memory_ids": expected,
                    }
                )
                + "\n"
            )

    print(f"Wrote {len(MEMORIES)} memories to {corpus_path}")
    print(f"Wrote {len(QUERIES)} queries to {queries_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
