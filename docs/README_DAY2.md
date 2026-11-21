# TaskHub — FastAPI, Authentication, RBAC và Redis Caching

Đã bổ sung **Bài 6 – Redis Caching**. Hướng dẫn chạy, cấu hình, thiết kế cache và kiểm thử tại [README_DAY6.md](README_DAY6.md). Tài liệu middleware và xử lý lỗi: [README_DAY5.md](README_DAY5.md).

Phần bên dưới lưu lại nội dung nền tảng Bài 2; kết quả kiểm thử cũ chỉ áp dụng cho thời điểm hoàn thành Bài 2.

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
│   └── database.py
├── models/
│   ├── base.py
│   ├── task.py
│   └── user.py
├── repositories/
│   ├── base.py
│   ├── task.py
│   └── user.py
├── schemas/
│   ├── pagination.py
│   └── task.py
├── services/
│   └── task.py
└── main.py

migrations/
├── versions/
└── env.py

tests/
└── test_app.py
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
| POST | `/api/tasks` | Tạo Task |
| GET | `/api/tasks` | Lấy danh sách Task có phân trang |
| GET | `/api/tasks/{identifier}` | Lấy chi tiết Task |
| PATCH | `/api/tasks/{identifier}` | Cập nhật Task |
| DELETE | `/api/tasks/{identifier}` | Xóa Task |
| GET | `/health` | Kiểm tra ứng dụng và database |

API danh sách hỗ trợ:

- `offset`: vị trí bắt đầu, mặc định 0.
- `limit`: số bản ghi, mặc định 20, tối đa 100.
- `total`: tổng số bản ghi.

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

## 9. Kết quả kiểm tra hiện tại

- Ruff check: Passed.
- Ruff format: Passed.
- MyPy strict: Passed.
- Pytest: 2 passed.
- Alembic check: No new upgrade operations detected.

Bài 2 kế thừa nền tảng CRUD và kiến trúc phân tầng của Bài 1, đồng thời bổ sung database persistence và quản lý schema bằng migration.
