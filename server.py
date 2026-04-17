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
    token = os.getenv("JOPLIN_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Joplin API token not found in secret or JOPLIN_TOKEN env var")
    return token


def _get_client() -> httpx.Client:
    global _client
    if _client is None:
        token = _load_token()
        # Sync client is intentional: this server handles a single stdio client with no
        # concurrent requests. Token is passed as a query param because the Joplin API
        # only supports token-as-query-param authentication; this is unavoidable.
        _client = httpx.Client(base_url=_BASE_URL, params={"token": token})
    return _client


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


if __name__ == "__main__":
    mcp.run()
