# ocm-mcp

MCP server bridge for OpenCircuitModel. Spawn this binary from any MCP client
(Claude Code, Cursor, Cline, Continue.dev, ChatGPT MCP connectors, etc.) to
expose OCM as a structured tool surface alongside its OpenAI-compat HTTP API.

## Architecture

```
[MCP client e.g. Claude Code]
   |  spawns subprocess; communicates via stdio JSON-RPC
   v
[ocm-mcp]
   |  HTTP requests to localhost:7300 (configurable via OCM_API_URL)
   v
[OCM daemon — ocm-api crate]
   |  forwards to inference + memory layers
   v
[Mem0 + llama-server / vLLM / etc.]
```

The bridge keeps the MCP surface decoupled from the daemon's port: a client
spawning `ocm-mcp` doesn't need to know what port the daemon listens on.

## Tools exposed

- **`chat`** — send a message to the OCM agent. The agent has persistent
  memory + library-driven retrieval per spec row 9, so the MCP client doesn't
  need to manage memory itself.
- **`list_models`** — list models available to the OCM daemon.

More tools (memory_search, memory_add, palace_search, etc.) land in follow-up
phases when the spec rows for those features ship.

## Configuration

Set `OCM_API_URL` to point at a non-default daemon URL:

```bash
OCM_API_URL=http://127.0.0.1:7300 ocm-mcp
```

## Example MCP client config (Claude Code)

```json
{
  "mcpServers": {
    "ocm": {
      "command": "ocm-mcp",
      "env": { "OCM_API_URL": "http://127.0.0.1:7300" }
    }
  }
}
```

## Wire format

JSON-RPC 2.0 over stdio per the [MCP specification](https://modelcontextprotocol.io).
Each line is a complete JSON object. Methods supported:

- `initialize` — server identity + capabilities
- `tools/list` — array of available tools
- `tools/call` — invoke a named tool with arguments
- Notifications (no `id` field) are accepted but produce no response

## License

Apache 2.0 — same as the parent OCM project.
