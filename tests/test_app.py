import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client():
    with TestClient(create_app()) as test_client:
        yield test_client


def create_task(client: TestClient, title: str = "Learn FastAPI") -> dict:
    response = client.post("/api/tasks", json={"title": title})
    assert response.status_code == 201
    return response.json()


def test_health(client: TestClient):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_task(client: TestClient):
    task = create_task(client, "Learn routing")

    assert task["id"] == 1
    assert task["title"] == "Learn routing"
    assert task["completed"] is False


@pytest.mark.parametrize(
    "payload",
    [
        {"title": " "},
        {"title": ""},
        {"title": "x" * 201},
        {"title": "Valid title", "unknown": "value"},
    ],
)
def test_create_task_validation(client: TestClient, payload: dict):
    response = client.post("/api/tasks", json=payload)

    assert response.status_code == 422


def test_list_tasks(client: TestClient):
    create_task(client, "Task 1")
    create_task(client, "Task 2")

    response = client.get("/api/tasks")

    assert response.status_code == 200
    assert len(response.json()["items"]) == 2
    assert response.json()["total"] == 2
    assert response.json()["offset"] == 0
    assert response.json()["limit"] == 20


def test_pagination(client: TestClient):
    for number in range(5):
        create_task(client, f"Task {number}")

    response = client.get("/api/tasks?offset=1&limit=2")

    assert response.status_code == 200
    assert len(response.json()["items"]) == 2
    assert response.json()["total"] == 5
    assert response.json()["offset"] == 1
    assert response.json()["limit"] == 2
    assert response.json()["items"][0]["title"] == "Task 1"
    assert response.json()["items"][1]["title"] == "Task 2"


def test_pagination_empty(client: TestClient):
    response = client.get("/api/tasks")

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["total"] == 0


def test_pagination_offset_beyond_total(client: TestClient):
    for number in range(3):
        create_task(client, f"Task {number}")

    response = client.get("/api/tasks?offset=10&limit=2")

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["total"] == 3


@pytest.mark.parametrize(
    "query",
    [
        "offset=-1",
        "limit=0",
        "limit=101",
    ],
)
def test_pagination_validation(client: TestClient, query: str):
    response = client.get(f"/api/tasks?{query}")

    assert response.status_code == 422


def test_read_task(client: TestClient):
    task = create_task(client, "Read this task")

    response = client.get(f"/api/tasks/{task['id']}")

    assert response.status_code == 200
    assert response.json()["title"] == "Read this task"


def test_read_nonexistent_task(client: TestClient):
    response = client.get("/api/tasks/999")

    assert response.status_code == 404


def test_update_task(client: TestClient):
    task = create_task(client, "Old title")

    response = client.patch(
        f"/api/tasks/{task['id']}",
        json={"title": "New title", "completed": True},
    )

    assert response.status_code == 200
    assert response.json()["title"] == "New title"
    assert response.json()["completed"] is True


def test_update_task_with_empty_payload(client: TestClient):
    task = create_task(client, "Unchanged title")

    response = client.patch(f"/api/tasks/{task['id']}", json={})

    assert response.status_code == 200
    assert response.json()["title"] == "Unchanged title"
    assert response.json()["completed"] is False


@pytest.mark.parametrize(
    "payload",
    [
        {"title": None},
        {"title": ""},
        {"title": "x" * 201},
        {"completed": None},
        {"unknown": "value"},
    ],
)
def test_update_task_validation(client: TestClient, payload: dict):
    task = create_task(client)

    response = client.patch(
        f"/api/tasks/{task['id']}",
        json=payload,
    )

    assert response.status_code == 422


def test_update_nonexistent_task(client: TestClient):
    response = client.patch(
        "/api/tasks/999",
        json={"title": "New title"},
    )

    assert response.status_code == 404


def test_delete_task(client: TestClient):
    task = create_task(client)

    response = client.delete(f"/api/tasks/{task['id']}")

    assert response.status_code == 204
    assert client.get(f"/api/tasks/{task['id']}").status_code == 404


def test_delete_nonexistent_task(client: TestClient):
    response = client.delete("/api/tasks/999")

    assert response.status_code == 404


def test_app_isolation():
    with TestClient(create_app()) as first_client:
        create_task(first_client, "Private task")

    with TestClient(create_app()) as second_client:
        response = second_client.get("/api/tasks")

        assert response.status_code == 200
        assert response.json()["items"] == []
        assert response.json()["total"] == 0


def test_openapi(client: TestClient):
    response = client.get("/openapi.json")

    assert response.status_code == 200
