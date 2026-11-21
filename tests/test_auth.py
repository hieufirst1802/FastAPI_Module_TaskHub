import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from secrets import token_hex

import jwt
import pytest
from pydantic import ValidationError
from sqlalchemy.engine import make_url

from app.core.config import Settings

AUTH_URL = "/api/v1/auth"


def assert_unauthorized(response):
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_register_and_login(public_client, registered_user, access_token, settings, account):
    assert set(registered_user) == {"id", "username", "role"}
    assert registered_user["id"] > 0
    assert registered_user["username"] == account["username"]
    assert registered_user["role"] == "member"

    claims = jwt.decode(
        access_token,
        settings.jwt_secret_key.get_secret_value(),
        algorithms=["HS256"],
    )
    assert claims["sub"] == str(registered_user["id"])
    assert claims["type"] == "access"
    assert claims["jti"]
    assert claims["exp"] - claims["iat"] == settings.access_token_expire_minutes * 60

    response = public_client.get(
        f"{AUTH_URL}/me", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200
    assert response.json() == registered_user


def test_duplicate_username_returns_conflict(public_client, registered_user, account):
    response = public_client.post(f"{AUTH_URL}/register", json=account)
    assert response.status_code == 409


def test_rejects_invalid_registration(public_client):
    response = public_client.post(
        f"{AUTH_URL}/register", json={"username": "ab", "password": "123"}
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"jwt_secret_key": None}, "jwt_secret_key"),
        ({"jwt_secret_key": "short"}, "jwt_secret_key"),
        ({"jwt_algorithm": "HS512"}, "jwt_algorithm"),
        ({"access_token_expire_minutes": 0}, "access_token_expire_minutes"),
    ],
)
def test_invalid_jwt_settings_fail_validation(monkeypatch, changes, field):
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    monkeypatch.delenv("JWT_ALGORITHM", raising=False)
    monkeypatch.delenv("ACCESS_TOKEN_EXPIRE_MINUTES", raising=False)
    options = {"jwt_secret_key": token_hex(32), **changes}
    if options["jwt_secret_key"] is None:
        del options["jwt_secret_key"]

    with pytest.raises(ValidationError) as exc:
        Settings(_env_file=None, **options)
    assert {error["loc"] for error in exc.value.errors()} == {(field,)}


def test_missing_username_and_wrong_password_return_same_error(
    public_client, registered_user, account
):
    wrong = public_client.post(f"{AUTH_URL}/login", json={**account, "password": "x"})
    unknown = public_client.post(f"{AUTH_URL}/login", json={"username": "x", "password": "x"})
    assert_unauthorized(wrong)
    assert_unauthorized(unknown)
    assert wrong.json() == unknown.json()


@pytest.mark.parametrize("token", [None, "invalid-token"])
def test_me_rejects_missing_or_malformed_token(public_client, token):
    headers = {} if token is None else {"Authorization": f"Bearer {token}"}
    assert_unauthorized(public_client.get(f"{AUTH_URL}/me", headers=headers))


@pytest.mark.parametrize(
    "scenario",
    ["expired", "wrong-signature", "non-numeric-subject", "wrong-type", "missing-expiry"],
)
def test_me_rejects_invalid_access_token(public_client, registered_user, settings, scenario):
    now = datetime.now(UTC)
    claims = {
        "sub": str(registered_user["id"]),
        "iat": now - timedelta(minutes=2),
        "exp": now + timedelta(minutes=2),
        "type": "access",
        "jti": token_hex(16),
    }
    key = settings.jwt_secret_key.get_secret_value()
    if scenario == "expired":
        claims["exp"] = now - timedelta(minutes=1)
    elif scenario == "wrong-signature":
        key = token_hex(32)
    elif scenario == "non-numeric-subject":
        claims["sub"] = "abc"
    elif scenario == "wrong-type":
        claims["type"] = "refresh"
    elif scenario == "missing-expiry":
        del claims["exp"]
    token = jwt.encode(claims, key, algorithm="HS256")

    response = public_client.get(f"{AUTH_URL}/me", headers={"Authorization": f"Bearer {token}"})
    assert_unauthorized(response)


@pytest.mark.parametrize(
    "sql",
    ["DELETE FROM users WHERE id = ?", "UPDATE users SET is_active = 0 WHERE id = ?"],
)
def test_token_rejected_after_user_deleted_or_disabled(
    public_client, settings, registered_user, access_token, account, sql
):
    database = make_url(settings.database_url).database
    with closing(sqlite3.connect(database)) as connection, connection:
        connection.execute(sql, (registered_user["id"],))

    response = public_client.get(
        f"{AUTH_URL}/me", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert_unauthorized(response)
    assert_unauthorized(public_client.post(f"{AUTH_URL}/login", json=account))


def test_legacy_demo_cannot_log_in_after_task_creation(client, registered_user, task):
    assert task["owner_id"] == registered_user["id"]
    response = client.post(
        f"{AUTH_URL}/login", json={"username": "demo", "password": "disabled-login"}
    )
    assert_unauthorized(response)


@pytest.mark.parametrize(
    ("method", "suffix", "payload"),
    [
        ("GET", "", None),
        ("POST", "", {"title": "Anonymous task"}),
        ("GET", "/1", None),
        ("PATCH", "/1", {"title": "Anonymous edit"}),
        ("DELETE", "/1", None),
    ],
)
def test_tasks_require_authentication(public_client, tasks_url, method, suffix, payload):
    response = public_client.request(method, f"{tasks_url}{suffix}", json=payload)
    assert_unauthorized(response)


def test_tasks_are_visible_only_to_the_owner(client, registered_user, task, tasks_url):
    assert task["owner_id"] == registered_user["id"]
    credentials = {"username": "other_user", "password": "example-test-password"}
    assert client.post(f"{AUTH_URL}/register", json=credentials).status_code == 201
    login = client.post(f"{AUTH_URL}/login", json=credentials)
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = client.get(tasks_url, headers=headers)
    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["total"] == 0

    url = f"{tasks_url}/{task['id']}"
    assert client.get(url, headers=headers).status_code == 404
    assert client.patch(url, json={"title": "Other edit"}, headers=headers).status_code == 404
    assert client.delete(url, headers=headers).status_code == 404
    assert client.get(url).json() == task
