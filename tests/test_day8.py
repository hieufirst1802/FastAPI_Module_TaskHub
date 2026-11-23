import subprocess
import sys
from threading import get_ident
from unittest.mock import AsyncMock

from app.models.user import User
from app.services import auth
from app.services.auth import AuthService


def test_app_import_does_not_create_password_limiter():
    script = (
        "from unittest.mock import patch\n"
        "with patch('anyio.CapacityLimiter', "
        "side_effect=RuntimeError('CapacityLimiter requires an async backend')):\n"
        "    import app.main\n"
    )
    subprocess.run([sys.executable, "-c", script], check=True, timeout=15)


async def test_authentication_verifies_password_outside_event_loop(settings, monkeypatch):
    service = AuthService(AsyncMock(), settings)
    user = User(id=1, username="member", password_hash="stored-hash", is_active=True)
    monkeypatch.setattr(service.users, "by_username", AsyncMock(return_value=user))
    event_loop_thread = get_ident()

    def verify(password: str, encoded: str) -> bool:
        assert get_ident() != event_loop_thread
        return (password, encoded) == ("provided", "stored-hash")

    monkeypatch.setattr("app.services.auth.verify_password", verify)
    assert await service.authenticate("member", "provided") is user
    assert await service.authenticate("member", "wrong") is None


async def test_authentication_verifies_dummy_hash_for_unknown_user(settings, monkeypatch):
    service = AuthService(AsyncMock(), settings)
    monkeypatch.setattr(service.users, "by_username", AsyncMock(return_value=None))
    event_loop_thread = get_ident()
    calls = []

    def verify(password: str, encoded: str) -> bool:
        assert get_ident() != event_loop_thread
        calls.append((password, encoded))
        return True

    monkeypatch.setattr(auth, "verify_password", verify)
    assert await service.authenticate("unknown", "provided") is None
    assert calls == [("provided", auth._DUMMY_PASSWORD_HASH)]


async def test_registration_hashes_password_outside_event_loop(settings, monkeypatch):
    service = AuthService(AsyncMock(), settings)
    user = User(id=1, username="member")
    create = AsyncMock(return_value=user)
    monkeypatch.setattr(service.users, "by_username", AsyncMock(return_value=None))
    monkeypatch.setattr(service.users, "create", create)
    event_loop_thread = get_ident()

    def hash_new(password: str) -> str:
        assert get_ident() != event_loop_thread
        assert password == "provided"
        return "new-hash"

    monkeypatch.setattr(auth, "hash_password", hash_new)
    assert await service.register("member", "provided") is user
    assert create.await_args.kwargs["password_hash"] == "new-hash"


async def test_change_password_verifies_and_hashes_outside_event_loop(settings, monkeypatch):
    session = AsyncMock()
    service = AuthService(session, settings)
    user = User(id=1, username="member", password_hash="stored-hash")
    event_loop_thread = get_ident()
    calls = []

    def verify(password: str, encoded: str) -> bool:
        assert get_ident() != event_loop_thread
        calls.append((password, encoded))
        return True

    def hash_new(password: str) -> str:
        assert get_ident() != event_loop_thread
        calls.append(password)
        return "new-hash"

    monkeypatch.setattr(auth, "verify_password", verify)
    monkeypatch.setattr(auth, "hash_password", hash_new)
    await service.change_password(user, "current", "new")
    assert calls == [("current", "stored-hash"), "new"]
    assert user.password_hash == "new-hash"
    session.commit.assert_awaited_once()
