# Bài 3 — Authentication, RBAC & Ownership

Nhánh: `codex/day3-auth-rbac`. Đây là một bài riêng, checkout và chạy trực tiếp từ thư mục gốc.

## Mục tiêu và phần đã hoàn thành


- Argon2 password hashing, OAuth2 password form, JWT HS256 có sub/iat/exp.
- Dependency get_current_user đọc User từ DB; role member/admin, service kiểm tra owner.
- POST /api/auth/register: {"username":"alice","password":"Password123!"}.
- POST /api/auth/token: form username/password; dùng Authorize trong Swagger.
- Member chỉ nhìn thấy task của mình; đọc/sửa/xóa task người khác trả 404.
- GET /api/users/me; GET /api/admin/users chỉ admin, member nhận 403.
- Tạo admin: `uv run python -m app.cli administrator`, nhập mật khẩu tại prompt.
- Tests kiểm tra credentials sai, JWT hết hạn, ownership, RBAC, admin và validation.
- Ảnh đề không có mục 2 sample app gốc; Task Manager là domain được chọn để thực hành.


## Cài đặt và chạy (PowerShell)

```powershell
git switch codex/day3-auth-rbac
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
`main` là bài 5, bốn nhánh `codex/day*` là bài 1–4, tổng đúng 5 nhánh.
Tên day là mốc bài thực hành, không có nghĩa giáo trình chỉ có 5 ngày.
