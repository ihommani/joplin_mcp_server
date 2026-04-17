# Joplin MCP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Joplin MCP server in Python that exposes Joplin's REST API as MCP tools, runs in a Podman container, and connects to Claude Code via stdio.

**Architecture:** FastMCP server with stdio transport. Claude Code spawns the container per session via `podman run --rm -i --secret joplin_token joplin-mcp-server`. The container reaches the Joplin API at `host.containers.internal:41184`. The API token is injected via Podman native secret, read from `/run/secrets/joplin_token` at startup with fallback to `JOPLIN_TOKEN` env var for tests.

**Tech Stack:** Python 3.13, FastMCP (`mcp[cli]`), httpx, pytest, respx, Podman, Alpine Linux.

---

## Task 1: Git init + project scaffold

**Files:**
- Create: `.gitignore`
- Create: `requirements.txt`
- Create: `requirements-dev.txt`

- [ ] **Step 1: Initialize git repository**

```bash
cd /var/home/ihommani/Projects/joplin_mcp_server
git init
```

Expected: `Initialized empty Git repository in .../joplin_mcp_server/.git/`

- [ ] **Step 2: Create `.gitignore`**

```
__pycache__/
*.pyc
*.pyo
.pytest_cache/
.venv/
venv/
dist/
*.egg-info/
.env
```

- [ ] **Step 3: Create `requirements.txt`**

```
mcp[cli]>=1.2.0
httpx>=0.27.0
```

- [ ] **Step 4: Create `requirements-dev.txt`**

```
pytest>=8.0.0
respx>=0.21.0
```

- [ ] **Step 5: Commit**

```bash
git add .gitignore requirements.txt requirements-dev.txt
git commit -m "chore: project scaffold"
```

---

## Task 2: Server skeleton

**Files:**
- Create: `server.py`

- [ ] **Step 1: Create `server.py` with token loading and client initialization**

```python
import os
import httpx
from pathlib import Path
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("joplin")

_BASE_URL = "http://host.containers.internal:41184"
_client: httpx.Client | None = None


def _load_token() -> str:
    secret_path = Path("/run/secrets/joplin_token")
    if secret_path.exists():
        return secret_path.read_text().strip()
    token = os.getenv("JOPLIN_TOKEN")
    if not token:
        raise RuntimeError("Joplin API token not found in secret or JOPLIN_TOKEN env var")
    return token


def _get_client() -> httpx.Client:
    global _client
    if _client is None:
        token = _load_token()
        _client = httpx.Client(base_url=_BASE_URL, params={"token": token})
    return _client


if __name__ == "__main__":
    mcp.run()
```

- [ ] **Step 2: Install dev dependencies**

```bash
pip install -r requirements.txt -r requirements-dev.txt
```

Expected: all packages install without error.

- [ ] **Step 3: Verify server starts**

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0"}}}' \
  | JOPLIN_TOKEN=test python server.py
```

Expected: JSON response containing `"result"` with server capabilities, then process waits on stdin.
Interrupt with Ctrl-C.

- [ ] **Step 4: Commit**

```bash
git add server.py
git commit -m "feat: server skeleton with token loading and httpx client"
```

---

## Task 3: Test infrastructure

**Files:**
- Create: `tests/conftest.py`

- [ ] **Step 1: Create `tests/conftest.py`**

```python
import pytest
import server


@pytest.fixture(autouse=True)
def reset_client():
    """Reset the lazy httpx client singleton before and after each test."""
    server._client = None
    yield
    server._client = None


@pytest.fixture(autouse=True)
def joplin_token(monkeypatch):
    """Provide a fake token via env var so _load_token() doesn't look for a secret file."""
    monkeypatch.setenv("JOPLIN_TOKEN", "test-token")
```

- [ ] **Step 2: Verify test infrastructure works**

```bash
pytest tests/ -v
```

Expected: no tests collected, no errors. Output: `no tests ran`.

- [ ] **Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "test: add test infrastructure and fixtures"
```

---

## Task 4: Notes tools

**Files:**
- Modify: `server.py`
- Create: `tests/test_notes.py`

- [ ] **Step 1: Write failing tests for all note tools**

Create `tests/test_notes.py`:

```python
import json
import pytest
import httpx
import respx

import server

BASE = "http://host.containers.internal:41184"


def test_create_note_sends_title_and_body():
    with respx.mock(base_url=BASE) as mock:
        route = mock.post("/notes").mock(
            return_value=httpx.Response(200, json={"id": "note-1", "title": "My Note"})
        )
        result = server.create_note(title="My Note", body="Hello world")
        assert route.called
        body = json.loads(route.calls[0].request.content)
        assert body["title"] == "My Note"
        assert body["body"] == "Hello world"
        assert result == {"id": "note-1", "title": "My Note"}


def test_create_note_includes_parent_id_when_provided():
    with respx.mock(base_url=BASE) as mock:
        route = mock.post("/notes").mock(
            return_value=httpx.Response(200, json={"id": "note-1", "title": "My Note"})
        )
        server.create_note(title="My Note", body="", parent_id="folder-99")
        body = json.loads(route.calls[0].request.content)
        assert body["parent_id"] == "folder-99"


def test_create_note_omits_parent_id_when_empty():
    with respx.mock(base_url=BASE) as mock:
        route = mock.post("/notes").mock(
            return_value=httpx.Response(200, json={"id": "note-1", "title": "My Note"})
        )
        server.create_note(title="My Note", body="")
        body = json.loads(route.calls[0].request.content)
        assert "parent_id" not in body


def test_get_note_calls_correct_endpoint():
    with respx.mock(base_url=BASE) as mock:
        route = mock.get("/notes/note-1").mock(
            return_value=httpx.Response(200, json={"id": "note-1", "title": "My Note"})
        )
        result = server.get_note(note_id="note-1")
        assert route.called
        assert result["id"] == "note-1"


def test_update_note_sends_provided_fields():
    with respx.mock(base_url=BASE) as mock:
        route = mock.put("/notes/note-1").mock(
            return_value=httpx.Response(200, json={"id": "note-1", "title": "New Title"})
        )
        server.update_note(note_id="note-1", title="New Title")
        body = json.loads(route.calls[0].request.content)
        assert body["title"] == "New Title"
        assert "body" not in body


def test_update_note_omits_empty_fields():
    with respx.mock(base_url=BASE) as mock:
        route = mock.put("/notes/note-1").mock(
            return_value=httpx.Response(200, json={"id": "note-1"})
        )
        server.update_note(note_id="note-1")
        body = json.loads(route.calls[0].request.content)
        assert body == {}


def test_delete_note_calls_correct_endpoint():
    with respx.mock(base_url=BASE) as mock:
        route = mock.delete("/notes/note-1").mock(
            return_value=httpx.Response(204)
        )
        result = server.delete_note(note_id="note-1")
        assert route.called
        assert result == {"success": True}


def test_list_notes_without_parent_calls_notes_endpoint():
    with respx.mock(base_url=BASE) as mock:
        route = mock.get("/notes").mock(
            return_value=httpx.Response(200, json={"items": [], "has_more": False})
        )
        result = server.list_notes()
        assert route.called
        assert result == {"items": [], "has_more": False}


def test_list_notes_with_parent_calls_folder_notes_endpoint():
    with respx.mock(base_url=BASE) as mock:
        route = mock.get("/folders/folder-1/notes").mock(
            return_value=httpx.Response(200, json={"items": [], "has_more": False})
        )
        server.list_notes(parent_id="folder-1")
        assert route.called


def test_note_api_error_raises():
    with respx.mock(base_url=BASE) as mock:
        mock.get("/notes/bad-id").mock(
            return_value=httpx.Response(404, json={"error": "Note not found"})
        )
        with pytest.raises(httpx.HTTPStatusError):
            server.get_note(note_id="bad-id")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_notes.py -v
```

Expected: all tests FAIL with `AttributeError: module 'server' has no attribute 'create_note'`.

- [ ] **Step 3: Implement note tools in `server.py`**

Add after `_get_client()` definition:

```python
# --- Notes ---

@mcp.tool()
def create_note(title: str, body: str = "", parent_id: str = "") -> dict:
    """Create a new note in Joplin."""
    payload = {"title": title, "body": body}
    if parent_id:
        payload["parent_id"] = parent_id
    resp = _get_client().post("/notes", json=payload)
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def get_note(note_id: str) -> dict:
    """Retrieve a note by ID."""
    resp = _get_client().get(f"/notes/{note_id}")
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def update_note(note_id: str, title: str = "", body: str = "") -> dict:
    """Update a note's title and/or body."""
    payload = {}
    if title:
        payload["title"] = title
    if body:
        payload["body"] = body
    resp = _get_client().put(f"/notes/{note_id}", json=payload)
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def delete_note(note_id: str) -> dict:
    """Delete a note by ID."""
    resp = _get_client().delete(f"/notes/{note_id}")
    resp.raise_for_status()
    return {"success": True}


@mcp.tool()
def list_notes(parent_id: str = "", page: int = 1, limit: int = 100) -> dict:
    """List notes with optional folder filter and pagination."""
    params = {"page": page, "limit": limit}
    if parent_id:
        resp = _get_client().get(f"/folders/{parent_id}/notes", params=params)
    else:
        resp = _get_client().get("/notes", params=params)
    resp.raise_for_status()
    return resp.json()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_notes.py -v
```

Expected: all 10 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add server.py tests/test_notes.py
git commit -m "feat: add note tools (create, get, update, delete, list)"
```

---

## Task 5: Folders tools

**Files:**
- Modify: `server.py`
- Create: `tests/test_folders.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_folders.py`:

```python
import json
import pytest
import httpx
import respx

import server

BASE = "http://host.containers.internal:41184"


def test_create_folder_sends_title():
    with respx.mock(base_url=BASE) as mock:
        route = mock.post("/folders").mock(
            return_value=httpx.Response(200, json={"id": "folder-1", "title": "Work"})
        )
        result = server.create_folder(title="Work")
        body = json.loads(route.calls[0].request.content)
        assert body["title"] == "Work"
        assert "parent_id" not in body
        assert result["id"] == "folder-1"


def test_create_folder_includes_parent_id_when_provided():
    with respx.mock(base_url=BASE) as mock:
        route = mock.post("/folders").mock(
            return_value=httpx.Response(200, json={"id": "folder-2", "title": "Sub"})
        )
        server.create_folder(title="Sub", parent_id="folder-1")
        body = json.loads(route.calls[0].request.content)
        assert body["parent_id"] == "folder-1"


def test_get_folder_calls_correct_endpoint():
    with respx.mock(base_url=BASE) as mock:
        route = mock.get("/folders/folder-1").mock(
            return_value=httpx.Response(200, json={"id": "folder-1", "title": "Work"})
        )
        result = server.get_folder(folder_id="folder-1")
        assert route.called
        assert result["id"] == "folder-1"


def test_update_folder_sends_title():
    with respx.mock(base_url=BASE) as mock:
        route = mock.put("/folders/folder-1").mock(
            return_value=httpx.Response(200, json={"id": "folder-1", "title": "Personal"})
        )
        server.update_folder(folder_id="folder-1", title="Personal")
        body = json.loads(route.calls[0].request.content)
        assert body["title"] == "Personal"


def test_update_folder_sends_empty_payload_when_no_title():
    with respx.mock(base_url=BASE) as mock:
        route = mock.put("/folders/folder-1").mock(
            return_value=httpx.Response(200, json={"id": "folder-1"})
        )
        server.update_folder(folder_id="folder-1")
        body = json.loads(route.calls[0].request.content)
        assert body == {}


def test_delete_folder_calls_correct_endpoint():
    with respx.mock(base_url=BASE) as mock:
        route = mock.delete("/folders/folder-1").mock(
            return_value=httpx.Response(204)
        )
        result = server.delete_folder(folder_id="folder-1")
        assert route.called
        assert result == {"success": True}


def test_list_folders_calls_folders_endpoint():
    with respx.mock(base_url=BASE) as mock:
        route = mock.get("/folders").mock(
            return_value=httpx.Response(200, json={"items": [], "has_more": False})
        )
        result = server.list_folders()
        assert route.called
        assert result == {"items": [], "has_more": False}


def test_folder_api_error_raises():
    with respx.mock(base_url=BASE) as mock:
        mock.get("/folders/bad-id").mock(
            return_value=httpx.Response(404, json={"error": "Folder not found"})
        )
        with pytest.raises(httpx.HTTPStatusError):
            server.get_folder(folder_id="bad-id")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_folders.py -v
```

Expected: all tests FAIL with `AttributeError: module 'server' has no attribute 'create_folder'`.

- [ ] **Step 3: Implement folder tools in `server.py`**

Add after the notes section:

```python
# --- Folders ---

@mcp.tool()
def create_folder(title: str, parent_id: str = "") -> dict:
    """Create a new folder (notebook) in Joplin."""
    payload = {"title": title}
    if parent_id:
        payload["parent_id"] = parent_id
    resp = _get_client().post("/folders", json=payload)
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def get_folder(folder_id: str) -> dict:
    """Retrieve a folder by ID."""
    resp = _get_client().get(f"/folders/{folder_id}")
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def update_folder(folder_id: str, title: str = "") -> dict:
    """Rename a folder."""
    payload = {}
    if title:
        payload["title"] = title
    resp = _get_client().put(f"/folders/{folder_id}", json=payload)
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def delete_folder(folder_id: str) -> dict:
    """Delete a folder by ID."""
    resp = _get_client().delete(f"/folders/{folder_id}")
    resp.raise_for_status()
    return {"success": True}


@mcp.tool()
def list_folders(page: int = 1, limit: int = 100) -> dict:
    """List all folders."""
    resp = _get_client().get("/folders", params={"page": page, "limit": limit})
    resp.raise_for_status()
    return resp.json()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_folders.py -v
```

Expected: all 8 tests PASS.

- [ ] **Step 5: Run full test suite to check for regressions**

```bash
pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add server.py tests/test_folders.py
git commit -m "feat: add folder tools (create, get, update, delete, list)"
```

---

## Task 6: Tags tools

**Files:**
- Modify: `server.py`
- Create: `tests/test_tags.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_tags.py`:

```python
import json
import pytest
import httpx
import respx

import server

BASE = "http://host.containers.internal:41184"


def test_create_tag_sends_title():
    with respx.mock(base_url=BASE) as mock:
        route = mock.post("/tags").mock(
            return_value=httpx.Response(200, json={"id": "tag-1", "title": "urgent"})
        )
        result = server.create_tag(title="urgent")
        body = json.loads(route.calls[0].request.content)
        assert body["title"] == "urgent"
        assert result["id"] == "tag-1"


def test_get_tag_calls_correct_endpoint():
    with respx.mock(base_url=BASE) as mock:
        route = mock.get("/tags/tag-1").mock(
            return_value=httpx.Response(200, json={"id": "tag-1", "title": "urgent"})
        )
        result = server.get_tag(tag_id="tag-1")
        assert route.called
        assert result["id"] == "tag-1"


def test_update_tag_sends_title():
    with respx.mock(base_url=BASE) as mock:
        route = mock.put("/tags/tag-1").mock(
            return_value=httpx.Response(200, json={"id": "tag-1", "title": "critical"})
        )
        server.update_tag(tag_id="tag-1", title="critical")
        body = json.loads(route.calls[0].request.content)
        assert body["title"] == "critical"


def test_update_tag_sends_empty_payload_when_no_title():
    with respx.mock(base_url=BASE) as mock:
        route = mock.put("/tags/tag-1").mock(
            return_value=httpx.Response(200, json={"id": "tag-1"})
        )
        server.update_tag(tag_id="tag-1")
        body = json.loads(route.calls[0].request.content)
        assert body == {}


def test_delete_tag_calls_correct_endpoint():
    with respx.mock(base_url=BASE) as mock:
        route = mock.delete("/tags/tag-1").mock(
            return_value=httpx.Response(204)
        )
        result = server.delete_tag(tag_id="tag-1")
        assert route.called
        assert result == {"success": True}


def test_list_tags_calls_tags_endpoint():
    with respx.mock(base_url=BASE) as mock:
        route = mock.get("/tags").mock(
            return_value=httpx.Response(200, json={"items": [], "has_more": False})
        )
        result = server.list_tags()
        assert route.called
        assert result == {"items": [], "has_more": False}


def test_tag_note_calls_correct_endpoint():
    with respx.mock(base_url=BASE) as mock:
        route = mock.post("/tags/tag-1/notes").mock(
            return_value=httpx.Response(200, json={"id": "note-1"})
        )
        server.tag_note(tag_id="tag-1", note_id="note-1")
        body = json.loads(route.calls[0].request.content)
        assert body["id"] == "note-1"
        assert route.called


def test_untag_note_calls_correct_endpoint():
    with respx.mock(base_url=BASE) as mock:
        route = mock.delete("/tags/tag-1/notes/note-1").mock(
            return_value=httpx.Response(204)
        )
        result = server.untag_note(tag_id="tag-1", note_id="note-1")
        assert route.called
        assert result == {"success": True}


def test_tag_api_error_raises():
    with respx.mock(base_url=BASE) as mock:
        mock.get("/tags/bad-id").mock(
            return_value=httpx.Response(404, json={"error": "Tag not found"})
        )
        with pytest.raises(httpx.HTTPStatusError):
            server.get_tag(tag_id="bad-id")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_tags.py -v
```

Expected: all tests FAIL with `AttributeError: module 'server' has no attribute 'create_tag'`.

- [ ] **Step 3: Implement tag tools in `server.py`**

Add after the folders section:

```python
# --- Tags ---

@mcp.tool()
def create_tag(title: str) -> dict:
    """Create a new tag in Joplin."""
    resp = _get_client().post("/tags", json={"title": title})
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def get_tag(tag_id: str) -> dict:
    """Retrieve a tag by ID."""
    resp = _get_client().get(f"/tags/{tag_id}")
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def update_tag(tag_id: str, title: str = "") -> dict:
    """Rename a tag."""
    payload = {}
    if title:
        payload["title"] = title
    resp = _get_client().put(f"/tags/{tag_id}", json=payload)
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def delete_tag(tag_id: str) -> dict:
    """Delete a tag by ID."""
    resp = _get_client().delete(f"/tags/{tag_id}")
    resp.raise_for_status()
    return {"success": True}


@mcp.tool()
def list_tags(page: int = 1, limit: int = 100) -> dict:
    """List all tags."""
    resp = _get_client().get("/tags", params={"page": page, "limit": limit})
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def tag_note(tag_id: str, note_id: str) -> dict:
    """Attach a tag to a note."""
    resp = _get_client().post(f"/tags/{tag_id}/notes", json={"id": note_id})
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def untag_note(tag_id: str, note_id: str) -> dict:
    """Remove a tag from a note."""
    resp = _get_client().delete(f"/tags/{tag_id}/notes/{note_id}")
    resp.raise_for_status()
    return {"success": True}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_tags.py -v
```

Expected: all 9 tests PASS.

- [ ] **Step 5: Run full test suite to check for regressions**

```bash
pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add server.py tests/test_tags.py
git commit -m "feat: add tag tools (create, get, update, delete, list, tag_note, untag_note)"
```

---

## Task 7: Search tool

**Files:**
- Modify: `server.py`
- Create: `tests/test_search.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_search.py`:

```python
import pytest
import httpx
import respx

import server

BASE = "http://host.containers.internal:41184"


def test_search_sends_query():
    with respx.mock(base_url=BASE) as mock:
        route = mock.get("/search").mock(
            return_value=httpx.Response(200, json={"items": [], "has_more": False})
        )
        result = server.search(query="meeting notes")
        assert route.called
        url = str(route.calls[0].request.url)
        assert "query=meeting+notes" in url or "query=meeting%20notes" in url
        assert result == {"items": [], "has_more": False}


def test_search_sends_default_type_note():
    with respx.mock(base_url=BASE) as mock:
        route = mock.get("/search").mock(
            return_value=httpx.Response(200, json={"items": []})
        )
        server.search(query="test")
        url = str(route.calls[0].request.url)
        assert "type=note" in url


def test_search_sends_custom_type():
    with respx.mock(base_url=BASE) as mock:
        route = mock.get("/search").mock(
            return_value=httpx.Response(200, json={"items": []})
        )
        server.search(query="test", type="folder")
        url = str(route.calls[0].request.url)
        assert "type=folder" in url


def test_search_sends_pagination_params():
    with respx.mock(base_url=BASE) as mock:
        route = mock.get("/search").mock(
            return_value=httpx.Response(200, json={"items": []})
        )
        server.search(query="test", page=2, limit=10)
        url = str(route.calls[0].request.url)
        assert "page=2" in url
        assert "limit=10" in url


def test_search_api_error_raises():
    with respx.mock(base_url=BASE) as mock:
        mock.get("/search").mock(
            return_value=httpx.Response(400, json={"error": "Invalid query"})
        )
        with pytest.raises(httpx.HTTPStatusError):
            server.search(query="")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_search.py -v
```

Expected: all tests FAIL with `AttributeError: module 'server' has no attribute 'search'`.

- [ ] **Step 3: Implement search tool in `server.py`**

Add after the tags section:

```python
# --- Search ---

@mcp.tool()
def search(query: str, type: str = "note", page: int = 1, limit: int = 100) -> dict:
    """Full-text search across Joplin. type can be: note, folder, tag, resource."""
    resp = _get_client().get(
        "/search",
        params={"query": query, "type": type, "page": page, "limit": limit},
    )
    resp.raise_for_status()
    return resp.json()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_search.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Run full test suite to check for regressions**

```bash
pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add server.py tests/test_search.py
git commit -m "feat: add search tool"
```

---

## Task 8: Resources tools

**Files:**
- Modify: `server.py`
- Create: `tests/test_resources.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_resources.py`:

```python
import pytest
import httpx
import respx

import server

BASE = "http://host.containers.internal:41184"


def test_list_resources_calls_resources_endpoint():
    with respx.mock(base_url=BASE) as mock:
        route = mock.get("/resources").mock(
            return_value=httpx.Response(200, json={"items": [], "has_more": False})
        )
        result = server.list_resources()
        assert route.called
        assert result == {"items": [], "has_more": False}


def test_list_resources_sends_pagination_params():
    with respx.mock(base_url=BASE) as mock:
        route = mock.get("/resources").mock(
            return_value=httpx.Response(200, json={"items": []})
        )
        server.list_resources(page=3, limit=20)
        url = str(route.calls[0].request.url)
        assert "page=3" in url
        assert "limit=20" in url


def test_get_resource_calls_correct_endpoint():
    with respx.mock(base_url=BASE) as mock:
        route = mock.get("/resources/res-1").mock(
            return_value=httpx.Response(200, json={"id": "res-1", "title": "photo.jpg"})
        )
        result = server.get_resource(resource_id="res-1")
        assert route.called
        assert result["id"] == "res-1"


def test_resources_api_error_raises():
    with respx.mock(base_url=BASE) as mock:
        mock.get("/resources/bad-id").mock(
            return_value=httpx.Response(404, json={"error": "Resource not found"})
        )
        with pytest.raises(httpx.HTTPStatusError):
            server.get_resource(resource_id="bad-id")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_resources.py -v
```

Expected: all tests FAIL with `AttributeError: module 'server' has no attribute 'list_resources'`.

- [ ] **Step 3: Implement resources tools in `server.py`**

Add after the search section:

```python
# --- Resources ---

@mcp.tool()
def list_resources(page: int = 1, limit: int = 100) -> dict:
    """List all resources (attachments)."""
    resp = _get_client().get("/resources", params={"page": page, "limit": limit})
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def get_resource(resource_id: str) -> dict:
    """Retrieve resource metadata by ID."""
    resp = _get_client().get(f"/resources/{resource_id}")
    resp.raise_for_status()
    return resp.json()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_resources.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Run full test suite**

```bash
pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add server.py tests/test_resources.py
git commit -m "feat: add resource tools (list, get)"
```

---

## Task 9: Containerfile + image build

**Files:**
- Create: `Containerfile`

- [ ] **Step 1: Create `Containerfile`**

```dockerfile
FROM python:3.13-alpine

RUN adduser -D appuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

USER appuser

ENTRYPOINT ["python", "server.py"]
```

Note: Alpine uses `adduser -D` (not `useradd`) to create a system user without a password.

- [ ] **Step 2: Build the image**

```bash
podman build -t joplin-mcp-server .
```

Expected: image builds successfully. If pip fails with a compilation error on any package, replace `FROM python:3.13-alpine` with `FROM python:3.13-slim` and rebuild.

- [ ] **Step 3: Verify the image runs and exposes tools**

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0"}}}' \
  | podman run --rm -i \
      -e JOPLIN_TOKEN=test \
      joplin-mcp-server
```

Expected: JSON response with `"result"` containing server capabilities. The process then waits for further input — interrupt with Ctrl-C.

Note: `-e JOPLIN_TOKEN=test` is used here for smoke testing only. Production use passes the token via Podman secret (Task 11).

- [ ] **Step 4: Verify image size**

```bash
podman image inspect joplin-mcp-server --format "{{.Size}}" | numfmt --to=iec
```

Expected: ~100-150MB for Alpine, ~250-300MB for slim. Alpine is preferred if the build succeeded.

- [ ] **Step 5: Commit**

```bash
git add Containerfile
git commit -m "feat: add Containerfile for Podman (Alpine base)"
```

---

## Task 10: Integration test script

**Files:**
- Create: `tests/integration.py`

- [ ] **Step 1: Create `tests/integration.py`**

```python
#!/usr/bin/env python3
"""
Manual integration test — requires Joplin running at localhost:41184.

Usage:
    JOPLIN_TOKEN=<your-token> python tests/integration.py

This is NOT run in CI. Run it manually to verify end-to-end connectivity.
"""
import os
import sys

# Allow importing server from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import server

token = os.getenv("JOPLIN_TOKEN")
if not token:
    print("ERROR: JOPLIN_TOKEN env var is required")
    sys.exit(1)

print("=== Joplin MCP Server Integration Test ===\n")

# 1. List folders
print("1. Listing folders...")
folders = server.list_folders()
print(f"   Found {len(folders.get('items', []))} folder(s)")

# 2. Create a test folder
print("2. Creating test folder...")
folder = server.create_folder(title="MCP Integration Test")
folder_id = folder["id"]
print(f"   Created folder: {folder_id}")

# 3. Create a test note in that folder
print("3. Creating test note...")
note = server.create_note(
    title="Integration Test Note",
    body="Created by integration test",
    parent_id=folder_id,
)
note_id = note["id"]
print(f"   Created note: {note_id}")

# 4. Get the note back
print("4. Retrieving note...")
fetched = server.get_note(note_id=note_id)
assert fetched["title"] == "Integration Test Note", f"Unexpected title: {fetched['title']}"
print("   Title matches.")

# 5. Update the note
print("5. Updating note...")
server.update_note(note_id=note_id, title="Updated Integration Test Note")
updated = server.get_note(note_id=note_id)
assert updated["title"] == "Updated Integration Test Note"
print("   Update confirmed.")

# 6. Create and apply a tag
print("6. Creating and applying tag...")
tag = server.create_tag(title="integration-test")
tag_id = tag["id"]
server.tag_note(tag_id=tag_id, note_id=note_id)
print(f"   Tag {tag_id} applied to note.")

# 7. Search
print("7. Searching...")
results = server.search(query="Integration Test Note")
assert any(r["id"] == note_id for r in results.get("items", [])), "Note not found in search"
print("   Search found the note.")

# 8. Cleanup
print("8. Cleaning up...")
server.untag_note(tag_id=tag_id, note_id=note_id)
server.delete_tag(tag_id=tag_id)
server.delete_note(note_id=note_id)
server.delete_folder(folder_id=folder_id)
print("   Cleanup complete.")

print("\n=== All integration tests passed ===")
```

- [ ] **Step 2: Run the integration test against live Joplin**

Ensure Joplin is running with the Web Clipper enabled (Tools → Options → Web Clipper), then:

```bash
JOPLIN_TOKEN=<your-actual-token> python tests/integration.py
```

Expected:
```
=== Joplin MCP Server Integration Test ===

1. Listing folders...
   Found N folder(s)
2. Creating test folder...
   Created folder: <id>
...
=== All integration tests passed ===
```

- [ ] **Step 3: Commit**

```bash
git add tests/integration.py
git commit -m "test: add manual integration test script"
```

---

## Task 11: Claude Code MCP configuration

**Files:**
- Create: `~/.claude/settings.json` (or update if it exists)

- [ ] **Step 1: Create the Podman secret (one-time setup)**

```bash
echo -n "<your-joplin-token>" | podman secret create joplin_token -
```

Verify:
```bash
podman secret ls
```

Expected output includes `joplin_token` in the list.

- [ ] **Step 2: Add the MCP server to Claude Code configuration**

Check if `~/.claude/settings.json` already exists:

```bash
cat ~/.claude/settings.json 2>/dev/null || echo "FILE NOT FOUND"
```

If the file does not exist, create it:

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

If the file already exists, add only the `"joplin"` entry inside the existing `"mcpServers"` object (do not replace the whole file).

- [ ] **Step 3: Verify Claude Code detects the server**

Start a new Claude Code session and run:

```
/mcp
```

Expected: `joplin` appears in the list of connected MCP servers with its tools visible.

- [ ] **Step 4: Smoke test with natural language**

In Claude Code, ask:

```
List my Joplin notebooks
```

Expected: Claude Code calls `list_folders` and returns your actual notebook list.

- [ ] **Step 5: Commit project state**

```bash
git status
git add .
git commit -m "docs: finalize project — all tools implemented and configured"
```
