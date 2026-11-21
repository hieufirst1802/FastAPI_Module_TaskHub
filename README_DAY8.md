# Bài 8 – Rà soát, refactor và tối ưu TaskHub

## Kiến trúc và vận hành

Các endpoint xác thực và Workspace dùng `/api/v1`. Router xử lý HTTP, service áp dụng quyền và nghiệp vụ, repository truy vấn database. Lifespan quản lý kết nối SQLAlchemy và Redis. Docker Compose chạy API, PostgreSQL 16 và Redis 7. Hướng dẫn cài đặt, thiết lập biến môi trường và thử Swagger nằm trong [README](README.md).

Các đường nâng cấp Alembic từ Bài 2 và Bài 3–5 có test giữ dữ liệu task. PostgreSQL trên Docker Compose đã được thử cài mới, nâng từ Bài 5 và mở lại database đã ở Bài 6. Production và staging yêu cầu JWT secret riêng, tối thiểu 32 ký tự.

## Thay đổi hiệu năng

Băm và kiểm tra mật khẩu bằng Argon2 chạy trong thread pool của Starlette để tránh chiếm event loop khi đăng ký, đăng nhập hoặc đổi mật khẩu. Test mới xác nhận bước kiểm tra mật khẩu chạy ở thread khác với event loop. Luồng nghiệp vụ và định dạng token giữ nguyên.

Danh sách task giới hạn 100 mục mỗi trang, sắp xếp theo ID và dùng Redis cho truy vấn lặp lại. Truy vấn tìm theo chuỗi con, đếm tổng số kết quả và phân trang với offset lớn vẫn có thể tốn thời gian trên tập dữ liệu lớn. Chưa đo tải đồng thời, latency hoặc mức dùng bộ nhớ của Argon2 trên môi trường triển khai.

## Kiểm tra chất lượng

Workflow **TaskHub quality** chạy trên pull request và lần push vào `main`. Có thể chạy cùng các kiểm tra ở local:

```powershell
uv sync --locked
uv run --locked ruff check .
uv run --locked mypy
uv run --locked pytest -q
docker compose config --quiet
```

Bộ test dùng SQLite và trình mô phỏng Redis để kiểm tra CRUD, phân quyền, token rotation, invalidation, tìm kiếm và OpenAPI. Lần thử trên Docker thật đã xác nhận API chạy với PostgreSQL, Redis lưu và thay phiên bản trang cache, và Swagger gửi Bearer JWT.

## Phạm vi còn lại

Email thông báo khi giao task chưa được triển khai. Client từ Bài 2–5 cần cập nhật URL task độc lập và danh sách user theo hướng dẫn nâng cấp trong README.
