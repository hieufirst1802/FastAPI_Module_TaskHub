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
from test_app import prepare_database
from test_day6 import MemoryRedis

from app.core.cache import TaskCache
from app.core.config import Settings
from app.main import create_app
from app.models.refresh_token import RefreshToken
from app.models.user import User


@pytest.fixture
def hub(tmp_path, monkeypatch):
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'hub.db').as_posix()}",
        jwt_secret_key="test-specific-secret-which-is-long-enough",
        redis_enabled=False,
    )
    prepare_database(settings)
    redis = MemoryRedis()
    cache = TaskCache(redis, prefix="test:hub")
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
    assert c.get("/api/v1/workspaces", headers=users["outsider"]["headers"]).json() == []
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
    assert len(c.get(f"/api/v1/tasks/{tid}/comments", headers=v).json()) == 1
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
    assert "/api/v1/auth/refresh" in schema["paths"]
    assert "/api/v1/projects/{pid}/tasks" in schema["paths"]
    assert "HTTPBearer" in schema["components"]["securitySchemes"]


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
    assert (
        c.post(
            "/api/v1/auth/register",
            json={"username": "another", "password": "Password123!", "email": "new@example.com"},
        ).status_code
        == 409
    )

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
