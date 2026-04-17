# Joplin MCP Server — Design Spec

**Date:** 2026-04-18
**Status:** Approved

---

## Goal

Build a Joplin MCP server that lets Claude Code interact with the Joplin note manager using natural language. The server exposes the full Joplin REST API surface as MCP tools, runs in an isolated Podman container, and connects directly to Claude Code via stdio — no proxy or gateway.

---

## Architecture

```
[Claude Code]
     │  spawns per session via `podman run`
     ▼
[joplin-mcp-server container]
     │  stdio — MCP protocol
     ◄►
     │  HTTP + token query param
     ▼
[Joplin API @ host.containers.internal:41184]
```

- Claude Code spawns the container per session using `podman run --rm -i`.
- The MCP protocol runs over stdio between Claude Code and the container.
- The container reaches the Joplin API on the host via `host.containers.internal:41184` (Podman's name for the host network interface).
- The container exits cleanly when the Claude Code session ends (`--rm`).

---

## Components

### `server.py`

FastMCP server with stdio transport. At startup it reads the Joplin API token from `/run/secrets/joplin_token` and constructs a shared `httpx` client.

MCP tools exposed:

**Notes**
- `create_note(title, body, parent_id="")` — create a note in markdown
- `get_note(note_id)` — retrieve a note by ID
- `update_note(note_id, title="", body="")` — update title and/or body
- `delete_note(note_id)` — delete a note
- `list_notes(parent_id="", page=1, limit=100)` — list notes, with optional folder filter and pagination

**Folders (Notebooks)**
- `create_folder(title, parent_id="")` — create a folder/notebook
- `get_folder(folder_id)` — retrieve a folder by ID
- `update_folder(folder_id, title="")` — rename a folder
- `delete_folder(folder_id)` — delete a folder
- `list_folders(page=1, limit=100)` — list all folders

**Tags**
- `create_tag(title)` — create a tag
- `get_tag(tag_id)` — retrieve a tag by ID
- `update_tag(tag_id, title="")` — rename a tag
- `delete_tag(tag_id)` — delete a tag
- `list_tags(page=1, limit=100)` — list all tags
- `tag_note(tag_id, note_id)` — attach a tag to a note
- `untag_note(tag_id, note_id)` — remove a tag from a note

**Search**
- `search(query, type="note", page=1, limit=100)` — full-text search, optional type filter (`note`, `folder`, `tag`, `resource`)

**Resources (Attachments)**
- `list_resources(page=1, limit=100)` — list all resources
- `get_resource(resource_id)` — retrieve resource metadata

Note: resource upload is excluded from initial scope. The container has no access to host filesystem paths, so uploading a local file would require a host volume mount strategy — deferred to a future iteration.

All tool docstrings are single-line. No `@mcp.prompt()` decorators. Parameters default to empty strings rather than `None` to avoid FastMCP compatibility issues.

### `Containerfile`

- Base image: `python:3.13-alpine` (preferred for smaller footprint; fall back to `python:3.13-slim` if any dependency lacks a musllinux wheel and requires native compilation)
- Non-root user (`appuser`)
- Copies `requirements.txt` and `server.py`
- Installs dependencies via `pip install --no-cache-dir`
- Entrypoint: `python server.py`

### `requirements.txt`

```
mcp[cli]>=1.2.0
httpx>=0.27.0
```

---

## Secrets & Configuration

### Creating the Podman secret

```bash
echo -n "<your-joplin-token>" | podman secret create joplin_token -
```

The token is read from stdin — it never touches disk as plaintext. Verify with `podman secret ls`.

### Inside the container

The secret is mounted read-only at `/run/secrets/joplin_token`. `server.py` reads it at startup:

```python
with open("/run/secrets/joplin_token") as f:
    token = f.read().strip()
```

The token is never passed as an environment variable and never appears in `podman inspect` or the process list.

### Claude Code configuration

In `~/.claude/settings.json` (global) or `.claude/settings.json` (project-level):

```json
{
  "mcpServers": {
    "joplin": {
      "command": "podman",
      "args": [
        "run", "--rm", "-i",
        "--secret", "joplin_token",
        "joplin-mcp-server"
      ]
    }
  }
}
```

- `--rm` removes the container after the session ends.
- `-i` keeps stdin open for MCP stdio communication.
- `--secret joplin_token` mounts the Podman secret inside the container.

---

## Build & Run

```bash
# Build the image
podman build -t joplin-mcp-server .

# Test manually (MCP handshake over stdio)
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | \
  podman run --rm -i --secret joplin_token joplin-mcp-server
```

---

## Testing

### Unit tests (`pytest` + `respx`)

`respx` mocks `httpx` transports. Each tool is tested for:
- Correct HTTP method, path, and query parameters
- Correct request body construction
- Correct response parsing
- Error responses (4xx/5xx from Joplin API) surfaced as meaningful MCP errors

Tests do not require a running Joplin instance and run in CI.

### Integration test script

A standalone `tests/integration.py` script that hits the real Joplin API (requires Joplin running locally and `JOPLIN_TOKEN` set). Run manually to verify end-to-end connectivity. Not part of CI.

---

## Future Considerations (out of scope)

- mcp-gateway-registry or Docker MCP Gateway integration
- streamable-HTTP transport for multi-client scenarios
- Resource upload via host volume mount (`--volume` in podman run args)
- Additional Joplin API endpoints (revisions, events)
