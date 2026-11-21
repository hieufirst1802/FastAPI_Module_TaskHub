# TaskHub – Workspace, Authentication và RBAC

FastAPI + SQLAlchemy async + Alembic + JWT access/refresh + Redis async. Giữ kiến trúc API → Service → Repository → Database. Xác thực và Workspace dùng `/api/v1`. Các API `/api/tasks` và `/api/users` tiếp tục phục vụ client cũ.

## Chạy local

Yêu cầu Python >= 3.12 và uv:

```powershell
uv sync --locked
Copy-Item .env.example .env
# Sửa JWT_SECRET_KEY trong .env.
uv run alembic upgrade head
docker compose up -d redis
uv run uvicorn app.main:create_app --factory --reload
```

Redis mặc định tắt khi chạy local. Đặt `REDIS_ENABLED=true` trong `.env` nếu chạy lệnh Docker để bật cache. Swagger: http://localhost:8000/docs; ReDoc: http://localhost:8000/redoc; health: http://localhost:8000/health. Cài bằng pip nếu cần: `python -m pip install -r requirements.txt`; dev tools: `python -m pip install pytest pytest-asyncio httpx ruff mypy`.

## Docker Compose

```powershell
docker compose up --build -d
docker compose logs -f app
docker compose down
```

Stack gồm app, PostgreSQL 16 và Redis 7. App tự chạy migration trước khi khởi động. PostgreSQL lưu trong volume `postgres_data`; `docker compose down` giữ volume. Compose dùng database riêng, không tự nhập SQLite cũ. Đổi JWT secret và `POSTGRES_PASSWORD` trước khi triển khai; mặc định chỉ dành cho local. Docker Engine phải đang chạy.

## Các chức năng

- Workspace, WorkspaceMember, Project, Label, TaskLabel, Comment và RefreshToken; migration giữ user/task cũ.
- JWT access + refresh, rotation một lần sử dụng kể cả request đồng thời, logout/revoke refresh token. Database lưu SHA-256 của refresh token, không lưu token gốc.
- Profile GET/PATCH full_name/email; đổi mật khẩu thu hồi mọi refresh token của user; từ chối tài khoản inactive.
- Workspace CRUD, thêm/xóa thành viên đã đăng ký, đổi EDITOR/VIEWER. Chủ Workspace nhận OWNER khi tạo, không được xóa/hạ vai trò qua API thành viên.
- Project CRUD, archive/unarchive. ARCHIVED vẫn đọc được, chặn sửa task/label/comment và tạo task mới. Owner/Admin có thể xóa Project/Workspace cùng dữ liệu con.
- Task theo Project: assignee, trạng thái, độ ưu tiên, due_date; lọc status/priority/assignee; page/limit/total.
- Label CRUD theo Project, gắn/gỡ label cùng Project; thêm/xem/xóa comment.
- Cache chi tiết task cũ và danh sách task theo Project, TTL, invalidation sau commit, fallback database. Luôn kiểm tra quyền Workspace trước cache hit.

## Ma trận quyền

User role lưu `admin/member` để tương thích dữ liệu cũ, tương ứng ADMIN/MEMBER trong đặc tả. Workspace role dùng OWNER/EDITOR/VIEWER. Không có API tự nâng user thành admin.

| Thao tác | OWNER | EDITOR | VIEWER | ADMIN |
|---|---|---|---|---|
| Đọc tài nguyên Workspace | Có | Có | Có | Có |
| Đổi tên/xóa Workspace, quản lý thành viên | Có | Không | Không | Có |
| Tạo/sửa/archive Project | Có | Có | Không | Có |
| Xóa Project | Có | Không | Không | Có |
| Tạo/sửa/xóa task và label | Có | Có | Không | Có |
| Thêm comment | Có | Có | Không | Có |
| Xóa comment | Mọi comment | Của mình | Không | Mọi comment |

Assignee phải là user active thuộc Workspace. Xóa membership tự gỡ assignee trong Workspace. User ngoài Workspace nhận 404; thành viên thiếu quyền nhận 403; chưa xác thực nhận 401. Đổi/xóa membership có hiệu lực ngay cả khi cache đang có dữ liệu.

## API

| Method | URL | Chức năng |
|---|---|---|
| POST | `/api/v1/auth/register` | username, password, email tùy chọn, full_name |
| POST | `/api/v1/auth/login` | access_token + refresh_token |
| POST | `/api/v1/auth/refresh` | Đổi refresh_token thành cặp token mới |
| POST | `/api/v1/auth/logout` | Revoke refresh_token trong body |
| POST | `/api/v1/auth/change-password` | current_password, new_password; cần Bearer |
| GET | `/api/v1/auth/me` | Tài khoản hiện tại |
| GET/PATCH | `/api/v1/users/me` | Profile |
| POST/GET | `/api/v1/workspaces` | Tạo/liệt kê |
| GET/PATCH/DELETE | `/api/v1/workspaces/{wid}` | Workspace CRUD |
| POST/GET | `/api/v1/workspaces/{wid}/members` | Thêm/liệt kê thành viên |
| PATCH/DELETE | `/api/v1/workspaces/{wid}/members/{uid}` | Đổi role/xóa thành viên |
| POST/GET | `/api/v1/workspaces/{wid}/projects` | Project trong Workspace |
| GET/PATCH/DELETE | `/api/v1/projects/{pid}` | Project CRUD; PATCH status=ARCHIVED/ACTIVE |
| POST/GET | `/api/v1/projects/{pid}/tasks` | Tạo; lọc/phân trang/cache |
| GET/PATCH/DELETE | `/api/v1/tasks/{tid}` | Task CRUD |
| POST/GET | `/api/v1/projects/{pid}/labels` | Tạo/liệt kê |
| PATCH/DELETE | `/api/v1/labels/{lid}` | Sửa/xóa |
| GET | `/api/v1/tasks/{tid}/labels` | Label của task |
| POST/DELETE | `/api/v1/tasks/{tid}/labels/{lid}` | Gắn/gỡ label |
| POST/GET | `/api/v1/tasks/{tid}/comments` | Thêm/liệt kê |
| DELETE | `/api/v1/comments/{cid}` | Xóa comment |

Task status: TODO/IN_PROGRESS/IN_REVIEW/DONE; priority: LOW/MEDIUM/HIGH/URGENT. Danh sách task hỗ trợ `?status=TODO&priority=HIGH&assignee_id=2&page=1&limit=20`. `page >= 1`, `1 <= limit <= 100`. PATCH cho phép `assignee_id=null` và `due_date=null` để xóa; các field khác không nhận null. Gửi due_date theo ISO 8601 UTC.

Danh sách Workspace, Project, Task trong Project và Comment trả `{items, total, page, limit}`.

Swagger: đăng ký → đăng nhập → Authorize bằng access_token → tạo Workspace → mời user → tạo Project → tạo task. Refresh/logout nhận `{"refresh_token":"..."}`. Refresh thành công làm token cũ hết hiệu lực; client phải lưu cặp mới. Logout chỉ revoke refresh token được gửi; access token đã phát vẫn sống đến TTL (mặc định 30 phút). Refresh token không dùng được như Bearer access token.

## Kiến trúc và dữ liệu cũ

`app/api/v1/endpoints` xử lý HTTP; `app/services` xử lý nghiệp vụ/RBAC/cache; `app/repositories` cung cấp async CRUD/pagination; `app/models` định nghĩa model/FK/constraints; `app/schemas` dùng Pydantic v2; `app/core` quản lý cấu hình, DB/Redis/JWT/dependencies/lỗi.

Task cũ giữ `project_id=null`, quyền owner/admin tại `/api/tasks`. Không tự chuyển task cũ vào Workspace bất kỳ. Task mới tạo qua `/api/v1/projects/{pid}/tasks`. `created_by` được trả từ cột `owner_id` hiện có để tránh nhân đôi dữ liệu. `completed` đồng bộ với status DONE khi sửa qua API. Danh sách `/api/tasks` chỉ liệt kê task cũ; thao tác chi tiết task có Project qua URL cũ vẫn kiểm tra quyền Workspace.

Khi nâng cấp client từ Bài 2–5, dùng `/api/tasks` cho task độc lập và `/api/users` cho danh sách tài khoản của admin. Hai danh sách này nhận `offset` và `limit`. Danh sách task theo Project dùng `page` và `limit`.

Bốn module in-memory Day 1 đã được đối chiếu import và Git history (`064067d`), chuyển thành `.py.txt` tại [docs/legacy_day1](docs/legacy_day1/README.md). Runtime dùng các package cùng tên. Tài liệu Day 2 cũ lưu tại [docs/README_DAY2.md](docs/README_DAY2.md).

Sao lưu trước khi chạy `uv run alembic upgrade head`. Đường nâng cấp nhận database Bài 2 (`6efbd1a2c410`), Bài 3–5 (`ab39fc81da27`) và database đã nâng lên Bài 6. Migration giữ user, task và trạng thái hiện tại, đồng thời khôi phục cờ `completed` từ trạng thái `DONE`. Downgrade qua revision TaskHub xóa dữ liệu Workspace, Project và refresh token, đồng thời chuyển `IN_REVIEW` về `IN_PROGRESS`. SQLite bật foreign keys khi ứng dụng kết nối.

## Cấu hình và cache

Xem `.env.example`: DATABASE_URL, JWT_SECRET_KEY, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS, REDIS_ENABLED, REDIS_URL, REDIS_CACHE_TTL, REDIS_SOCKET_TIMEOUT, REDIS_KEY_PREFIX. Dùng namespace Redis riêng cho từng database/môi trường.

Đặt `ENVIRONMENT=staging` hoặc `ENVIRONMENT=production` khi triển khai. Ứng dụng sẽ từ chối khởi động nếu `JWT_SECRET_KEY` là giá trị mẫu hoặc ngắn hơn 32 ký tự. Thuật toán JWT là `HS256`.

Client Redis theo lifespan. Khi Redis lỗi, API đọc database và ghi warning. Cache lưu chi tiết Task độc lập và danh sách Task theo Project. Chi tiết Task thuộc Project luôn đọc DB và kiểm tra quyền. Key danh sách gồm Project ID, phiên bản, bộ lọc và phân trang. Sau khi commit thay đổi, phiên bản liên quan đổi sang UUID mới. Một lượt đọc chậm chỉ có thể ghi vào phiên bản cũ. TTL phiên bản gấp đôi TTL dữ liệu. Nếu Redis lỗi khi cập nhật phiên bản, dữ liệu cũ có thể còn được đọc đến hết TTL. Authentication/membership không cache. Redis không lưu password/token.

## Kiểm thử và giới hạn

```powershell
uv run pytest -q
uv run ruff check .
uv run mypy
uv run alembic check
docker compose config --quiet
git diff --check
```

Tests dùng SQLite và Redis giả có đồng hồ TTL điều khiển được. Có kiểm thử cache hit/miss/expiration/giảm truy vấn/invalidation/lỗi Redis; JWT rotation/concurrency; profile; RBAC và thu hồi quyền; task/label/comment; cascade; API cũ; migration nâng/hạ/nâng giữ dữ liệu cũ và kiểm tra schema drift.

Chi tiết thiết kế cache xem [README_DAY6.md](README_DAY6.md).
