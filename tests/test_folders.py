import json
import pytest
import httpx
import respx

import server

BASE = "http://host.containers.internal:41184"


def test_create_folder_sends_title():
    with respx.mock(base_url=BASE) as mock:
        route = mock.post("/folders").mock(
            return_value=httpx.Response(200, json={"id": "folder-1", "title": "Work"})
        )
        result = server.create_folder(title="Work")
        body = json.loads(route.calls[0].request.content)
        assert body["title"] == "Work"
        assert "parent_id" not in body
        assert result["id"] == "folder-1"


def test_create_folder_includes_parent_id_when_provided():
    with respx.mock(base_url=BASE) as mock:
        route = mock.post("/folders").mock(
            return_value=httpx.Response(200, json={"id": "folder-2", "title": "Sub"})
        )
        server.create_folder(title="Sub", parent_id="folder-1")
        body = json.loads(route.calls[0].request.content)
        assert body["parent_id"] == "folder-1"


def test_get_folder_calls_correct_endpoint():
    with respx.mock(base_url=BASE) as mock:
        route = mock.get("/folders/folder-1").mock(
            return_value=httpx.Response(200, json={"id": "folder-1", "title": "Work"})
        )
        result = server.get_folder(folder_id="folder-1")
        assert route.called
        assert result["id"] == "folder-1"


def test_update_folder_sends_title():
    with respx.mock(base_url=BASE) as mock:
        route = mock.put("/folders/folder-1").mock(
            return_value=httpx.Response(200, json={"id": "folder-1", "title": "Personal"})
        )
        server.update_folder(folder_id="folder-1", title="Personal")
        body = json.loads(route.calls[0].request.content)
        assert body["title"] == "Personal"


def test_update_folder_sends_empty_payload_when_no_title():
    with respx.mock(base_url=BASE) as mock:
        route = mock.put("/folders/folder-1").mock(
            return_value=httpx.Response(200, json={"id": "folder-1"})
        )
        server.update_folder(folder_id="folder-1")
        body = json.loads(route.calls[0].request.content)
        assert body == {}


def test_delete_folder_calls_correct_endpoint():
    with respx.mock(base_url=BASE) as mock:
        route = mock.delete("/folders/folder-1").mock(
            return_value=httpx.Response(204)
        )
        result = server.delete_folder(folder_id="folder-1")
        assert route.called
        assert result == {"success": True}


def test_list_folders_calls_folders_endpoint():
    with respx.mock(base_url=BASE) as mock:
        route = mock.get("/folders").mock(
            return_value=httpx.Response(200, json={"items": [], "has_more": False})
        )
        result = server.list_folders()
        assert route.called
        assert result == {"items": [], "has_more": False}


def test_list_folders_sends_pagination_params():
    with respx.mock(base_url=BASE) as mock:
        route = mock.get("/folders").mock(
            return_value=httpx.Response(200, json={"items": []})
        )
        server.list_folders(page=2, limit=50)
        url = str(route.calls[0].request.url)
        assert "page=2" in url
        assert "limit=50" in url


def test_folder_api_error_raises():
    with respx.mock(base_url=BASE) as mock:
        mock.get("/folders/bad-id").mock(
            return_value=httpx.Response(404, json={"error": "Folder not found"})
        )
        with pytest.raises(httpx.HTTPStatusError):
            server.get_folder(folder_id="bad-id")
