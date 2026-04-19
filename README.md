# Joplin MCP Server

A [Model Context Protocol](https://modelcontextprotocol.io/) server that lets Claude Code interact with [Joplin](https://joplinapp.org/) using natural language. It runs in an isolated Podman container and exposes the full Joplin REST API as MCP tools.

---

## Tutorial: Get up and running

This walkthrough takes you from zero to Claude Code talking to your Joplin notes.

### Prerequisites

- Podman installed and running
- Joplin desktop app running with the Web Clipper service enabled (Settings → Web Clipper)
- Claude Code installed

### Step 1 — Get your Joplin API token

In Joplin, open **Tools → Options → Web Clipper**. Copy the API token shown at the bottom of the page.

### Step 2 — Store the token as a Podman secret

```bash
echo -n "<your-token>" | podman secret create joplin_token -
```

Verify it was stored:

```bash
podman secret ls
```

The token never touches disk as a plaintext file and never appears in `podman inspect` or the process list.

### Step 3 — Build the container image

```bash
podman build -t joplin-mcp-server .
```

### Step 4 — Configure Claude Code

The repository already includes a `.mcp.json` file at the project root. Claude Code picks it up automatically when you open a project in this directory. No additional configuration is needed.

If you want the server available in every project, copy the same configuration to `~/.claude/settings.json` under the `mcpServers` key.

### Step 5 — Verify the connection

Start Claude Code in this project directory. In a conversation, ask:

> List my Joplin notebooks.

Claude Code will invoke the `list_folders` tool and return your notebooks. If you see results, everything is working.

---

## How-to guides

### How to run the unit tests

```bash
pip install -r requirements-dev.txt
pytest
```

All 40 tests run without a live Joplin instance. They mock the HTTP layer with `respx`.

### How to run the integration test against a live Joplin instance

Requires Joplin running locally with the Web Clipper enabled.

```bash
JOPLIN_TOKEN=<your-token> python tests/integration.py
```

The script creates a folder, a note, tags it, searches for it, then cleans up. Inspect its output to confirm end-to-end connectivity.

### How to rebuild the image after changing server.py

```bash
podman build -t joplin-mcp-server .
```

Claude Code spawns a fresh container per session, so the updated image is used immediately on the next session start.

### How to rotate the API token

```bash
podman secret rm joplin_token
echo -n "<new-token>" | podman secret create joplin_token -
```

No rebuild required. The container reads the secret at startup, so the next Claude Code session picks up the new token automatically.

### How to test the MCP handshake manually

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | \
  podman run --rm -i --secret joplin_token joplin-mcp-server
```

You should see a JSON response listing all 17 tools.

### How to use a Joplin instance not running on the host

By default the server contacts `http://host.containers.internal:41184` (the host machine as seen from inside the container). To point at a different address, set `JOPLIN_BASE_URL` in the container environment:

```json
{
  "mcpServers": {
    "joplin": {
      "command": "podman",
      "args": [
        "run", "--rm", "-i",
        "--secret", "joplin_token",
        "-e", "JOPLIN_BASE_URL=http://192.168.1.10:41184",
        "joplin-mcp-server"
      ]
    }
  }
}
```

---

## Reference

### MCP tools

#### Notes

| Tool | Parameters | Description |
|---|---|---|
| `create_note` | `title`, `body=""`, `parent_id=""` | Create a note |
| `get_note` | `note_id` | Retrieve a note by ID |
| `update_note` | `note_id`, `title=""`, `body=""` | Update title and/or body |
| `delete_note` | `note_id` | Delete a note |
| `list_notes` | `parent_id=""`, `page=1`, `limit=100` | List notes, optionally filtered by folder |

#### Folders (Notebooks)

| Tool | Parameters | Description |
|---|---|---|
| `create_folder` | `title`, `parent_id=""` | Create a folder |
| `get_folder` | `folder_id` | Retrieve a folder by ID |
| `update_folder` | `folder_id`, `title=""` | Rename a folder |
| `delete_folder` | `folder_id` | Delete a folder |
| `list_folders` | `page=1`, `limit=100` | List all folders |

#### Tags

| Tool | Parameters | Description |
|---|---|---|
| `create_tag` | `title` | Create a tag |
| `get_tag` | `tag_id` | Retrieve a tag by ID |
| `update_tag` | `tag_id`, `title=""` | Rename a tag |
| `delete_tag` | `tag_id` | Delete a tag |
| `list_tags` | `page=1`, `limit=100` | List all tags |
| `tag_note` | `tag_id`, `note_id` | Attach a tag to a note |
| `untag_note` | `tag_id`, `note_id` | Remove a tag from a note |

#### Search

| Tool | Parameters | Description |
|---|---|---|
| `search` | `query`, `type="note"`, `page=1`, `limit=100` | Full-text search. `type` can be `note`, `folder`, `tag`, or `resource` |

#### Resources (Attachments)

| Tool | Parameters | Description |
|---|---|---|
| `list_resources` | `page=1`, `limit=100` | List all resources |
| `get_resource` | `resource_id` | Retrieve resource metadata by ID |

Resource upload is not supported. The container has no access to host filesystem paths; uploading a local file would require a volume mount strategy not currently implemented.

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `JOPLIN_BASE_URL` | `http://localhost:41184` | Joplin API base URL. Inside the container, the host is reachable at `http://host.containers.internal:41184` |
| `JOPLIN_TOKEN` | _(none)_ | Fallback token source when the Podman secret is not available. Intended for local development and testing only |

### Token resolution order

1. `/run/secrets/joplin_token` (Podman secret — preferred in production)
2. `JOPLIN_TOKEN` environment variable (fallback for local dev and tests)

If neither is present, the server raises `RuntimeError` at startup.

### Known limitations

- `update_note`, `update_folder`, and `update_tag` use empty string as a sentinel for "not provided". This means you cannot clear a field by passing an empty string — the field will simply be left unchanged. This is a consequence of the Joplin API using query parameters only for authentication (no bearer token support), which forces all auth through the token query parameter.

### Project structure

```
.
├── server.py            # FastMCP server — all 17 MCP tools
├── Containerfile        # Podman image definition (python:3.13-alpine)
├── requirements.txt     # Runtime dependencies
├── requirements-dev.txt # Dev/test dependencies
├── .mcp.json            # Claude Code MCP server configuration
└── tests/
    ├── conftest.py      # Shared pytest fixtures
    ├── test_notes.py
    ├── test_folders.py
    ├── test_tags.py
    ├── test_search.py
    ├── test_resources.py
    └── integration.py   # Manual end-to-end test script
```

---

## Explanation

### Why a container instead of running server.py directly?

Isolation and secret management. Running the server in a Podman container means:

- The Joplin API token is stored as a Podman secret and mounted read-only inside the container. It is never visible in environment variables, `ps` output, or `podman inspect`.
- The server process has no access to the host filesystem or network beyond what is explicitly granted.
- Claude Code spawns a fresh container per session (`--rm`) — there is no persistent process to manage or restart.

### Why stdio transport instead of HTTP?

Claude Code connects to MCP servers over stdio (stdin/stdout). This is the standard transport for local MCP servers: the client spawns the server as a subprocess and communicates via JSON-RPC over the process's standard streams. No port binding, no network configuration, no authentication between client and server.

### Why a synchronous httpx client?

The stdio transport means there is exactly one MCP client (Claude Code) and MCP processes requests sequentially. There are no concurrent requests to the server, so an async event loop brings no benefit. A synchronous `httpx.Client` is simpler and equally correct here.

### Why host.containers.internal?

Podman containers run in a network namespace isolated from the host. `host.containers.internal` is Podman's DNS name for the gateway IP that routes back to the host — the equivalent of `host.docker.internal` in Docker. This lets the container reach a Joplin instance running on the host machine without any special network configuration.

### Architecture overview

```
[Claude Code]
     │  spawns per session via `podman run`
     ▼
[joplin-mcp-server container]
     │  stdio — MCP protocol (JSON-RPC)
     ◄►
     │  HTTP + token query parameter
     ▼
[Joplin API @ host.containers.internal:41184]
```
