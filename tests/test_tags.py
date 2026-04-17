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


def test_list_tags_sends_pagination_params():
    with respx.mock(base_url=BASE) as mock:
        route = mock.get("/tags").mock(
            return_value=httpx.Response(200, json={"items": []})
        )
        server.list_tags(page=2, limit=50)
        url = str(route.calls[0].request.url)
        assert "page=2" in url
        assert "limit=50" in url


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


def test_tag_note_api_error_raises():
    with respx.mock(base_url=BASE) as mock:
        mock.post("/tags/tag-1/notes").mock(
            return_value=httpx.Response(404, json={"error": "Tag not found"})
        )
        with pytest.raises(httpx.HTTPStatusError):
            server.tag_note(tag_id="tag-1", note_id="note-1")


def test_tag_api_error_raises():
    with respx.mock(base_url=BASE) as mock:
        mock.get("/tags/bad-id").mock(
            return_value=httpx.Response(404, json={"error": "Tag not found"})
        )
        with pytest.raises(httpx.HTTPStatusError):
            server.get_tag(tag_id="bad-id")
