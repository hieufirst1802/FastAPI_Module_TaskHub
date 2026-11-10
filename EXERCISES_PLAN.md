# Phương án chia 5 bài thực hành

Chia một repository thành đúng 5 nhánh theo ảnh GitHub đã xác nhận.

| Bài | Nhánh dự kiến | Nội dung | Sản phẩm |
| --- | --- | --- | --- |
| 1 | codex/day1-core-setup | Layered Architecture, FastAPI, APIRouter, lifespan, routing, DI, Pydantic v2 | App CRUD một resource trong bộ nhớ, README chạy và thử API |
| 2 | codex/day2-database | SQLAlchemy 2 async, User–Task relationship, BaseRepository[T], pagination, Alembic | CRUD lưu DB, migration upgrade/downgrade, README |
| 3 | codex/day3-auth-rbac | Password hashing, JWT, get_current_user, RBAC, ownership | Đăng ký/đăng nhập, member/admin, kiểm thử quyền |
| 4 | codex/day4-core-features | Middleware, exceptions, Redis, docs, settings, logging, Docker tùy chọn | App tích hợp, cấu hình môi trường, README Compose |
| 5 | main | Review, DRY, Ruff, mypy, kiểm thử, performance review | Bản hoàn chỉnh, báo cáo kiểm tra và hướng dẫn |

Mỗi nhánh là một bài có thể checkout và chạy độc lập; bài sau mở rộng bài trước.
`main` là bài 5 và trang giới thiệu, không thêm một nhánh bài 5 trùng lặp.
Các tên day1–day4 là số bài/mốc triển khai, không phải toàn bộ 8 ngày của giáo trình.
