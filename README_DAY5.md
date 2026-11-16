# Day 5 – Middleware & Exception Handling

Gói này chứa các file cần thêm/thay thế trên branch `lesson-5-middleware-exceptions`, dựa trên branch Day 4 `lesson-4-authorization`.

## Nội dung

- Request logging middleware: log method, path, status code và thời gian xử lý.
- Response header `X-Process-Time` (đơn vị giây).
- Custom base exception và `UsernameAlreadyExistsError`.
- Exception handlers cho lỗi nghiệp vụ, validation, HTTP và lỗi không dự kiến.
- Test riêng cho middleware và exception handlers.

## Cách áp dụng

1. Tạo/chuyển sang branch Day 5 dựa trên commit Day 4.
2. Giải nén ZIP vào thư mục gốc repository, giữ nguyên cấu trúc thư mục.
3. Cho phép ghi đè các file trùng tên trong gói. Gói này chỉ chứa các file Day 5 cần thêm hoặc thay thế.
4. Chạy:

```cmd
uv run ruff check .
uv run pytest -v
git diff --check
```

5. Chỉ commit sau khi kiểm tra toàn bộ diff và test thành công.

## Các file trong gói

### Thêm mới
- `app/core/exceptions.py`
- `app/core/exception_handlers.py`
- `app/middleware/__init__.py`
- `app/middleware/request_logging.py`
- `tests/test_day5.py`

### Thay thế
- `app/main.py`
- `app/services/auth.py`
- `app/api/v1/endpoints/auth.py`

## Error response mẫu

Lỗi validation:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed",
    "details": []
  }
}
```

Lỗi nghiệp vụ trùng username:

```json
{
  "error": {
    "code": "username_already_exists",
    "message": "Username already registered"
  }
}
```

Lỗi server không dự kiến không tiết lộ chi tiết nội bộ cho client.
