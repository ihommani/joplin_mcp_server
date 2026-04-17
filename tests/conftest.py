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
