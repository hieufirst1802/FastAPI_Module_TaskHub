"""Run: python -m app.cli USERNAME (password is prompted, never logged)."""

import asyncio
import getpass
import sys

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.repositories import UserRepository
from app.security import passwords


async def create_admin(username: str, password: str) -> None:
    from app.schemas import Register

    data = Register(username=username, password=password)
    engine = create_async_engine(get_settings().database_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            repository = UserRepository(session)
            if await repository.by_username(data.username):
                raise ValueError("Username already exists")
            await repository.create(
                username=data.username, password_hash=passwords.hash(data.password), role="admin"
            )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m app.cli USERNAME")
    asyncio.run(create_admin(sys.argv[1], getpass.getpass("Admin password: ")))
