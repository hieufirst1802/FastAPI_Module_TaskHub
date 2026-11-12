# Bài 1 — Core Setup & Architecture

Nhánh: `codex/day1-core-setup`. Đây là một bài riêng, checkout và chạy trực tiếp từ thư mục gốc.

## Mục tiêu và phần đã hoàn thành


- FastAPI app factory, APIRouter, lifespan khởi tạo repository riêng cho mỗi app.
- Layered API → service → repository, Dependency Injection từ request.app.state.
- Pydantic v2, validation và CRUD Task trong bộ nhớ, mã lỗi 404/422.
- Thực hành: POST /api/tasks với {"title":"Học FastAPI"}; GET /api/tasks;
  PATCH /api/tasks/1 với {"completed":true}; DELETE /api/tasks/1.
- Dữ liệu mất khi khởi động lại; dùng một worker cho bài trong bộ nhớ.
- Không cần .env hay database ở bài này. Tests kiểm tra CRUD và dữ liệu tách theo app.


## Cài đặt và chạy (PowerShell)

```powershell
git switch codex/day1-core-setup
uv sync --locked
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
