# Bài 2 — Database, Repository & Alembic

Nhánh: `lesson-2`. Đây là một bài riêng, checkout và chạy trực tiếp từ thư mục gốc.

## Mục tiêu và phần đã hoàn thành


- SQLAlchemy 2 async, AsyncSession theo request; model User 1–n Task, khóa ngoại và index.
- Generic BaseRepository[T] có get/create/update/delete/page; phân trang offset/limit và total.
- Alembic initial migration, nâng/hạ schema. CRUD lưu SQLite, hỗ trợ URL PostgreSQL asyncpg.
- Tài khoản demo cố định minh họa quan hệ; chưa có đăng nhập/phân quyền ở bài 2.
  Thực hành local một người dùng; bài 3 bổ sung bảo vệ API.
- Thử POST /api/tasks với {"title":"Task lưu DB"}; khởi động lại và GET /api/tasks.
- Thử `uv run alembic downgrade base` rồi `uv run alembic upgrade head` trên DB thực hành trống;
  downgrade xóa bảng và dữ liệu. `uv run alembic check` không được có schema drift.
- Test xác minh dữ liệu còn sau khi tạo lại app, PATCH, DELETE và giới hạn pagination.


## Cài đặt và chạy (PowerShell)

```powershell
git switch lesson-2
uv sync --locked
Copy-Item .env.example .env
# Sua JWT_SECRET (toi thieu 32 ky tu)
uv run alembic upgrade head
uv run uvicorn app.main:create_app --factory --reload
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
Mỗi bài có một nhánh `lesson-*` và một PR riêng vào `main`.
Tên day là mốc bài thực hành, không có nghĩa giáo trình chỉ có 5 ngày.
