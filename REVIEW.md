# Bài 5 — Review, Refactor & Optimization

## Kết quả review

- Layered architecture tách API, service ownership, repository, schema, model, config.
- Generic BaseRepository[T] loại bỏ CRUD lặp; TaskService dùng chung kiểm tra quyền.
- App factory và lifespan quản lý engine/Redis; đóng tài nguyên khi shutdown.
- Session riêng từng request, rollback lỗi; login không lưu/ghi log mật khẩu dạng rõ.
- JWT giới hạn thuật toán HS256 và bắt buộc sub/iat/exp; role lấy từ DB mỗi request.
- Đăng ký công khai không nhận role; task không nhận owner_id, trả 404 cho khác owner.
- Pydantic v2 phân biệt create/update/read, PATCH từ chối null cho cột không nullable.

## Review hiệu năng

- username unique index hỗ trợ đăng nhập, owner_id index hỗ trợ lọc tài nguyên.
- Phân trang tối đa 100 bản ghi, thứ tự id ổn định, không load relationship ngầm.
- Hash/verify Argon2 chạy threadpool; async engine/async session cho DB I/O.
- Redis có TTL và fallback khi lỗi. Cache key gắn nội dung hiện tại và owner;
  kiểm tra quyền DB trước cache. Cache này minh họa tích hợp, vẫn đọc DB mỗi lần.
- Chưa benchmark hoặc chứng minh giảm latency; offset lớn/COUNT lớn cần đo trên
  PostgreSQL với dữ liệu thực tế trước khi chuyển sang cursor pagination.

## Quy trình xác minh

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy app
uv run pytest -q
uv run alembic upgrade head
uv run alembic check
```

API tests bao gồm CRUD, pagination, đăng nhập, duplicate username, JWT hết hạn,
member/admin, ownership, payload validation và OpenAPI. Redis mock test kiểm tra
cache hit, TTL và fallback. Các bài 1–2 có test riêng cho in-memory isolation và
DB persistence. Bài 3 có auth/RBAC tests; bài 4–5 có thêm cache test.

Migration đã được kiểm tra upgrade → check → downgrade → upgrade trên SQLite.
Compose config đã được kiểm tra cú pháp. Docker Engine chưa chạy trong phiên
chuẩn bị đầu tiên, nên chưa xác minh tích hợp PostgreSQL và Redis server thực tế.
Một cảnh báo deprecation xuất phát từ TestClient/httpx ở thư viện đã cài; test vẫn pass.

## Kết quả kiểm thử từng bài

Đã chạy riêng từng thư mục bài trong một Python interpreter riêng để tránh dùng
nhầm import của bản hoàn chỉnh; Python 3.14, SQLite tạm riêng cho tests.

| Bài | Pytest | Ruff | mypy strict |
| --- | --- | --- | --- |
| 1 Core Setup | 1 passed | Đạt | Đạt |
| 2 Database | 1 passed | Đạt | Đạt |
| 3 Auth/RBAC | 4 passed | Đạt | Đạt |
| 4 Core Features | 5 passed | Đạt | Đạt |
| 5 Review (`main`) | 5 passed | Đạt | Đạt |

## Giới hạn phạm vi

Ảnh không có mục 2 mô tả sample app gốc. TaskHub dùng domain Task Manager để
thực hiện các nội dung nhìn thấy. Background queue là tùy chọn, không triển khai.
Không có refresh-token/revocation, rate limiter, UI frontend hoặc email delivery.
Không coi các tính năng ngoài đề này là đã hoàn thành.
