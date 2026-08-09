import pytest
import httpx
import respx

import server


def test_sync_without_trigger_url_raises(monkeypatch):
    monkeypatch.delenv("JOPLIN_SYNC_TRIGGER_URL", raising=False)
    with pytest.raises(RuntimeError, match="JOPLIN_SYNC_TRIGGER_URL"):
        server.sync()


def test_sync_posts_to_trigger_url(monkeypatch):
    monkeypatch.setenv("JOPLIN_SYNC_TRIGGER_URL", "http://localhost:41185/sync")
    with respx.mock as mock:
        route = mock.post("http://localhost:41185/sync").mock(
            return_value=httpx.Response(200, text="sync complete")
        )
        result = server.sync()
        assert route.called
        assert result == "sync complete"


def test_sync_reports_already_in_progress(monkeypatch):
    monkeypatch.setenv("JOPLIN_SYNC_TRIGGER_URL", "http://localhost:41185/sync")
    with respx.mock as mock:
        mock.post("http://localhost:41185/sync").mock(
            return_value=httpx.Response(409, text="sync already in progress")
        )
        assert server.sync() == "sync already in progress"
