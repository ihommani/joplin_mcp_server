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


if __name__ == "__main__":
    mcp.run()
