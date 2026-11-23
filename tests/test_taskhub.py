import asyncio
import hashlib
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.cache import TaskCache
from app.main import create_app
from app.models.refresh_token import RefreshToken
from app.models.user import User


@pytest.fixture
def hub(settings, redis, monkeypatch):
    cache = TaskCache(redis, ttl=10, prefix="test:hub")
    monkeypatch.setattr(TaskCache, "from_settings", classmethod(lambda cls, config: cache))
    with TestClient(create_app(settings)) as client:
        users = {}
        for name in ["owner", "editor", "viewer", "outsider", "admin"]:
            r = client.post(
                "/api/v1/auth/register",
                json={
                    "username": name,
                    "password": "Password123!",
                    "email": f"{name}@example.com",
                    "full_name": name.title(),
                },
            )
            assert r.status_code == 201, r.text
            login = client.post(
                "/api/v1/auth/login", json={"username": name, "password": "Password123!"}
            )
            assert login.status_code == 200, login.text
            users[name] = {
                "id": r.json()["id"],
                "tokens": login.json(),
                "headers": {"Authorization": "Bearer " + login.json()["access_token"]},
            }

        async def promote():
            engine = create_async_engine(settings.database_url)
            async with engine.begin() as conn:
                await conn.execute(
                    update(User).where(User.username == "admin").values(role="admin")
                )
            await engine.dispose()

        asyncio.run(promote())
        yield client, users, settings, redis, cache


def seed(hub):
    c, users, *_ = hub
    h = users["owner"]["headers"]
    w = c.post("/api/v1/workspaces", json={"name": "Team"}, headers=h)
    assert w.status_code == 201, w.text
    wid = w.json()["id"]
    for name, role in [("editor", "EDITOR"), ("viewer", "VIEWER")]:
        r = c.post(
            f"/api/v1/workspaces/{wid}/members",
            json={"user_id": users[name]["id"], "role": role},
            headers=h,
        )
        assert r.status_code == 201, r.text
    p = c.post(f"/api/v1/workspaces/{wid}/projects", json={"name": "Project"}, headers=h)
    assert p.status_code == 201, p.text
    return wid, p.json()["id"]


def test_refresh_rotation_logout_and_token_types(hub):
    c, users, settings, *_ = hub
    original = users["owner"]["tokens"]
    rotated = c.post("/api/v1/auth/refresh", json={"refresh_token": original["refresh_token"]})
    assert rotated.status_code == 200, rotated.text
    assert rotated.json()["refresh_token"] != original["refresh_token"]
    assert (
        c.post(
            "/api/v1/auth/refresh", json={"refresh_token": original["refresh_token"]}
        ).status_code
        == 401
    )
    assert (
        c.get(
            "/api/v1/users/me", headers={"Authorization": "Bearer " + original["refresh_token"]}
        ).status_code
        == 401
    )
    assert (
        c.post("/api/v1/auth/refresh", json={"refresh_token": original["access_token"]}).status_code
        == 401
    )
    fresh = rotated.json()["refresh_token"]
    for _ in range(2):
        assert c.post("/api/v1/auth/logout", json={"refresh_token": fresh}).status_code == 204
    assert c.post("/api/v1/auth/refresh", json={"refresh_token": fresh}).status_code == 401
    assert c.post("/api/v1/auth/refresh", json={"refresh_token": "invalid"}).status_code == 401

    async def persisted():
        engine = create_async_engine(settings.database_url)
        async with async_sessionmaker(engine)() as session:
            row = await session.get(RefreshToken, hashlib.sha256(fresh.encode()).hexdigest())
            assert row is not None and row.revoked
        await engine.dispose()

    asyncio.run(persisted())


def test_refresh_concurrent_one_use(hub):
    c, users, *_ = hub
    token = users["owner"]["tokens"]["refresh_token"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: c.post("/api/v1/auth/refresh", json={"refresh_token": token}).status_code,
                range(2),
            )
        )
    assert sorted(results) == [200, 401]


def test_expired_and_forged_tokens(hub):
    c, users, settings, *_ = hub
    for payload in [
        {
            "sub": str(users["owner"]["id"]),
            "exp": datetime.now(UTC) - timedelta(seconds=1),
            "type": "refresh",
            "jti": "expired",
        },
        {"sub": "bad", "exp": int(time.time()) + 60, "type": "refresh", "jti": "bad"},
    ]:
        token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
        assert c.post("/api/v1/auth/refresh", json={"refresh_token": token}).status_code == 401
    token = jwt.encode(
        {
            "sub": str(users["owner"]["id"]),
            "exp": int(time.time()) + 60,
            "type": "refresh",
            "jti": "unstored",
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    assert c.post("/api/v1/auth/refresh", json={"refresh_token": token}).status_code == 401


def test_profile_password_and_revocation(hub):
    c, users, *_ = hub
    h = users["owner"]["headers"]
    assert (
        c.patch("/api/v1/users/me", json={"full_name": "Updated"}, headers=h).json()["full_name"]
        == "Updated"
    )
    assert (
        c.patch("/api/v1/users/me", json={"full_name": "X", "role": "admin"}, headers=h).status_code
        == 422
    )
    assert (
        c.post(
            "/api/v1/auth/change-password",
            json={"current_password": "Incorrect123!", "new_password": "NewPassword123!"},
            headers=h,
        ).status_code
        == 400
    )
    assert (
        c.post(
            "/api/v1/auth/change-password",
            json={"current_password": "Password123!", "new_password": "NewPassword123!"},
            headers=h,
        ).status_code
        == 204
    )
    assert (
        c.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": users["owner"]["tokens"]["refresh_token"]},
        ).status_code
        == 401
    )
    assert (
        c.post(
            "/api/v1/auth/login", json={"username": "owner", "password": "Password123!"}
        ).status_code
        == 401
    )
    assert (
        c.post(
            "/api/v1/auth/login", json={"username": "owner", "password": "NewPassword123!"}
        ).status_code
        == 200
    )


def test_workspace_rbac_and_owner_invariants(hub):
    c, users, *_ = hub
    wid, pid = seed(hub)
    owner = users["owner"]["headers"]
    for role in ["viewer", "editor"]:
        h = users[role]["headers"]
        assert c.get(f"/api/v1/workspaces/{wid}", headers=h).status_code == 200
        assert (
            c.patch(f"/api/v1/workspaces/{wid}", json={"name": "Hijacked"}, headers=h).status_code
            == 403
        )
        assert (
            c.post(
                f"/api/v1/workspaces/{wid}/members",
                json={"user_id": users["outsider"]["id"]},
                headers=h,
            ).status_code
            == 403
        )
    assert (
        c.get(f"/api/v1/workspaces/{wid}", headers=users["outsider"]["headers"]).status_code == 404
    )
    assert c.get("/api/v1/workspaces", headers=users["outsider"]["headers"]).json()["items"] == []
    assert c.get(f"/api/v1/projects/{pid}", headers=users["admin"]["headers"]).status_code == 200
    assert (
        c.delete(
            f"/api/v1/workspaces/{wid}/members/{users['owner']['id']}", headers=owner
        ).status_code
        == 409
    )
    assert (
        c.patch(
            f"/api/v1/workspaces/{wid}/members/{users['owner']['id']}",
            json={"role": "VIEWER"},
            headers=owner,
        ).status_code
        == 409
    )
    assert (
        c.post(
            f"/api/v1/workspaces/{wid}/members",
            json={"user_id": users["outsider"]["id"], "role": "OWNER"},
            headers=owner,
        ).status_code
        == 422
    )


def test_tasks_filters_cache_and_revoked_membership(hub):
    c, users, _settings, redis, cache = hub
    wid, pid = seed(hub)
    h = users["editor"]["headers"]
    url = f"/api/v1/projects/{pid}/tasks"
    created = c.post(
        url,
        headers=h,
        json={
            "title": "Implement",
            "assignee_id": users["viewer"]["id"],
            "priority": "HIGH",
            "due_date": "2026-12-01T12:00:00Z",
        },
    )
    assert created.status_code == 201, created.text
    tid = created.json()["id"]
    assert created.json()["created_by"] == users["editor"]["id"]
    assert c.get(url + "?status=TODO&priority=HIGH&page=1&limit=1", headers=h).json()["total"] == 1
    assert c.get(url + "?priority=LOW", headers=h).json()["total"] == 0
    assert c.get(url + f"?assignee_id={users['viewer']['id']}", headers=h).json()["total"] == 1
    assert c.get(url + "?page=2&limit=1", headers=h).json()["items"] == []
    assert c.get(url + "?page=0", headers=h).status_code == 422
    assert c.get(url, headers=users["viewer"]["headers"]).json()["total"] == 1
    old_version = redis.values[f"{cache.prefix}:projects:{pid}:version"][0]
    assert (
        c.patch(
            f"/api/v1/tasks/{tid}", json={"status": "DONE", "assignee_id": None}, headers=h
        ).status_code
        == 200
    )
    assert redis.values[f"{cache.prefix}:projects:{pid}:version"][0] != old_version
    assert c.get(url + "?status=TODO", headers=h).json()["total"] == 0
    assert c.get(url + "?status=DONE", headers=h).json()["total"] == 1
    assert (
        c.patch(
            f"/api/v1/tasks/{tid}", json={"title": "No"}, headers=users["viewer"]["headers"]
        ).status_code
        == 403
    )
    assert (
        c.post(
            url, json={"title": "Bad", "assignee_id": users["outsider"]["id"]}, headers=h
        ).status_code
        == 422
    )
    assert (
        c.delete(
            f"/api/v1/workspaces/{wid}/members/{users['editor']['id']}",
            headers=users["owner"]["headers"],
        ).status_code
        == 204
    )
    assert c.get(url, headers=h).status_code == 404
    assert c.patch(f"/api/v1/tasks/{tid}", json={"status": "TODO"}, headers=h).status_code == 404
    assert c.get(f"/api/tasks/{tid}", headers=h).status_code == 404


def test_labels_comments_and_cross_project_isolation(hub):
    c, users, *_ = hub
    wid, pid = seed(hub)
    h = users["owner"]["headers"]
    e = users["editor"]["headers"]
    v = users["viewer"]["headers"]
    tid = c.post(f"/api/v1/projects/{pid}/tasks", json={"title": "Task"}, headers=h).json()["id"]
    label = c.post(
        f"/api/v1/projects/{pid}/labels", json={"name": "Bug", "color": "#ff0000"}, headers=e
    )
    assert label.status_code == 201
    lid = label.json()["id"]
    assert (
        c.post(f"/api/v1/projects/{pid}/labels", json={"name": "Bug"}, headers=e).status_code == 409
    )
    assert c.post(f"/api/v1/tasks/{tid}/labels/{lid}", headers=v).status_code == 403
    for _ in range(2):
        assert c.post(f"/api/v1/tasks/{tid}/labels/{lid}", headers=e).status_code == 204
    assert len(c.get(f"/api/v1/tasks/{tid}/labels", headers=v).json()) == 1
    p2 = c.post(f"/api/v1/workspaces/{wid}/projects", json={"name": "Second"}, headers=h).json()[
        "id"
    ]
    l2 = c.post(f"/api/v1/projects/{p2}/labels", json={"name": "Other"}, headers=h).json()["id"]
    assert c.post(f"/api/v1/tasks/{tid}/labels/{l2}", headers=h).status_code == 422
    comment = c.post(f"/api/v1/tasks/{tid}/comments", json={"content": "Comment"}, headers=h)
    assert comment.status_code == 201
    cid = comment.json()["id"]
    assert (
        c.post(f"/api/v1/tasks/{tid}/comments", json={"content": "No"}, headers=v).status_code
        == 403
    )
    assert c.delete(f"/api/v1/comments/{cid}", headers=e).status_code == 403
    assert len(c.get(f"/api/v1/tasks/{tid}/comments", headers=v).json()["items"]) == 1
    assert c.delete(f"/api/v1/comments/{cid}", headers=h).status_code == 204
    assert (
        c.patch(
            f"/api/v1/labels/{lid}", json={"name": "Issue", "color": "#123456"}, headers=e
        ).status_code
        == 200
    )
    assert c.delete(f"/api/v1/labels/{lid}", headers=e).status_code == 204
    assert c.get(f"/api/v1/tasks/{tid}/labels", headers=h).json() == []


def test_archive_delete_cascade_and_legacy_guard(hub):
    c, users, *_ = hub
    wid, pid = seed(hub)
    h = users["owner"]["headers"]
    url = f"/api/v1/projects/{pid}/tasks"
    tid = c.post(url, json={"title": "Task"}, headers=h).json()["id"]
    c.post(f"/api/v1/tasks/{tid}/comments", json={"content": "Delete with task"}, headers=h)
    # Warm legacy detail cache, then downgrade creator to VIEWER.
    assert c.get(f"/api/tasks/{tid}", headers=h).status_code == 200
    assert (
        c.patch(f"/api/v1/projects/{pid}", json={"status": "ARCHIVED"}, headers=h).status_code
        == 200
    )
    assert c.post(url, json={"title": "No"}, headers=h).status_code == 409
    assert c.patch(f"/api/tasks/{tid}", json={"completed": True}, headers=h).status_code == 409
    assert c.get(url, headers=h).status_code == 200
    assert (
        c.patch(f"/api/v1/projects/{pid}", json={"status": "ACTIVE"}, headers=h).status_code == 200
    )
    assert c.delete(f"/api/v1/workspaces/{wid}", headers=h).status_code == 204
    assert c.get(f"/api/v1/tasks/{tid}", headers=h).status_code == 404
    assert c.get(f"/api/tasks/{tid}", headers=h).status_code == 404
    assert c.get(f"/api/v1/projects/{pid}", headers=h).status_code == 404


def test_anonymous_and_openapi(hub):
    c, *_ = hub
    assert c.get("/api/v1/workspaces").status_code == 401
    schema = c.get("/openapi.json").json()
    paths = schema["paths"]
    bearer = schema["components"]["securitySchemes"]["HTTPBearer"]
    assert (bearer["type"], bearer["scheme"], bearer["bearerFormat"]) == ("http", "bearer", "JWT")
    assert "security" not in paths["/api/v1/auth/login"]["post"]
    assert "security" not in paths["/api/v1/auth/refresh"]["post"]
    for methods in paths.values():
        for operation in methods.values():
            assert operation["tags"] and operation["summary"] and operation["description"]

    operation = paths["/api/v1/projects/{pid}/tasks"]["get"]
    assert operation["security"] == [{"HTTPBearer": []}]
    assert {"search", "status", "priority", "assignee_id", "page", "limit"} <= {
        parameter["name"] for parameter in operation["parameters"]
    }
    errors = operation["responses"]
    assert {"401", "404", "422", "500"} <= errors.keys()
    assert "WWW-Authenticate" in errors["401"]["headers"]
    for code, model in (("401", "ErrorResponse"), ("422", "ValidationErrorResponse")):
        assert errors[code]["content"]["application/json"]["schema"]["$ref"].endswith(f"/{model}")
    assert "content" not in paths["/api/v1/tasks/{tid}"]["delete"]["responses"]["204"]


def test_downgrade_blocks_legacy_writes_and_unassigns_removed_member(hub):
    c, users, *_ = hub
    wid, pid = seed(hub)
    h = users["owner"]["headers"]
    e = users["editor"]["headers"]
    tid = c.post(
        f"/api/v1/projects/{pid}/tasks",
        json={"title": "By editor", "assignee_id": users["editor"]["id"]},
        headers=e,
    ).json()["id"]
    assert c.get(f"/api/tasks/{tid}", headers=e).status_code == 200
    assert (
        c.patch(
            f"/api/v1/workspaces/{wid}/members/{users['editor']['id']}",
            json={"role": "VIEWER"},
            headers=h,
        ).status_code
        == 200
    )
    assert c.patch(f"/api/tasks/{tid}", json={"title": "Bypass"}, headers=e).status_code == 403
    assert c.delete(f"/api/tasks/{tid}", headers=e).status_code == 403
    assert (
        c.delete(f"/api/v1/workspaces/{wid}/members/{users['editor']['id']}", headers=h).status_code
        == 204
    )
    assert c.get(f"/api/v1/tasks/{tid}", headers=h).json()["assignee_id"] is None
    assert (
        c.get(f"/api/v1/projects/{pid}/tasks", headers=h).json()["items"][0]["assignee_id"] is None
    )
    assert c.get(f"/api/tasks/{tid}", headers=e).status_code == 404


def test_inactive_user_and_unique_email(hub):
    c, users, settings, *_ = hub
    assert (
        c.patch(
            "/api/v1/users/me",
            json={"email": "editor@example.com"},
            headers=users["owner"]["headers"],
        ).status_code
        == 409
    )
    assert (
        c.patch(
            "/api/v1/users/me", json={"email": "new@example.com"}, headers=users["owner"]["headers"]
        ).status_code
        == 200
    )
    duplicate = c.post(
        "/api/v1/auth/register",
        json={"username": "another", "password": "Password123!", "email": "new@example.com"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "email_already_exists"

    async def deactivate():
        engine = create_async_engine(settings.database_url)
        async with engine.begin() as conn:
            await conn.execute(
                update(User).where(User.id == users["owner"]["id"]).values(is_active=False)
            )
        await engine.dispose()

    asyncio.run(deactivate())
    assert c.get("/api/v1/users/me", headers=users["owner"]["headers"]).status_code == 401
    assert (
        c.post(
            "/api/v1/auth/login", json={"username": "owner", "password": "Password123!"}
        ).status_code
        == 401
    )
    assert (
        c.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": users["owner"]["tokens"]["refresh_token"]},
        ).status_code
        == 401
    )


def test_project_list_cache_hit_expiration_and_delete(hub, monkeypatch):
    from app.models.task import Task
    from app.repositories.workspace import DomainRepository

    c, users, _settings, redis, cache = hub
    _wid, pid = seed(hub)
    h = users["owner"]["headers"]
    tid = c.post(f"/api/v1/projects/{pid}/tasks", json={"title": "Cached"}, headers=h).json()["id"]
    calls = []
    original = DomainRepository.page

    async def counted(self, *args):
        if self.model is Task:
            calls.append(1)
        return await original(self, *args)

    monkeypatch.setattr(DomainRepository, "page", counted)
    url = f"/api/v1/projects/{pid}/tasks"
    for _ in range(2):
        assert c.get(url, headers=h).json()["total"] == 1
    assert len(calls) == 1
    redis.now += cache.ttl
    assert c.get(url, headers=h).json()["total"] == 1
    assert len(calls) == 2
    assert c.delete(f"/api/v1/tasks/{tid}", headers=h).status_code == 204
    assert c.get(url, headers=h).json()["total"] == 0
    assert len(calls) == 3
    assert c.delete(f"/api/v1/projects/{pid}", headers=h).status_code == 204
    assert c.get(url, headers=h).status_code == 404


def test_project_task_search_combines_filters_and_pagination(hub):
    c, users, *_ = hub
    _, pid = seed(hub)
    headers = users["owner"]["headers"]
    url = f"/api/v1/projects/{pid}/tasks"
    ids = []
    for title, description, priority in (
        ("Release 100%_ready", "", "HIGH"),
        ("Checklist", "release 100%_READY", "HIGH"),
        ("Release 100XXready", "", "HIGH"),
        ("Release 100%_ready", "", "LOW"),
    ):
        response = c.post(
            url,
            headers=headers,
            json={"title": title, "description": description, "priority": priority},
        )
        assert response.status_code == 201, response.text
        ids.append(response.json()["id"])

    params = {"search": "  100%_ReAdY  ", "priority": "HIGH", "status": "TODO", "limit": 1}
    for page, identifier in enumerate(ids[:2], start=1):
        result = c.get(url, headers=headers, params={**params, "page": page}).json()
        assert result["total"] == 2
        assert result["page"] == page
        assert [item["id"] for item in result["items"]] == [identifier]
    assert c.get(url, headers=headers, params={**params, "search": "check"}).json()["total"] == 1
    assert c.get(url, headers=headers, params=params).json()["total"] == 2
    for invalid in (
        {"search": "x" * 201},
        {"status": "UNKNOWN"},
        {"priority": "UNKNOWN"},
        {"unknown": "value"},
    ):
        assert c.get(url, headers=headers, params=invalid).status_code == 422

    response = c.patch(f"/api/v1/tasks/{ids[0]}", headers=headers, json={"status": "DONE"})
    assert response.status_code == 200, response.text
    assert c.get(url, headers=headers, params=params).json()["total"] == 1


def test_standalone_task_search_cache_scope_and_invalidation(hub, monkeypatch):
    from app.repositories.task import TaskRepository

    c, users, *_ = hub
    owner = users["owner"]["headers"]
    viewer = users["viewer"]["headers"]
    admin = users["admin"]["headers"]
    url = "/api/tasks"
    params = {"search": "audit", "completed": False, "offset": 0, "limit": 1}
    calls = []
    original = TaskRepository.page

    async def counted(self, *args):
        calls.append(1)
        return await original(self, *args)

    monkeypatch.setattr(TaskRepository, "page", counted)

    def total(headers):
        response = c.get(url, headers=headers, params=params)
        assert response.status_code == 200, response.text
        return response.json()["total"]

    assert total(owner) == 0
    assert total(viewer) == 0
    assert total(admin) == 0
    created = c.post(url, headers=owner, json={"title": "Audit"})
    assert created.status_code == 201, created.text
    tid = created.json()["id"]

    def assert_totals(owner_total, admin_total):
        previous_calls = len(calls)
        assert total(viewer) == 0
        assert len(calls) == previous_calls
        assert total(owner) == owner_total
        assert total(admin) == admin_total
        assert len(calls) == previous_calls + 2
        assert total(owner) == owner_total
        assert total(admin) == admin_total
        assert len(calls) == previous_calls + 2

    assert_totals(1, 1)
    response = c.patch(f"{url}/{tid}", headers=admin, json={"completed": True})
    assert response.status_code == 200, response.text
    assert_totals(0, 0)

    params["completed"] = True
    assert total(viewer) == 0
    assert total(owner) == 1
    assert total(admin) == 1
    assert c.delete(f"{url}/{tid}", headers=admin).status_code == 204
    assert_totals(0, 0)


def test_standalone_task_query_rejects_invalid_parameters(hub):
    c, users, *_ = hub
    headers = users["owner"]["headers"]
    for params in (
        {"status": "UNKNOWN"},
        {"status": "TODO"},
        {"priority": "UNKNOWN"},
        {"priority": "HIGH"},
        {"completed": "maybe"},
        {"limit": 101},
        {"search": "x" * 201},
        {"offset": 10_001},
        {"unknown": "value"},
    ):
        response = c.get("/api/tasks", headers=headers, params=params)
        assert response.status_code == 422, response.text
        assert ["query", next(iter(params))] in [
            issue["loc"] for issue in response.json()["error"]["details"]
        ]

    response = c.get("/api/tasks", headers=headers, params={"offset": 10_000})
    assert response.status_code == 200, response.text
    assert response.json()["offset"] == 10_000


def test_standalone_task_search_treats_wildcards_as_literals(hub):
    c, users, *_ = hub
    headers = users["owner"]["headers"]
    url = "/api/tasks"
    ids = []
    for payload in (
        {"title": "Release 100%_ready"},
        {"title": "Checklist", "description": "release 100%_READY"},
        {"title": "Release 100X_ready"},
        {"title": "Release 100%Xready"},
    ):
        created = c.post(url, headers=headers, json=payload)
        assert created.status_code == 201, created.text
        ids.append(created.json()["id"])

    for offset in range(2):
        response = c.get(
            url, headers=headers, params={"search": "  100%_ReAdY  ", "offset": offset, "limit": 1}
        )
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["total"] == 2
        assert result["offset"] == offset
        assert [item["id"] for item in result["items"]] == [ids[offset]]


def test_domain_lists_use_shared_pagination(hub):
    client, users, *_ = hub
    headers = users["owner"]["headers"]
    wid, pid = seed(hub)
    task = client.post(f"/api/v1/projects/{pid}/tasks", json={"title": "Task"}, headers=headers)
    assert task.status_code == 201
    tid = task.json()["id"]
    comments_url = f"/api/v1/tasks/{tid}/comments"
    assert (
        client.post(comments_url, json={"content": "Comment"}, headers=headers).status_code == 201
    )

    for url in (
        "/api/v1/workspaces",
        f"/api/v1/workspaces/{wid}/projects",
        f"/api/v1/projects/{pid}/tasks",
        comments_url,
    ):
        first = client.get(url, params={"limit": 1}, headers=headers)
        assert first.status_code == 200
        page = first.json()
        assert len(page["items"]) == page["total"] == page["page"] == page["limit"] == 1

        second = client.get(url, params={"page": 2, "limit": 1}, headers=headers)
        assert second.status_code == 200
        assert second.json() == {"items": [], "total": 1, "page": 2, "limit": 1}
        assert client.get(url, params={"limit": 101}, headers=headers).status_code == 422
