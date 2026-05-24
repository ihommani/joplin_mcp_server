import pytest
import httpx
import respx

import server

BASE = "http://localhost:41184"


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
