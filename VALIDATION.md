# Kết quả xác nhận – 17/11/2026

- Python 3.14.7 trên Windows; dự án khai báo Python >= 3.12.
- `pytest -q`: 36 tests passed. Có một deprecation warning có sẵn từ Starlette TestClient/httpx.
- `ruff check .`: passed.
- `mypy`: strict passed, 43 source files.
- `git diff --check`: passed.
- `docker compose config --quiet`: passed.
- Alembic upgrade/downgrade/upgrade trên SQLite có user/task cũ: passed; dữ liệu cũ được giữ và status backfill đúng.
- `alembic check`: No new upgrade operations detected.
- Database local đã backup tại `.exercise-build/backups/tasks_before_workspace_20261117.db`, sau đó upgrade đến `4a37d57500de`. Giữ 2 users/1 task; `PRAGMA foreign_key_check` không có lỗi.

Kiểm thử bao gồm auth/RBAC cũ, middleware/exception, Redis cache-aside/TTL/lỗi kết nối/dữ liệu hỏng, refresh rotation và request đồng thời, logout/password revocation, inactive user, profile và email unique, quyền Workspace, membership removal/downgrade khi cache còn dữ liệu, assignee, archive, task filtering/pagination, label/comment isolation và xóa dữ liệu con.

Giới hạn: database tests dùng SQLite, cache tests dùng Redis giả với đồng hồ điều khiển được. Docker Engine đang tắt nên chưa chạy Docker build hoặc tích hợp PostgreSQL/Redis server thật. Migration có nhánh batch recreate riêng cho SQLite; nhánh ALTER TABLE PostgreSQL chưa được kiểm thử runtime. Chưa triển khai email/background notification.

ZIP loại trừ database/backup cục bộ, .env, .git, virtualenv, cache và ảnh tài liệu tham chiếu. Bao gồm source, migrations, tests, lockfile, Dockerfile/Compose, tài liệu và cấu hình mẫu. Chạy `python tools/package_source.py` để đóng gói lại và kiểm tra checksum từng file trong ZIP.
