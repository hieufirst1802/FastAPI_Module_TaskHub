from threading import get_ident
from unittest.mock import AsyncMock

from app.models.user import User
from app.services.auth import AuthService


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
