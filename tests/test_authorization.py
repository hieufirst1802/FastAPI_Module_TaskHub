import sqlite3
from contextlib import closing

from sqlalchemy.engine import make_url

from app.models.enums import UserRole

USERS_URL = "/api/v1/users"


def test_anonymous_user_cannot_list_accounts(public_client):
    assert public_client.get(USERS_URL).status_code == 401


def test_member_cannot_list_accounts(client):
    response = client.get(USERS_URL)
    assert response.status_code == 403
    assert "WWW-Authenticate" not in response.headers


def test_admin_can_list_accounts_and_manage_another_users_task(
    client, task, tasks_url, registered_user, settings
):
    credentials = {"username": "site_admin", "password": "admin-test-password"}
    registered = client.post("/api/v1/auth/register", json=credentials)
    assert registered.status_code == 201
    admin_id = registered.json()["id"]

    with (
        closing(sqlite3.connect(make_url(settings.database_url).database)) as connection,
        connection,
    ):
        connection.execute("UPDATE users SET role = ? WHERE id = ?", (UserRole.ADMIN, admin_id))

    login = client.post("/api/v1/auth/login", json=credentials)
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    users = client.get(USERS_URL, params={"offset": 1, "limit": 1}, headers=headers)
    assert users.status_code == 200
    assert users.json()["items"] == [registered_user]
    assert users.json()["offset"] == users.json()["limit"] == 1

    page = client.get(tasks_url, headers=headers)
    assert page.status_code == 200
    assert page.json()["items"] == [task]
    assert page.json()["total"] == 1

    url = f"{tasks_url}/{task['id']}"
    assert client.get(url, headers=headers).json() == task
    updated = client.patch(url, json={"title": "Admin edit"}, headers=headers)
    assert updated.status_code == 200
    assert updated.json() == {**task, "title": "Admin edit"}
    assert client.delete(url, headers=headers).status_code == 204
    assert client.get(url).status_code == 404
