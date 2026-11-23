# Bài 7 – Tìm kiếm, lọc, phân trang và Redis cache

## API danh sách task

| API | Tìm kiếm và lọc | Phân trang |
|---|---|---|
| `GET /api/v1/projects/{pid}/tasks` | `search`, `status`, `priority`, `assignee_id` | `page` từ 1, `limit` mặc định 20 |
| `GET /api/tasks` | `search`, `completed` | `offset` từ 0 đến 10.000, `limit` mặc định 20 |

- `search` tìm một phần của tiêu đề hoặc mô tả, không phân biệt hoa thường theo quy tắc của database. API bỏ khoảng trắng hai đầu và giới hạn từ khóa ở 200 ký tự. Chuỗi rỗng tương đương bỏ qua tìm kiếm. Ký tự `%` và `_` được tìm theo nghĩa đen. Khi nhập URL, dùng `%25` cho ký tự `%`.
- Với task Project, `status` nhận `TODO`, `IN_PROGRESS`, `IN_REVIEW`, `DONE`. `priority` nhận `LOW`, `MEDIUM`, `HIGH`, `URGENT`. `assignee_id` phải là số nguyên dương.
- Task phải thỏa mọi bộ lọc đã gửi. Kết quả sắp xếp theo ID tăng dần. `total` đếm tất cả kết quả sau lọc, trước phân trang. Trang vượt quá số kết quả trả `items: []` và giữ `total`. `limit` từ 1 đến 100.
- Danh sách Project trả `{items, total, page, limit}`. Danh sách độc lập trả `{items, total, offset, limit}`. Tham số không được hỗ trợ, sai định dạng hoặc ngoài phạm vi trả HTTP 422.

Đăng nhập và gửi access token dưới dạng Bearer token. Có thể thử hai URL sau trong Swagger UI tại `/docs`:

```text
GET /api/v1/projects/1/tasks?search=release&status=TODO&priority=HIGH&assignee_id=2&page=1&limit=10
GET /api/tasks?search=release&completed=false&offset=0&limit=10
```

## Redis cache

Bật `REDIS_ENABLED=true` để dùng Redis. `REDIS_CACHE_TTL` mặc định là 60 giây. Mỗi trang cache có khóa gồm phạm vi, phiên bản dữ liệu và mã băm của các tham số truy vấn. Khi cache trống, hết hạn hoặc Redis không khả dụng, API truy vấn database.

API Project kiểm tra quyền Workspace trước khi đọc cache. API task độc lập dùng phạm vi theo ID người dùng cho thành viên và phạm vi toàn bộ task độc lập cho admin. Sau khi tạo, sửa hoặc xóa task độc lập thành công, ứng dụng đổi phiên bản của chủ sở hữu task và của danh sách admin. Thay đổi task Project đổi phiên bản danh sách của Project tương ứng. Các trang cũ tự hết hạn theo TTL. Nếu Redis gặp lỗi lúc đổi phiên bản, trang cũ có thể còn được đọc đến khi hết TTL.

Khi cache miss, tìm chuỗi con trên tiêu đề hoặc mô tả có thể quét nhiều dòng do ký tự đại diện ở đầu mẫu tìm kiếm. Truy vấn cũng chạy `COUNT(*)` để tính `total`. Với dữ liệu PostgreSQL lớn, có thể đo bằng `EXPLAIN ANALYZE` và cân nhắc chỉ mục GIN với `pg_trgm` trên các cột `title` và `description` mà truy vấn `ILIKE` sử dụng. [Tài liệu PostgreSQL về pg_trgm](https://www.postgresql.org/docs/current/pgtrgm.html#PGTRGM-INDEX)

Bài 7 dùng schema database hiện tại.
