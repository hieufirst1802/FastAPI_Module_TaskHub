import pytest


def test_create_task(task):
    assert task["title"] == "Learn routing"
    assert task["description"] == ""
    assert task["status"] == "TODO"
    assert task["owner_id"] > 0


def test_create_rejects_blank_title(client, tasks_url):
    assert client.post(tasks_url, json={"title": " "}).status_code == 422


def test_get_task(client, task, tasks_url):
    response = client.get(f"{tasks_url}/{task['id']}")
    assert response.status_code == 200
    assert response.json() == task


def test_update_task(client, task, tasks_url):
    url = f"{tasks_url}/{task['id']}"
    for status in ("IN_PROGRESS", "DONE"):
        response = client.patch(url, json={"status": status})
        assert response.status_code == 200
        assert response.json() == {**task, "status": status}


@pytest.mark.parametrize("payload", [{"title": None}, {"status": "INVALID"}])
def test_update_rejects_invalid_fields(client, task, payload, tasks_url):
    assert client.patch(f"{tasks_url}/{task['id']}", json=payload).status_code == 422


def test_delete_task(client, task, tasks_url):
    url = f"{tasks_url}/{task['id']}"
    assert client.delete(url).status_code == 204
    assert client.get(url).status_code == 404


@pytest.mark.parametrize("method", ["GET", "PATCH", "DELETE"])
def test_missing_task(client, method, tasks_url):
    response = client.request(method, f"{tasks_url}/999", json={} if method == "PATCH" else None)
    assert response.status_code == 404
    assert response.json() == {"error": {"code": "not_found", "message": "Task not found"}}


@pytest.mark.parametrize("method", ["GET", "PATCH", "DELETE"])
def test_task_id_must_be_positive(client, method, tasks_url):
    response = client.request(method, f"{tasks_url}/0", json={} if method == "PATCH" else None)
    assert response.status_code == 422
