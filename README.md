# FastAPI Module TaskHub — Bài 5: Review & Optimization

Repository gồm **5 nhánh**, mỗi nhánh là một bài thực hành chạy độc lập.

| Bài | Nhánh | Nội dung |
| --- | --- | --- |
| 1 | [codex/day1-core-setup](../../tree/codex/day1-core-setup) | Skeleton, layered architecture, DI, Pydantic v2, CRUD trong bộ nhớ |
| 2 | [codex/day2-database](../../tree/codex/day2-database) | SQLAlchemy async, repository, quan hệ, pagination, Alembic |
| 3 | [codex/day3-auth-rbac](../../tree/codex/day3-auth-rbac) | Password hashing, JWT, RBAC, resource ownership |
| 4 | [codex/day4-core-features](../../tree/codex/day4-core-features) | Redis, middleware, exceptions, settings, logging, Docker |
| 5 | `main` — nhánh hiện tại | Bản hoàn chỉnh, kiểm thử, quality checks, review hiệu năng |

Chọn nhánh ở menu GitHub hoặc dùng `git switch <tên-nhánh>`, sau đó làm theo README
của bài đó. Bài sau kế thừa bài trước. Tên day là mốc bài, không thay đổi thời lượng
8 ngày trong đề. Xem [bảng phân chia](EXERCISES_PLAN.md) và [báo cáo review](REVIEW.md).

Sample app quản lý công việc, triển khai theo các nội dung nhìn thấy trong 3 ảnh.
Ảnh không chứa mục 2 mô tả sample app gốc; vì vậy domain Task Manager là giả định
để thực hành, chưa thể khẳng định khớp các nghiệp vụ của mục 2 chưa được cung cấp.
Thời lượng đúng theo các hàng: 8 + 8 + 40 + 8 = **64 giờ**, không phải 68 giờ.

## Chạy local (PowerShell)

Cần Python 3.12+ và uv. Dự án đã được chạy kiểm thử với Python 3.14.

```powershell
uv sync --locked
Copy-Item .env.example .env
# Mở .env, thay JWT_SECRET bằng chuỗi ngẫu nhiên tối thiểu 32 ký tự.
# Nếu không dùng Redis local: xóa dòng REDIS_URL khỏi .env.
uv run alembic upgrade head
uv run uvicorn app.main:create_app --factory --reload
```

Swagger: http://localhost:8000/docs ; ReDoc: http://localhost:8000/redoc ;
OpenAPI: http://localhost:8000/openapi.json ; health: http://localhost:8000/health.
Không tự tạo bảng khi khởi động; luôn dùng Alembic.

## Thực hành theo luồng

1. POST `/api/auth/register`: `{"username":"alice","password":"Password123!"}`.
2. POST `/api/auth/token`: form `username=alice&password=Password123!`.
   Trong Swagger dùng nút **Authorize**, nhập username/password.
3. Gửi Bearer token khi gọi các endpoint bảo vệ.
4. POST `/api/tasks`: `{"title":"Học FastAPI","description":"Ngày 1"}`.
5. GET `/api/tasks?offset=0&limit=20`: có items, total, offset, limit.
6. GET `/api/tasks/1`; PATCH `/api/tasks/1`: `{"completed":true}`.
7. Tạo tài khoản thứ hai: không nhìn thấy task của Alice và nhận 404 khi truy cập
   trực tiếp, sửa hoặc xóa task đó. Không nhận owner_id hoặc role từ payload task.
8. DELETE `/api/tasks/1`: 204; đọc lại: 404.
9. Tạo admin: `uv run python -m app.cli administrator`; nhập mật khẩu khi được hỏi.
   Đăng nhập admin để dùng GET `/api/admin/users` và quản lý mọi task.
   Đăng ký công khai chỉ tạo member.

Mật khẩu được băm Argon2 qua pwdlib; JWT HS256 có sub, iat, exp. Thời hạn mặc định
30 phút. Role được lấy từ DB mỗi request. Token hết hạn/sai trả 401, thiếu role
trả 403, tài nguyên không tồn tại/không thuộc quyền trả 404, trùng username trả 409,
payload sai trả 422. Không trả password_hash. PATCH bỏ qua trường không gửi và từ
chối null. Đây là access-token flow, không có refresh-token/logout revocation.

## Kiến trúc và đối chiếu yêu cầu

| Buổi | Nội dung | Triển khai |
| --- | --- | --- |
| 1 | Layered architecture, instance, APIRouter, lifespan, DI, Pydantic v2, CRUD | `app/main.py`, `api.py`, `database.py`, `schemas.py`, `services.py` |
| 2 | SQLAlchemy async, models, relationships, generic repository, pagination, Alembic | `models.py`, `repositories.py`, `migrations/` |
| 3–7 | Password hashing, JWT, current user, RBAC, ownership | `security.py`, `services.py`, auth/admin/task endpoints |
| 3–7 | Middleware, exception handling, logging | Request ID, thời gian xử lý, log method/path/status; lỗi có request_id |
| 3–7 | Redis, API documentation | `cache.py`, cache task đã kiểm tra quyền, Swagger/ReDoc/OpenAPI |
| 3–7 | pydantic-settings, multi-environment, fail-fast | `config.py`, development/test/production, secret bắt buộc, production yêu cầu Redis |
| 3–7 | Docker tùy chọn | Multi-stage Dockerfile, Compose app + PostgreSQL + Redis + migration job |
| 8 | Review, DRY, Ruff, mypy, performance, README | Generic repository, service ownership dùng chung, tests, lệnh kiểm tra dưới đây |

API → service cho ownership → repository → async session → DB. Một session mỗi
request; rollback khi lỗi, đóng session khi kết thúc. Quan hệ User 1–n Task dùng
lazy="raise" để tránh implicit async I/O. Không trả ORM relationship ra response.

## Biến môi trường

| Biến | Mặc định / điều kiện |
| --- | --- |
| ENVIRONMENT | development; nhận test, production |
| DATABASE_URL | sqlite+aiosqlite:///./tasks.db; Compose dùng postgresql+asyncpg |
| JWT_SECRET | bắt buộc, tối thiểu 32 ký tự |
| TOKEN_MINUTES | 30, từ 1 đến 1440 |
| REDIS_URL | tùy chọn local; bắt buộc production, kiểm tra kết nối khi startup |
| CACHE_SECONDS | 60, tối thiểu 1 |
| POSTGRES_PASSWORD | bắt buộc khi chạy Compose; dùng ký tự URL-safe |

Settings được kiểm tra khi tạo app. DB được kiểm tra trong lifespan; migration
thiếu sẽ được phát hiện khi truy vấn bảng. Không ghi mật khẩu/token vào log.

## Docker Compose

Khởi động Docker Desktop Linux Engine trước. Trong .env, đặt JWT_SECRET ngẫu nhiên
và thêm POSTGRES_PASSWORD (URL-safe). Compose tự dùng hostname db/redis nội bộ.

```powershell
docker compose up --build -d
docker compose logs app
docker compose exec app python -m app.cli administrator
docker compose down
```

Migration job chạy trước app; PostgreSQL lưu dữ liệu trong named volume. Không
publish port DB/Redis ra host. `docker compose down` giữ dữ liệu.

## Kiểm tra chất lượng

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy app
uv run pytest -q
uv run alembic check
```

Kiểm thử API dùng SQLite tạm riêng cho mỗi test. Kiểm thử Redis dùng mock để xác
nhận TTL/hit/fallback; không thay cho kiểm thử Redis server thực tế. Các kiểm tra
migration cần chạy sau `alembic upgrade head` với DB đã cấu hình.

## Review hiệu năng và giới hạn

- Query danh sách có pagination giới hạn 100, ORDER BY id ổn định; index username
  unique và owner_id hỗ trợ login/lọc task. Không có N+1 relationship loading.
- Password hashing/verification chạy trong threadpool để không khóa event loop.
- Cache chỉ cho GET task sau kiểm tra quyền DB. Key băm từ nội dung hiện tại,
  nên update không đọc bản cũ; delete vẫn bị chặn bởi kiểm tra DB trước cache.
  Key cũ hết hạn theo TTL. Redis lỗi thì dùng DB, không chặn CRUD.
- Do vẫn đọc DB để kiểm tra quyền và nội dung, cache hiện tại chủ yếu minh họa
  Redis; chưa chứng minh cải thiện latency. Không tuyên bố số liệu benchmark.
- COUNT và trang dữ liệu là hai query; phân trang offset lớn nên cân nhắc cursor.
- Background tasks/queue là tùy chọn trong đề, không thêm nghiệp vụ giả để sử dụng.
- Docker/PostgreSQL/Redis thực tế cần xác minh khi Docker Engine hoạt động.

Tham khảo chính thức: [FastAPI JWT](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/),
[SQLAlchemy async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html).
