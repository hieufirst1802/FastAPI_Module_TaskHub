# FastAPI Module TaskHub

Dự án thực hành xây dựng REST API bằng FastAPI theo kiến trúc phân lớp. Các chức năng được phát triển theo từng giai đoạn, từ thiết lập nền tảng đến cơ sở dữ liệu, xác thực và mở rộng tính năng.

## Day 1 — Core Setup & Architecture

### 1. Mục tiêu

- Xây dựng FastAPI application factory.
- Tổ chức API bằng `APIRouter`.
- Áp dụng kiến trúc phân lớp: API → Service → Repository.
- Sử dụng Dependency Injection để quản lý các thành phần.
- Sử dụng Pydantic v2 để kiểm tra và xác thực dữ liệu.
- Xây dựng API CRUD quản lý Task.
- Xử lý các lỗi HTTP 404 và 422.

### 2. Cấu trúc dự án

```text
app/
├── api/
│   └── v1/
│       ├── endpoints/
│       │   ├── health.py
│       │   └── tasks.py
│       └── router.py
├── core/
│   ├── constants.py
│   ├── exceptions.py
│   └── messages.py
├── models/
│   └── task.py
├── repositories/
│   └── task.py
├── schemas/
│   ├── base.py
│   ├── pagination.py
│   └── task.py
├── services/
│   └── task.py
└── main.py
```

### 3. Cài đặt môi trường

Yêu cầu Python 3.12 trở lên và công cụ `uv`.

```cmd
uv sync --locked
```

### 4. Chạy ứng dụng

```cmd
uv run uvicorn app.main:create_app --factory --reload
```

Sau khi chạy, truy cập:

- API documentation: http://localhost:8000/docs
- Health check: http://localhost:8000/health

### 5. Các API Task

| Method | Endpoint | Chức năng |
|---|---|---|
| POST | `/api/tasks` | Tạo Task |
| GET | `/api/tasks` | Lấy danh sách Task |
| GET | `/api/tasks/{task_id}` | Lấy Task theo ID |
| PATCH | `/api/tasks/{task_id}` | Cập nhật Task |
| DELETE | `/api/tasks/{task_id}` | Xóa Task |

Ví dụ tạo Task:

```json
{
  "title": "Học FastAPI"
}
```

Ví dụ cập nhật Task:

```json
{
  "completed": true
}
```

### 6. Phạm vi Day 1

- Dữ liệu được lưu trong In-memory Repository, chưa sử dụng database.
- Dữ liệu sẽ mất khi ứng dụng khởi động lại.
- Mỗi ứng dụng được tạo bằng application factory có repository riêng.
- Vì dữ liệu chỉ lưu trong bộ nhớ, nên sử dụng một worker khi chạy ứng dụng.

### 7. Kiểm tra chất lượng

```cmd
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy app
```

### 8. Quản lý dependencies

Dự án sử dụng `pyproject.toml` để khai báo dependencies và `uv.lock` để khóa phiên bản.

Đồng bộ môi trường:

```cmd
uv sync --locked
```

Cập nhật lockfile khi dependencies thay đổi:

```cmd
uv lock
```
