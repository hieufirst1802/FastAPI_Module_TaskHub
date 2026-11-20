# Bài 5 — Middleware và xử lý lỗi

Nhánh thực hiện: `lesson-5-middleware-exceptions`

## 1. Mục tiêu

Mở rộng Bài 4 với phản hồi lỗi chuẩn hóa, log HTTP và thời gian xử lý request.
Bộ kiểm thử tích hợp chạy trên SQLite.

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
│       │   ├── auth.py
│       │   ├── health.py
│       │   ├── tasks.py
│       │   └── users.py
│       └── router.py
├── core/
│   ├── config.py
│   ├── constants.py
│   ├── database.py
│   ├── dependencies.py
│   ├── enums.py
│   ├── exception_handlers.py
│   ├── exceptions.py
│   ├── messages.py
│   ├── permissions.py
│   └── security.py
├── middleware/
│   ├── request_logging.py
│   └── unhandled_errors.py
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
│   ├── auth.py
│   ├── base.py
│   ├── pagination.py
│   └── task.py
├── services/
│   ├── auth.py
│   ├── task.py
│   └── user.py
└── main.py

migrations/
├── versions/
└── env.py

tests/
├── conftest.py
├── test_auth.py
├── test_authorization.py
├── test_day5.py
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

Sau khi thiết lập `JWT_SECRET_KEY` ở mục 6, cập nhật database bằng migration:

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

Nếu chưa có `.env`, sao chép từ `.env.example`. Tạo khóa riêng bằng lệnh sau và đặt kết quả
vào `JWT_SECRET_KEY` trong `.env`. Khóa có tối thiểu 32 ký tự. Thuật toán là `HS256` và
`ACCESS_TOKEN_EXPIRE_MINUTES` mặc định là 30 phút.

```powershell
uv run python -c "import secrets; print(secrets.token_hex(32))"
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
| POST | `/api/v1/auth/register` | Đăng ký |
| POST | `/api/v1/auth/login` | Đăng nhập và nhận access token |
| GET | `/api/v1/auth/me` | Xem tài khoản hiện tại |
| GET | `/api/v1/users` | Liệt kê tài khoản có phân trang, dành cho admin |
| POST | `/api/v1/tasks` | Tạo Task |
| GET | `/api/v1/tasks` | Lấy danh sách Task có phân trang |
| GET | `/api/v1/tasks/{task_id}` | Lấy chi tiết Task |
| PATCH | `/api/v1/tasks/{task_id}` | Cập nhật Task |
| DELETE | `/api/v1/tasks/{task_id}` | Xóa Task |
| GET | `/health` | Kiểm tra ứng dụng và database |

Gửi `Authorization: Bearer <access_token>` cho các API yêu cầu đăng nhập. Member chỉ truy cập
Task của mình. Admin có thể xem, cập nhật và xóa Task của mọi người dùng. Khi tạo Task, hệ thống
lấy chủ sở hữu từ tài khoản đang đăng nhập. Đăng ký công khai luôn tạo tài khoản member.
Migration vô hiệu hóa tài khoản demo cũ có mật khẩu `disabled-login` và giữ lại dữ liệu liên quan.

API danh sách hỗ trợ:

- `offset`: vị trí bắt đầu, mặc định 0.
- `limit`: số bản ghi, mặc định 20, tối đa 100.
- `total`: tổng số bản ghi.

## 8. Phản hồi lỗi và log HTTP

Các lỗi trả về theo cấu trúc `{"error": {"code": "...", "message": "..."}}`.
Ví dụ, `401` dùng mã `unauthorized`, `403` dùng `forbidden` và Task không tìm thấy dùng
`not_found`. Lỗi xác thực giữ header `WWW-Authenticate: Bearer`. Chi tiết validation chỉ
gồm `loc`, `msg` và `type`.

`LOG_LEVEL` mặc định là `INFO`. Middleware ghi method, path, mã HTTP và thời gian xử lý.
`X-Process-Time` đo thời gian đến lúc bắt đầu gửi header, kể cả đối với lỗi 500 phát sinh
trước khi response bắt đầu. Nếu lỗi xảy ra sau khi bắt đầu streaming, mã trạng thái và header
đã gửi sẽ giữ nguyên và máy chủ ASGI xử lý lỗi.

## 9. Kiểm thử và chất lượng mã nguồn

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
