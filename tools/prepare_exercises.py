"""Prepare independently runnable lesson snapshots; never changes Git refs or sends data."""

import shutil
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / ".exercise-build"
ALLOW = [
    "app",
    "tests",
    "migrations",
    "pyproject.toml",
    "uv.lock",
    "requirements.txt",
    ".gitignore",
    ".env.example",
    "alembic.ini",
    "README.md",
]


def write(root: Path, name: str, content: str) -> None:
    target = root / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")


def copy_snapshot(snapshot_name: str, excluded: set[str]) -> Path:
    target = BUILD / snapshot_name
    if target.exists():
        raise SystemExit(f"Refusing to overwrite existing snapshot: {target}")
    target.mkdir(parents=True)
    for name in ALLOW:
        source = ROOT / name
        if not source.exists():
            continue
        if source.is_dir():
            for file in source.rglob("*"):
                relative = file.relative_to(ROOT).as_posix()
                if file.is_file() and "__pycache__" not in file.parts and relative not in excluded:
                    destination = target / relative
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(file, destination)
        elif name not in excluded:
            shutil.copy2(source, target / name)
    return target


MINIMAL_MAIN = """
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.api import router
from app.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_async_engine(config.database_url, pool_pre_ping=True)
        app.state.settings = config
        app.state.sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            yield
        finally:
            await engine.dispose()

    app = FastAPI(title="TaskHub - LESSON", lifespan=lifespan)

    @app.get("/health")
    async def health(request: Request) -> dict[str, str]:
        async with request.app.state.sessions() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ok"}

    app.include_router(router)
    return app
"""

DAY2_API = """
from fastapi import APIRouter, HTTPException, Query, Response
from app.database import Session
from app.models import Task
from app.repositories import BaseRepository, UserRepository
from app.schemas import TaskCreate, TaskOut, TaskPage, TaskUpdate

router = APIRouter(prefix="/api", tags=["Tasks"])


async def find_task(identifier: int, session: Session) -> Task:
    task = await BaseRepository(session, Task).get(identifier)
    if task is None:
        raise HTTPException(404, "Task not found")
    return task


@router.post("/tasks", response_model=TaskOut, status_code=201)
async def create(data: TaskCreate, session: Session) -> object:
    # Fixed demo user illustrates the relationship before authentication in lesson 3.
    users = UserRepository(session)
    owner = await users.by_username("demo")
    if owner is None:
        owner = await users.create(username="demo", password_hash="disabled-login")
    return await BaseRepository(session, Task).create(**data.model_dump(), owner_id=owner.id)


@router.get("/tasks", response_model=TaskPage)
async def page(session: Session, offset: int = Query(0, ge=0),
               limit: int = Query(20, ge=1, le=100)) -> TaskPage:
    rows, total = await BaseRepository(session, Task).page(offset, limit)
    return TaskPage(items=[TaskOut.model_validate(row) for row in rows],
                    total=total, offset=offset, limit=limit)


@router.get("/tasks/{identifier}", response_model=TaskOut)
async def read(identifier: int, session: Session) -> object:
    return await find_task(identifier, session)


@router.patch("/tasks/{identifier}", response_model=TaskOut)
async def update(identifier: int, data: TaskUpdate, session: Session) -> object:
    task = await find_task(identifier, session)
    return await BaseRepository(session, Task).update(task, data.model_dump(exclude_unset=True))


@router.delete("/tasks/{identifier}", status_code=204)
async def delete(identifier: int, session: Session) -> Response:
    await BaseRepository(session, Task).delete(await find_task(identifier, session))
    return Response(status_code=204)
"""

SIMPLE_TEST = """
import asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from app.config import Settings
from app.main import create_app
from app.models import Base


def test_persistent_crud_and_pagination(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'lesson.db'}"
    async def prepare():
        engine = create_async_engine(url)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await engine.dispose()
    asyncio.run(prepare())
    config = Settings(database_url=url, jwt_secret="test-secret-at-least-32-characters-long")
    with TestClient(create_app(config)) as client:
        response = client.post("/api/tasks", json={"title": "Database task"})
        assert response.status_code == 201
        identifier = response.json()["id"]
        assert client.get("/api/tasks?limit=1").json()["total"] == 1
        assert client.get("/api/tasks?limit=101").status_code == 422
        assert client.patch(f"/api/tasks/{identifier}", json={"completed": True}).status_code == 200
    # Restart app with the same DB: committed data persists.
    with TestClient(create_app(config)) as client:
        assert client.get(f"/api/tasks/{identifier}").json()["completed"] is True
        assert client.delete(f"/api/tasks/{identifier}").status_code == 204
        assert client.get(f"/api/tasks/{identifier}").status_code == 404
"""

DAY1 = {
    "app/schemas.py": """
from pydantic import BaseModel, ConfigDict, Field, model_validator

class TaskCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    completed: bool = False

class TaskUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    title: str | None = Field(default=None, min_length=1, max_length=200)
    completed: bool | None = None

    @model_validator(mode="after")
    def non_null(self) -> "TaskUpdate":
        if any(getattr(self, name) is None for name in self.model_fields_set):
            raise ValueError("Omit unchanged fields; null is not allowed")
        return self

class TaskOut(TaskCreate):
    id: int
""",
    "app/repositories.py": """
from threading import RLock
from typing import Any
from app.schemas import TaskCreate, TaskOut

class TaskRepository:
    def __init__(self) -> None:
        self.rows: dict[int, TaskOut] = {}
        self.next_id = 1
        self.lock = RLock()

    def create(self, data: TaskCreate) -> TaskOut:
        with self.lock:
            row = TaskOut(id=self.next_id, **data.model_dump())
            self.next_id += 1
            self.rows[row.id] = row
            return row

    def get(self, identifier: int) -> TaskOut | None:
        with self.lock:
            return self.rows.get(identifier)

    def page(self, offset: int, limit: int) -> list[TaskOut]:
        with self.lock:
            return list(self.rows.values())[offset:offset + limit]

    def update(self, identifier: int, values: dict[str, Any]) -> TaskOut | None:
        with self.lock:
            row = self.rows.get(identifier)
            if row is None:
                return None
            updated = TaskOut.model_validate(row.model_dump() | values)
            self.rows[identifier] = updated
            return updated

    def delete(self, identifier: int) -> bool:
        with self.lock:
            return self.rows.pop(identifier, None) is not None
""",
    "app/services.py": """
from fastapi import HTTPException
from app.repositories import TaskRepository
from app.schemas import TaskOut, TaskUpdate

class TaskService:
    def __init__(self, repository: TaskRepository):
        self.repository = repository

    def get(self, identifier: int) -> TaskOut:
        row = self.repository.get(identifier)
        if row is None:
            raise HTTPException(404, "Task not found")
        return row

    def update(self, identifier: int, data: TaskUpdate) -> TaskOut:
        row = self.repository.update(identifier, data.model_dump(exclude_unset=True))
        if row is None:
            raise HTTPException(404, "Task not found")
        return row

    def delete(self, identifier: int) -> None:
        if not self.repository.delete(identifier):
            raise HTTPException(404, "Task not found")
""",
    "app/api.py": """
from typing import Annotated
from fastapi import APIRouter, Depends, Query, Request, Response
from app.repositories import TaskRepository
from app.services import TaskService
from app.schemas import TaskCreate, TaskOut, TaskUpdate

router = APIRouter(prefix="/api", tags=["Tasks"])

def get_repository(request: Request) -> TaskRepository:
    repository: TaskRepository = request.app.state.repository
    return repository

Repository = Annotated[TaskRepository, Depends(get_repository)]

@router.post("/tasks", response_model=TaskOut, status_code=201)
def create(data: TaskCreate, repository: Repository) -> TaskOut:
    return repository.create(data)

@router.get("/tasks", response_model=list[TaskOut])
def page(repository: Repository, offset: int = Query(0, ge=0),
         limit: int = Query(20, ge=1, le=100)) -> list[TaskOut]:
    return repository.page(offset, limit)

@router.get("/tasks/{identifier}", response_model=TaskOut)
def read(identifier: int, repository: Repository) -> TaskOut:
    return TaskService(repository).get(identifier)

@router.patch("/tasks/{identifier}", response_model=TaskOut)
def update(identifier: int, data: TaskUpdate, repository: Repository) -> TaskOut:
    return TaskService(repository).update(identifier, data)

@router.delete("/tasks/{identifier}", status_code=204)
def delete(identifier: int, repository: Repository) -> Response:
    TaskService(repository).delete(identifier)
    return Response(status_code=204)
""",
    "app/main.py": """
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.api import router
from app.repositories import TaskRepository

def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.repository = TaskRepository()
        yield
    app = FastAPI(title="TaskHub - Bai 1 Core Setup", lifespan=lifespan)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(router)
    return app
""",
    "tests/test_app.py": """
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
        assert client.patch(f"/api/tasks/{identifier}", json={"completed": True}).json()["completed"]
        assert client.patch(f"/api/tasks/{identifier}", json={"title": None}).status_code == 422
        assert client.delete(f"/api/tasks/{identifier}").status_code == 204
        assert client.get(f"/api/tasks/{identifier}").status_code == 404
        assert client.get("/openapi.json").status_code == 200
    with TestClient(create_app()) as client:
        assert client.get("/api/tasks").json() == []
""",
}


def lesson_readme(number: int, branch: str, title: str, details: str) -> str:
    setup = (
        ""
        if number == 1
        else "Copy-Item .env.example .env\n# Sua JWT_SECRET (toi thieu 32 ky tu)\nuv run alembic upgrade head\n"
    )
    return f"""# Bài {number} — {title}

Nhánh: `{branch}`. Đây là một bài riêng, checkout và chạy trực tiếp từ thư mục gốc.

## Mục tiêu và phần đã hoàn thành

{details}

## Cài đặt và chạy (PowerShell)

```powershell
git switch {branch}
uv sync --locked
{setup}uv run uvicorn app.main:create_app --factory --reload
```

Mở http://localhost:8000/docs để thực hành và http://localhost:8000/health để kiểm tra.

## Kiểm tra

```powershell
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy app
```

Các bài có phần mở rộng tích lũy: core → database → security → features → review.
`main` là bài 5, bốn nhánh `codex/day*` là bài 1–4, tổng đúng 5 nhánh.
Tên day là mốc bài thực hành, không có nghĩa giáo trình chỉ có 5 ngày.
"""


def main() -> None:
    # Snapshots exclude tools, local environments, actual secrets and databases.
    common_excluded = {"app/cache.py", "tests/test_cache.py"}
    first = copy_snapshot(
        "day1",
        common_excluded
        | {
            "app/config.py",
            "app/database.py",
            "app/models.py",
            "app/security.py",
            "app/cli.py",
            "alembic.ini",
            ".env.example",
        },
    )
    # Lesson 1 must not accidentally carry SQL migrations.
    migration = first / "migrations"
    if migration.exists():
        for file in migration.rglob("*"):
            if file.is_file():
                file.unlink()
    for name, source in DAY1.items():
        write(first, name, source)
    write(
        first,
        "README.md",
        lesson_readme(
            1,
            "codex/day1-core-setup",
            "Core Setup & Architecture",
            """
- FastAPI app factory, APIRouter, lifespan khởi tạo repository riêng cho mỗi app.
- Layered API → service → repository, Dependency Injection từ request.app.state.
- Pydantic v2, validation và CRUD Task trong bộ nhớ, mã lỗi 404/422.
- Thực hành: POST /api/tasks với {\"title\":\"Học FastAPI\"}; GET /api/tasks;
  PATCH /api/tasks/1 với {\"completed\":true}; DELETE /api/tasks/1.
- Dữ liệu mất khi khởi động lại; dùng một worker cho bài trong bộ nhớ.
- Không cần .env hay database ở bài này. Tests kiểm tra CRUD và dữ liệu tách theo app.
""",
        ),
    )

    second = copy_snapshot(
        "day2", common_excluded | {"app/security.py", "app/cli.py", "app/services.py"}
    )
    write(second, "app/main.py", MINIMAL_MAIN.replace("LESSON", "Bai 2 Database"))
    write(second, "app/api.py", DAY2_API)
    write(second, "tests/test_app.py", SIMPLE_TEST)
    write(
        second,
        "README.md",
        lesson_readme(
            2,
            "codex/day2-database",
            "Database, Repository & Alembic",
            """
- SQLAlchemy 2 async, AsyncSession theo request; model User 1–n Task, khóa ngoại và index.
- Generic BaseRepository[T] có get/create/update/delete/page; phân trang offset/limit và total.
- Alembic initial migration, nâng/hạ schema. CRUD lưu SQLite, hỗ trợ URL PostgreSQL asyncpg.
- Tài khoản demo cố định minh họa quan hệ; chưa có đăng nhập/phân quyền ở bài 2.
  Thực hành local một người dùng; bài 3 bổ sung bảo vệ API.
- Thử POST /api/tasks với {\"title\":\"Task lưu DB\"}; khởi động lại và GET /api/tasks.
- Thử `uv run alembic downgrade base` rồi `uv run alembic upgrade head` trên DB thực hành trống;
  downgrade xóa bảng và dữ liệu. `uv run alembic check` không được có schema drift.
- Test xác minh dữ liệu còn sau khi tạo lại app, PATCH, DELETE và giới hạn pagination.
""",
        ),
    )

    third = copy_snapshot("day3", common_excluded)
    third_main = MINIMAL_MAIN.replace("LESSON", "Bai 3 Authentication and RBAC")
    third_main = third_main.replace(
        "from app.config import Settings, get_settings",
        "from app.config import Settings, get_settings\nfrom app.security import passwords",
    )
    third_main = third_main.replace(
        "app.state.settings = config",
        'app.state.settings = config\n        app.state.dummy_hash = passwords.hash("dummy-password-for-timing")',
    )
    write(third, "app/main.py", third_main)
    api = (ROOT / "app/api.py").read_text(encoding="utf-8").replace("import hashlib\n", "")
    start = api.index("    # Always authorize")
    end = api.index("\n\n@router.patch", start)
    api = (
        api[:start]
        + "    task = await TaskService(session).owned(identifier, user)\n    return TaskOut.model_validate(task)\n"
        + api[end:]
    )
    write(third, "app/api.py", api)
    tests = (third / "tests/test_app.py").read_text(encoding="utf-8")
    tests = tests.replace('    assert "X-Request-ID" in client.get("/health").headers\n', "")
    write(third, "tests/test_app.py", tests)
    write(
        third,
        "README.md",
        lesson_readme(
            3,
            "codex/day3-auth-rbac",
            "Authentication, RBAC & Ownership",
            """
- Argon2 password hashing, OAuth2 password form, JWT HS256 có sub/iat/exp.
- Dependency get_current_user đọc User từ DB; role member/admin, service kiểm tra owner.
- POST /api/auth/register: {\"username\":\"alice\",\"password\":\"Password123!\"}.
- POST /api/auth/token: form username/password; dùng Authorize trong Swagger.
- Member chỉ nhìn thấy task của mình; đọc/sửa/xóa task người khác trả 404.
- GET /api/users/me; GET /api/admin/users chỉ admin, member nhận 403.
- Tạo admin: `uv run python -m app.cli administrator`, nhập mật khẩu tại prompt.
- Tests kiểm tra credentials sai, JWT hết hạn, ownership, RBAC, admin và validation.
- Ảnh đề không có mục 2 sample app gốc; Task Manager là domain được chọn để thực hành.
""",
        ),
    )

    fourth = copy_snapshot("day4", set())
    for name in ["Dockerfile", ".dockerignore", "compose.yaml"]:
        shutil.copy2(ROOT / name, fourth / name)
    original = (fourth / "README.md").read_text(encoding="utf-8")
    write(
        fourth,
        "README.md",
        "# Bài 4 — Core Features & Configuration\n\n"
        "Nhánh: `codex/day4-core-features`. Bổ sung middleware, exception handlers, Redis cache, "
        "settings đa môi trường, logging, Swagger/ReDoc và Docker Compose.\n\n"
        "Kế thừa đầy đủ JWT/RBAC/ownership của bài 3. Chạy và thực hành theo hướng dẫn dưới đây.\n\n"
        + original,
    )
    print("Prepared snapshots in .exercise-build/day1 through day4")


if __name__ == "__main__":
    main()
