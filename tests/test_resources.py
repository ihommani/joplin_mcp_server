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
