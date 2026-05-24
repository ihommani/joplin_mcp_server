# Project: Joplin MCP Server

A FastMCP server that exposes the Joplin REST API as MCP tools, packaged as a Podman container.

---

## Architecture

```
[Claude Code]
     │  spawns per session via `podman run`
     ▼
[joplin-mcp-server container]   ←→ stdio (MCP / JSON-RPC)
     │
     │  HTTP + token query param
     ▼
[Joplin API @ host.containers.internal:41184]
```

- One file does everything: `server.py`. Do not split it without a strong reason.
- Transport is stdio, not HTTP. Claude Code spawns the container and communicates over stdin/stdout.
- The container exits when the session ends (`--rm`).
- `host.containers.internal` is Podman's DNS name for the host machine inside a container.

---

## Key design decisions (do not change without discussion)

### Sync httpx.Client, not async
One MCP client, sequential requests. An async event loop adds no value here and complicates the code.

### Token via Podman secret, not env var
`/run/secrets/joplin_token` is the production path. `JOPLIN_TOKEN` env var is a fallback for tests only. The token is injected as a query param on every request because the Joplin API supports no other auth mechanism.

### Empty string as "not provided" sentinel
`update_note`, `update_folder`, `update_tag` use `title=""` etc. as defaults. Empty strings are skipped — the field is not sent. This means you **cannot clear a field** by passing `""`. This is a known limitation, documented in each tool's docstring.

### Alpine base image
`python:3.13-alpine` (~103 MiB). Only fall back to `python:3.13-slim` if a dependency requires native compilation unavailable for musl.

---

## File layout

```
server.py            ← the entire server (do not split)
Containerfile        ← Podman image definition
requirements.txt     ← runtime: mcp[cli], httpx
requirements-dev.txt ← test: pytest, respx
.mcp.json            ← Claude Code MCP server config (project-level)
tests/
  conftest.py        ← autouse fixtures: reset _client, set JOPLIN_TOKEN
  test_notes.py
  test_folders.py
  test_tags.py
  test_search.py
  test_resources.py
  integration.py     ← manual end-to-end script, NOT part of CI
```

---

## Test conventions

- Framework: `pytest` + `respx` for HTTP mocking
- **Never mock the MCP layer** — call `server.<tool_name>()` directly in tests
- `respx.mock(base_url=BASE)` intercepts `httpx` at the transport level
- Verify: request method/path, request body, response parsing, and error surfacing
- `conftest.py` resets `server._client = None` before and after each test (autouse)
- `conftest.py` sets `JOPLIN_TOKEN=test-token` via monkeypatch (autouse); it does **not** set `JOPLIN_BASE_URL`, so `server._BASE_URL` defaults to `http://localhost:41184` during tests
- Each test file defines its own `BASE = "http://localhost:41184"` constant that matches the server's default `_BASE_URL` — both must stay in sync
- Override the server's base URL in tests via `JOPLIN_BASE_URL` env var if needed

Run tests:
```bash
pip install -r requirements-dev.txt
pytest
```

Integration test (requires live Joplin):
```bash
JOPLIN_TOKEN=<token> python tests/integration.py
```

---

## Build and run

```bash
# Build
podman build -t joplin-mcp-server .

# Create secret (once)
echo -n "<token>" | podman secret create joplin_token -
podman secret ls   # verify it exists

# Run manually
podman run --rm -i --network host --secret joplin_token joplin-mcp-server
```

---

## MCP tools (17 total)

| Domain | Tools |
|---|---|
| Notes | `create_note`, `get_note`, `update_note`, `delete_note`, `list_notes` |
| Folders | `create_folder`, `get_folder`, `update_folder`, `delete_folder`, `list_folders` |
| Tags | `create_tag`, `get_tag`, `update_tag`, `delete_tag`, `list_tags`, `tag_note`, `untag_note` |
| Search | `search` |
| Resources | `list_resources`, `get_resource` |

Resource upload is out of scope (requires volume mount strategy not yet implemented).

---

## Out of scope (do not add without approval)

- mcp-gateway or proxy integration
- Async transport or multi-client support
- Resource upload
- Additional Joplin API endpoints (revisions, events)
- Any feature not explicitly requested
