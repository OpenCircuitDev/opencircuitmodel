"""Schema compression token impact (Sandbox E).

Reads MCP tool definitions from /workloads/mcp-tool-defs-30.jsonl, computes
input-token count BEFORE compression, applies the canonical schema-compression
recipe (strip descriptions, shorten param names, hide optional params), and
computes input-token count AFTER. Reports median pct reduction across the
30 tool definitions.

Pure measurement — no model invocation. The secondary metric (tool-call
accuracy delta) is intentionally OUT of scope here; that requires a model
and lives in a future paired sandbox.

Output: outputs.json with primary_value = pct_reduction_median.
"""

from __future__ import annotations

import json
import os
import statistics
import time
from pathlib import Path

# ----------------------------------------------------------------------
# Tokenizer — use cl100k_base (OpenAI GPT-4 / Claude tokenizer family)
# via tiktoken if available; fall back to a deterministic heuristic so the
# sandbox runs without dependencies in degraded mode.
# ----------------------------------------------------------------------

try:
    import tiktoken  # type: ignore
    _TOKENIZER = tiktoken.get_encoding("cl100k_base")

    def count_tokens(text: str) -> int:
        return len(_TOKENIZER.encode(text))

    TOKENIZER_NAME = "cl100k_base"
except ImportError:
    # Deterministic fallback: 4 chars per token (cl100k_base average).
    # Conservative enough for relative-comparison purposes since we apply
    # the same heuristic to BOTH sides of the diff.
    def count_tokens(text: str) -> int:
        return max(1, len(text) // 4)

    TOKENIZER_NAME = "char-div-4-fallback"


# ----------------------------------------------------------------------
# Compression recipe (per spec v0.2 row 21)
# ----------------------------------------------------------------------

_PARAM_NAME_MAP = {
    # Common verbose names → 1-3 char abbreviations. The model sees the
    # abbreviation; OCM's MCP layer keeps the original-name mapping
    # internally so tool dispatch still works.
    "encoding": "e",
    "max_bytes": "mb",
    "max_results": "mr",
    "include_hidden": "ih",
    "follow_symlinks": "fs",
    "permanent": "p",
    "respect_gitignore": "rg",
    "follow_redirects": "fr",
    "viewport_width": "vw",
    "viewport_height": "vh",
    "wait_seconds": "ws",
    "full_page": "fp",
    "fixed_strings": "f",
    "context_lines": "cl",
    "case_insensitive": "ci",
    "language": "l",
    "fix": "fx",
    "filter": "ft",
    "verbose": "v",
    "check_only": "co",
    "calendar_id": "cid",
    "apply_to": "at",
    "duration_minutes": "dm",
    "window_start": "ws_",
    "window_end": "we_",
    "attendees": "at_",
    "cc": "cc",
    "bcc": "bcc",
    "reply_to": "rt",
    "since": "sn",
    "unread_only": "uo",
    "include_html": "ih_",
    "email_id": "eid",
    "email_ids": "eids",
    "max_results": "mr",
    "timeout_seconds": "ts",
    "headers": "h",
    "overwrite": "o",
    "create_parents": "cp",
    "new_window": "nw",
    "urgency": "u",
}


def compress_tool(tool: dict) -> dict:
    """Apply the canonical compression recipe to one MCP tool definition.

    Steps:
      1. Strip top-level tool description (keep name)
      2. Strip per-parameter descriptions
      3. Shorten parameter names per _PARAM_NAME_MAP
      4. Hide optional parameters entirely (model only sees required ones)
      5. Drop default values from the schema (the runtime applies them)

    The compressed shape is still a valid MCP tool definition; the original-
    parameter-name mapping is reconstructed by OCM's MCP layer from a
    side-table when the model selects a tool to call. That layer is out
    of scope for this benchmark — we only measure the token-budget impact.
    """
    name = tool["name"]
    schema = tool.get("inputSchema", {})
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))

    compressed_props: dict[str, dict] = {}
    for param_name, param_def in properties.items():
        if param_name not in required:
            continue  # hide optional
        short = _PARAM_NAME_MAP.get(param_name, param_name)
        compressed_props[short] = {"type": param_def.get("type", "string")}
        # Preserve nested 'items' for arrays (model needs to know element type)
        if "items" in param_def:
            compressed_props[short]["items"] = {"type": param_def["items"].get("type", "string")}

    return {
        "name": name,
        "inputSchema": {
            "type": "object",
            "properties": compressed_props,
            "required": [_PARAM_NAME_MAP.get(p, p) for p in schema.get("required", [])],
        },
    }


def serialize_for_model(tool: dict) -> str:
    """Serialize a tool definition the way it'd be embedded in a prompt."""
    return json.dumps(tool, ensure_ascii=False, separators=(",", ":"))


# ----------------------------------------------------------------------
# Bench entry point
# ----------------------------------------------------------------------

def main() -> int:
    workload_path = Path(os.environ.get("WORKLOAD_PATH", "/workloads/mcp-tool-defs-30.jsonl"))
    if not workload_path.exists():
        # Local dev: workload sits in repo at bench/workloads/
        repo_workload = Path(__file__).resolve().parents[3] / "workloads" / "mcp-tool-defs-30.jsonl"
        if repo_workload.exists():
            workload_path = repo_workload
        else:
            print(f"ERROR: workload not found at {workload_path} or {repo_workload}")
            return 2

    tools: list[dict] = []
    with workload_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                tools.append(json.loads(line))

    if not tools:
        print("ERROR: workload is empty")
        return 2

    pct_reductions: list[float] = []
    before_tokens_per_tool: list[int] = []
    after_tokens_per_tool: list[int] = []
    started = time.monotonic()

    for tool in tools:
        before = count_tokens(serialize_for_model(tool))
        compressed = compress_tool(tool)
        after = count_tokens(serialize_for_model(compressed))
        pct = (1 - after / before) * 100 if before > 0 else 0.0
        pct_reductions.append(pct)
        before_tokens_per_tool.append(before)
        after_tokens_per_tool.append(after)

    elapsed = time.monotonic() - started
    median_pct = statistics.median(pct_reductions)
    median_before = statistics.median(before_tokens_per_tool)
    median_after = statistics.median(after_tokens_per_tool)

    output = {
        "primary_value": median_pct,
        "duration_seconds": elapsed,
        "n_tools": len(tools),
        "tokenizer": TOKENIZER_NAME,
        "before_tokens_median": median_before,
        "after_tokens_median": median_after,
        # Per-tool detail for debugging / report-generation
        "per_tool_pct_reduction": pct_reductions,
    }

    Path("outputs.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
