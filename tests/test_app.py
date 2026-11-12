from fastapi.testclient import TestClient

from app.main import create_app


def test_crud_validation_and_app_isolation():
    with TestClient(create_app()) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert client.post("/api/tasks", json={"title": " "}).status_code == 422
        response = client.post("/api/tasks", json={"title": "Learn routing"})
        assert response.status_code == 201
        identifier = response.json()["id"]
        assert len(client.get("/api/tasks").json()) == 1
        assert client.get(f"/api/tasks/{identifier}").json()["title"] == "Learn routing"
        assert client.patch(f"/api/tasks/{identifier}", json={"completed": True}).json()[
            "completed"
        ]
        assert client.patch(f"/api/tasks/{identifier}", json={"title": None}).status_code == 422
        assert client.delete(f"/api/tasks/{identifier}").status_code == 204
        assert client.get(f"/api/tasks/{identifier}").status_code == 404
        assert client.get("/openapi.json").status_code == 200
    with TestClient(create_app()) as client:
        assert client.get("/api/tasks").json() == []
