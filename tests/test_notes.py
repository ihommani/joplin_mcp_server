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


def test_list_notes_sends_pagination_params():
    with respx.mock(base_url=BASE) as mock:
        route = mock.get("/notes").mock(
            return_value=httpx.Response(200, json={"items": [], "has_more": False})
        )
        server.list_notes(page=2, limit=50)
        url = str(route.calls[0].request.url)
        assert "page=2" in url
        assert "limit=50" in url


def test_note_api_error_raises():
    with respx.mock(base_url=BASE) as mock:
        mock.get("/notes/bad-id").mock(
            return_value=httpx.Response(404, json={"error": "Note not found"})
        )
        with pytest.raises(httpx.HTTPStatusError):
            server.get_note(note_id="bad-id")
