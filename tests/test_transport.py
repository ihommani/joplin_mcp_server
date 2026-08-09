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


def test_transport_config_defaults_to_stdio(monkeypatch):
    monkeypatch.delenv("MCP_TRANSPORT", raising=False)
    assert server._transport_config() == ("stdio", {})


def test_transport_config_http_reads_port(monkeypatch):
    monkeypatch.setenv("MCP_TRANSPORT", "http")
    monkeypatch.setenv("MCP_HTTP_PORT", "9000")
    assert server._transport_config() == (
        "streamable-http",
        {"host": "127.0.0.1", "port": 9000},
    )


def test_transport_config_http_defaults_port(monkeypatch):
    monkeypatch.setenv("MCP_TRANSPORT", "http")
    monkeypatch.delenv("MCP_HTTP_PORT", raising=False)
    assert server._transport_config() == (
        "streamable-http",
        {"host": "127.0.0.1", "port": 8080},
    )


def test_transport_config_rejects_unknown_transport(monkeypatch):
    monkeypatch.setenv("MCP_TRANSPORT", "carrier-pigeon")
    with pytest.raises(RuntimeError, match="carrier-pigeon"):
        server._transport_config()
