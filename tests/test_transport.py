import pytest

import server


def test_load_token_reads_joplin_api_token(monkeypatch):
    monkeypatch.setattr(server.Path, "exists", lambda self: False)
    monkeypatch.setenv("JOPLIN_API_TOKEN", "from-hermes-infra")
    assert server._load_token() == "from-hermes-infra"


def test_load_token_ignores_the_retired_joplin_token(monkeypatch):
    monkeypatch.setattr(server.Path, "exists", lambda self: False)
    monkeypatch.delenv("JOPLIN_API_TOKEN", raising=False)
    monkeypatch.setenv("JOPLIN_TOKEN", "retired-name")
    with pytest.raises(RuntimeError, match="JOPLIN_API_TOKEN"):
        server._load_token()
