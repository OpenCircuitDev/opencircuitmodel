"""Generate chat-singleturn-1k.jsonl: 1000 diverse single-turn prompts.

Reproducible. Deterministic seed.

Run from bench/ directory:
    python workloads/_generate_chat_singleturn.py
"""

from __future__ import annotations

import json
import random
from pathlib import Path

OUT = Path(__file__).parent / "chat-singleturn-1k.jsonl"

SEED = 20260509


CATEGORIES = {
    "factual": [
        "What is the capital of {country}?",
        "Who wrote {book}?",
        "When did {event} happen?",
        "What does {acronym} stand for?",
        "How many {unit} in a {bigger_unit}?",
    ],
    "reasoning": [
        "If I have {n} apples and give away {k}, how many do I have left?",
        "A train leaves at {time1} and arrives at {time2}. How long is the trip?",
        "Compare {item1} and {item2} on three dimensions.",
        "Explain why {phenomenon} happens.",
        "What's the next number in the sequence: {sequence}?",
    ],
    "code": [
        "Write a Python function that returns the {operation} of a list.",
        "Implement a {pattern} pattern in Python.",
        "Convert this snake_case to camelCase: {snake}",
        "Reverse a string in {language} without using built-in reverse.",
        "Write a SQL query to {sql_task}.",
    ],
    "creative": [
        "Write a haiku about {topic}.",
        "Describe a {place} in three sentences.",
        "Compose a tagline for {product}.",
        "Tell a 100-word story involving {character} and {object}.",
        "What's an interesting fact about {topic}?",
    ],
    "instruction": [
        "Summarize {topic} in one sentence.",
        "List three pros and three cons of {choice}.",
        "Translate '{phrase}' to {language}.",
        "Convert {temp}F to Celsius.",
        "Outline the steps to {task}.",
    ],
    "tool_use": [
        "I need to read a file at {path}; give me the right command.",
        "What tool would I use to {operation_x}?",
        "Generate a regex that matches {pattern_descr}.",
        "Compose a curl request to {endpoint}.",
        "Build a one-liner shell command to {shell_task}.",
    ],
}

FILLERS = {
    "country": ["France", "Japan", "Brazil", "Egypt", "Norway", "India", "Chile", "Kenya"],
    "book": ["1984", "Pride and Prejudice", "Beloved", "Dune", "The Trial", "Crime and Punishment"],
    "event": ["the Apollo 11 landing", "the fall of the Berlin Wall", "the Cuban Missile Crisis"],
    "acronym": ["NATO", "DNA", "CPU", "API", "HTTP", "JSON", "DHCP", "TLS"],
    "unit": ["seconds", "millimeters", "ounces", "feet", "minutes"],
    "bigger_unit": ["minute", "meter", "pound", "yard", "hour"],
    "n": [str(x) for x in range(5, 50)],
    "k": [str(x) for x in range(1, 10)],
    "time1": ["9:00am", "1:30pm", "6:45am", "11:15pm"],
    "time2": ["11:30am", "4:00pm", "9:20am", "2:45am"],
    "item1": ["Python", "Rust", "TCP", "REST", "SQL", "graph databases"],
    "item2": ["JavaScript", "Go", "UDP", "GraphQL", "NoSQL", "key-value stores"],
    "phenomenon": [
        "rainbows form",
        "tides happen",
        "compilers do dead-code elimination",
        "neural networks generalize",
    ],
    "sequence": ["2, 4, 8, 16", "1, 1, 2, 3, 5", "100, 81, 64, 49", "3, 6, 9, 12"],
    "operation": ["sum", "product", "median", "longest run of duplicates", "second-largest element"],
    "pattern": ["singleton", "observer", "factory", "decorator", "strategy"],
    "snake": ["read_file_async", "compute_total_cost", "validate_email_address"],
    "language": ["Python", "Rust", "Go", "TypeScript", "Spanish", "French", "Mandarin"],
    "sql_task": [
        "find users registered in the last 7 days",
        "count orders per region",
        "find the second-highest salary",
        "join customers with their last purchase",
    ],
    "topic": ["the ocean", "machine learning", "ancient Rome", "compilers", "honeybees", "graph theory"],
    "place": ["a derelict train station", "an alpine meadow", "a futuristic library"],
    "product": ["a citizen-science compute network", "a privacy-preserving search engine"],
    "character": ["a retired astronaut", "a curious cat", "a bookbinder", "a quantum physicist"],
    "object": ["a brass telescope", "a faded letter", "an unmarked USB drive"],
    "choice": ["working remotely", "running a marathon", "learning Rust", "writing a novel"],
    "phrase": ["good morning", "thank you very much", "see you tomorrow"],
    "temp": [str(x) for x in (32, 50, 68, 85, 100, 212, 0)],
    "task": ["bake bread", "set up Tor", "publish to PyPI", "deploy a Tauri app"],
    "path": ["/var/log/syslog", "C:/Users/dev/notes.md", "~/projects/repo/main.py"],
    "operation_x": ["minify JSON", "diff two directories", "find duplicate photos"],
    "pattern_descr": [
        "valid email addresses",
        "ISO-8601 dates",
        "hex color codes",
        "phone numbers in E.164",
    ],
    "endpoint": ["the GitHub API issues endpoint", "the Anthropic messages endpoint"],
    "shell_task": [
        "find files larger than 100MB modified in the last week",
        "count lines of Python in a directory",
        "decode a base64 string from stdin",
    ],
}


def fill_template(template: str, rng: random.Random) -> str:
    out = template
    for key, options in FILLERS.items():
        placeholder = "{" + key + "}"
        if placeholder in out:
            out = out.replace(placeholder, rng.choice(options))
    return out


def main() -> None:
    rng = random.Random(SEED)
    rows = []
    target = 1000
    per_category = target // len(CATEGORIES)
    for category, templates in CATEGORIES.items():
        for _ in range(per_category):
            template = rng.choice(templates)
            prompt = fill_template(template, rng)
            rows.append({"category": category, "prompt": prompt})

    while len(rows) < target:
        category = rng.choice(list(CATEGORIES))
        template = rng.choice(CATEGORIES[category])
        rows.append({"category": category, "prompt": fill_template(template, rng)})

    rng.shuffle(rows)
    with OUT.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
    print(f"Wrote {len(rows)} prompts to {OUT}")


if __name__ == "__main__":
    main()
