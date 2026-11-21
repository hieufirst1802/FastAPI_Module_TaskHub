# Bài 2 — Database & Layered Architecture

Nhánh thực hiện: `lesson-2-rework`

## 1. Mục tiêu

Mở rộng Bài 1 từ ứng dụng FastAPI sử dụng dữ liệu trong bộ nhớ thành ứng dụng có cơ sở dữ liệu lưu trữ lâu dài, sử dụng SQLAlchemy Async và Alembic.

Các mục tiêu chính:

- Tổ chức mã nguồn theo kiến trúc phân tầng.
- Sử dụng SQLAlchemy 2.0 Async để thao tác cơ sở dữ liệu.
- Xây dựng quan hệ giữa User và Task.
- Sử dụng Repository và Service để tách biệt truy cập dữ liệu và nghiệp vụ.
- Sử dụng Pydantic v2 để kiểm tra dữ liệu đầu vào và đầu ra.
- Sử dụng Alembic để quản lý database migrations.
- Hỗ trợ CRUD, phân trang và tổng số bản ghi.
- Kiểm thử API và khả năng lưu dữ liệu sau khi ứng dụng khởi động lại.

## 2. Cấu trúc dự án

```text
app/
├── api/
│   └── v1/
│       ├── endpoints/
│       │   ├── health.py
│       │   └── tasks.py
│       └── router.py
├── core/
│   ├── config.py
│   ├── constants.py
│   ├── database.py
│   ├── exceptions.py
│   └── messages.py
├── models/
│   ├── base.py
│   ├── enums.py
│   ├── task.py
│   └── user.py
├── repositories/
│   ├── base.py
│   ├── task.py
│   └── user.py
├── schemas/
│   ├── base.py
│   ├── pagination.py
│   └── task.py
├── services/
│   └── task.py
└── main.py

migrations/
├── versions/
└── env.py

tests/
├── conftest.py
├── test_health.py
├── test_pagination.py
├── test_persistence.py
└── test_tasks.py
```

## 3. Công nghệ sử dụng

- Python >= 3.12
- FastAPI
- SQLAlchemy 2.0 Async
- SQLite với aiosqlite
- Alembic
- Pydantic v2
- Pytest
- Ruff
- MyPy

## 4. Kiến trúc xử lý

Luồng xử lý request:

API Endpoint → Service → Repository → SQLAlchemy AsyncSession → Database

Vai trò từng tầng:

- API: tiếp nhận request, kiểm tra tham số và trả response.
- Service: xử lý nghiệp vụ.
- Repository: thực hiện truy vấn và thao tác dữ liệu.
- Models: định nghĩa cấu trúc bảng và quan hệ ORM.
- Schemas: xác thực dữ liệu đầu vào và định dạng dữ liệu đầu ra.
- Core: quản lý cấu hình và kết nối database.

## 5. Database và migration

Mặc định sử dụng SQLite:

`sqlite+aiosqlite:///./tasks.db`

Khởi tạo database bằng migration:

```powershell
uv run alembic upgrade head
```

Kiểm tra migration hiện tại:

```powershell
uv run alembic current
uv run alembic check
```

## 6. Cài đặt và chạy ứng dụng

Cài đặt dependencies:

```powershell
uv sync
```

Khởi tạo database:

```powershell
uv run alembic upgrade head
```

Chạy ứng dụng:

```powershell
uv run uvicorn app.main:create_app --factory --reload
```

Truy cập:

- API documentation: http://localhost:8000/docs
- Health check: http://localhost:8000/health

## 7. API endpoints

| Method | Endpoint | Chức năng |
|---|---|---|
| POST | `/api/v1/tasks` | Tạo Task |
| GET | `/api/v1/tasks` | Lấy danh sách Task có phân trang |
| GET | `/api/v1/tasks/{task_id}` | Lấy chi tiết Task |
| PATCH | `/api/v1/tasks/{task_id}` | Cập nhật Task |
| DELETE | `/api/v1/tasks/{task_id}` | Xóa Task |
| GET | `/health` | Kiểm tra ứng dụng và database |

API danh sách hỗ trợ:

- `offset`: vị trí bắt đầu, mặc định 0.
- `limit`: số bản ghi, mặc định 20, tối đa 100.
- `total`: tổng số bản ghi.

Task dùng trường `status` với các giá trị `TODO` (mặc định), `IN_PROGRESS` và `DONE`.
Migration chuyển `completed=false` thành `TODO` và `completed=true` thành `DONE`.
Nếu downgrade, `IN_PROGRESS` được chuyển thành `completed=false`.

Migration tạo user `demo` nếu chưa có. Bài 2 dùng tài khoản này làm chủ sở hữu khi tạo Task.
Khi xóa một user, database tự động xóa các Task của user đó bằng `ON DELETE CASCADE`.

## 8. Kiểm thử và chất lượng mã nguồn

Chạy kiểm thử:

```powershell
uv run pytest -q
```

Kiểm tra Ruff:

```powershell
uv run ruff check .
uv run ruff format --check .
```

Kiểm tra MyPy:

```powershell
uv run mypy
```

Kiểm tra đồng bộ database:

```powershell
uv run alembic check
```
