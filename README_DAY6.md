# Day 6 – Redis Caching

## 1. Tổng quan

**Mục tiêu:** Tích hợp Redis Caching vào ứng dụng FastAPI TaskHub nhằm giảm các truy vấn không cần thiết đến cơ sở dữ liệu và cải thiện hiệu suất phản hồi của API.

Bản triển khai này mở rộng ứng dụng TaskHub hiện tại nhưng vẫn duy trì kiến trúc phân lớp:

`API → Service → Repository → Database`

Redis được tích hợp tại các tầng Service/Core với vai trò là một lớp bộ nhớ đệm (Cache) tùy chọn. PostgreSQL vẫn là nguồn dữ liệu chính (Source of Truth).

Yêu cầu trọng tâm của Day 6 là sử dụng Redis để Cache danh sách Task thuộc Project và vô hiệu hóa dữ liệu Cache khi có thay đổi liên quan.

## 2. Các tính năng

- Tìm hiểu các kiến thức cơ bản về Redis và các thao tác dữ liệu.
- Sử dụng Redis Async Client thông qua `redis.asyncio`.
- Quản lý kết nối và cấu hình Redis.
- Triển khai Cache-aside Pattern.
- Cấu hình TTL (Time To Live – thời gian tồn tại của Cache).
- Cache thông tin chi tiết Task.
- Cache danh sách Task theo Project.
- Vô hiệu hóa Cache sau khi các thao tác thay đổi dữ liệu thành công.
- Xử lý lỗi Redis và chuyển sang sử dụng Database khi cần thiết.
- Kiểm tra quyền truy cập và quyền sở hữu khi lấy dữ liệu từ Cache.
- Cấu hình Docker Compose cho Redis và PostgreSQL.

## 3. Cài đặt và khởi chạy

### Yêu cầu hệ thống

- Python >= 3.12
- uv
- Docker Desktop
- Redis 7
- PostgreSQL 16

### Cài đặt các thư viện phụ thuộc

```bash
uv sync --locked
```

### Cấu hình biến môi trường

Đối với Windows CMD:

```cmd
copy .env.example .env
```

Cập nhật các biến môi trường khi cần thiết, đặc biệt là `JWT_SECRET_KEY`.

### Khởi chạy các dịch vụ

```bash
docker compose up -d
```

### Chạy Database Migration

```bash
uv run alembic upgrade head
```

### Khởi chạy FastAPI

```bash
uv run uvicorn app.main:create_app --factory --reload
```

Tài liệu API:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## 4. Cấu hình Redis

Các biến môi trường sau được sử dụng để điều khiển hoạt động của Redis:

| Biến môi trường | Giá trị mặc định | Mô tả |
|---|---|---|
| REDIS_ENABLED | false | Bật hoặc tắt Redis Caching |
| REDIS_URL | redis://localhost:6379/0 | URL kết nối Redis |
| REDIS_CACHE_TTL | 60 | Thời gian hết hạn của Cache, tính bằng giây |
| REDIS_SOCKET_TIMEOUT | 0.2 | Thời gian chờ tối đa cho kết nối và thao tác Redis |
| REDIS_KEY_PREFIX | taskhub:v1 | Tiền tố namespace của Redis Key |

Có thể tắt Redis Caching bằng cách thiết lập:

```env
REDIS_ENABLED=false
```

Khi Redis bị tắt hoặc không khả dụng, ứng dụng vẫn tiếp tục hoạt động bằng cách sử dụng Database.

## 5. Kiến trúc Cache

### 5.1. Cache danh sách Task theo Project (Yêu cầu chính)

Theo đặc tả Sample App TaskHub, yêu cầu Caching trọng tâm là:

`GET /api/v1/projects/{id}/tasks`

Ứng dụng sử dụng Redis để Cache danh sách Task được trả về từ API này.

Quy trình Cache-aside:

1. Nhận yêu cầu lấy danh sách Task thuộc một Project.
2. Kiểm tra thông tin xác thực và quyền thành viên của người dùng trong Project/Workspace.
3. Tạo Cache Key dựa trên Project ID và các tham số truy vấn liên quan.
4. Kiểm tra dữ liệu trong Redis.
5. Nếu Cache Hit (có dữ liệu), trả về dữ liệu đã được Cache.
6. Nếu Cache Miss (không có dữ liệu), truy vấn Repository.
7. Lưu kết quả vào Redis kèm thời gian hết hạn (TTL).
8. Trả về danh sách Task cho API.

Thông tin thành viên và quyền truy cập được kiểm tra trước khi trả về dữ liệu Cache nhằm ngăn chặn truy cập trái phép.

Project Version Key được sử dụng để vô hiệu hóa các danh sách Task đã Cache trước đó khi dữ liệu Project liên quan thay đổi.

### 5.2. Cache thông tin chi tiết Task

Chi tiết Task độc lập được lưu trong Redis dưới dạng JSON. Chi tiết Task thuộc Project đọc database và kiểm tra quyền Workspace ở mỗi lần truy cập.

Định dạng Redis Key:

```text
taskhub:v1:tasks:{task_id}:standalone:{version}
```

Quy trình Cache-aside:

1. Kiểm tra Redis để tìm Task được yêu cầu.
2. Nếu Cache Hit, trả về dữ liệu đã Cache.
3. Nếu Cache Miss, truy vấn Repository.
4. Lưu kết quả vào Redis kèm TTL.
5. Trả về thông tin Task.

Các Task không tồn tại sẽ không được lưu vào Cache.

Quyền sở hữu Task và quyền Administrator luôn được kiểm tra độc lập với việc dữ liệu được lấy từ Cache hay Database.

### 5.3. Vô hiệu hóa Cache (Cache Invalidation)

Cơ chế vô hiệu hóa Cache giúp đảm bảo dữ liệu Cache không bị lỗi thời sau khi có thay đổi.

Các cơ chế được triển khai:

- Đổi phiên bản cache chi tiết sau khi database commit thành công. Lượt đọc chậm chỉ ghi vào key phiên bản cũ.
- Vô hiệu hóa Cache danh sách Task của Project sau các thay đổi liên quan đến Task trong Project.
- Giữ nguyên Cache hợp lệ nếu thao tác ghi dữ liệu vào Database thất bại.
- Sử dụng TTL để giới hạn thời gian tồn tại của dữ liệu Cache cũ.
- PostgreSQL luôn được duy trì là nguồn dữ liệu chính.

### 5.4. TTL (Time To Live)

Thời gian tồn tại mặc định của Cache là 60 giây.

TTL được cấu hình thông qua biến môi trường:

`REDIS_CACHE_TTL`

Redis sẽ tự động hết hạn các Cache Entry khi thời gian tồn tại được thiết lập kết thúc.

## 6. Xử lý lỗi và đảm bảo độ tin cậy

Redis được xem là một lớp Cache tùy chọn, không phải thành phần bắt buộc để ứng dụng hoạt động.

Ứng dụng sẽ chuyển sang sử dụng Database khi Redis gặp các lỗi:

- Lỗi kết nối (Connection Errors).
- Lỗi quá thời gian chờ (Operation Timeouts).
- Lỗi từ Redis Server.
- Dữ liệu Cache không hợp lệ hoặc bị hỏng.

Các cơ chế bảo vệ bổ sung:

- PostgreSQL luôn là nguồn dữ liệu chính.
- Password và Authentication Token không được lưu trong Cache.
- Quyền truy cập luôn được kiểm tra độc lập, kể cả khi dữ liệu được lấy từ Cache.
- Kết nối Redis được đóng khi ứng dụng tắt.
- Các thao tác Redis đều sử dụng cấu hình Timeout.
- Lỗi Redis không ngăn cản các thao tác Database thông thường.

Cache hoạt động theo cơ chế nhất quán ở mức Best-effort Consistency. Nếu thao tác vô hiệu hóa Cache thất bại, dữ liệu cũ có thể tiếp tục tồn tại cho đến khi TTL hết hạn.

## 7. Docker Compose

Dự án cung cấp cấu hình Docker Compose bao gồm các dịch vụ:

- FastAPI Application.
- PostgreSQL Database.
- Redis Server.

Khởi chạy các dịch vụ:

```bash
docker compose up -d
```

Kiểm tra trạng thái các dịch vụ:

```bash
docker compose ps
```

Kiểm tra kết nối Redis:

```bash
docker compose exec redis redis-cli ping
```

Kết quả mong đợi:

```text
PONG
```

Dừng các dịch vụ:

```bash
docker compose down
```

## 8. Kiểm thử (Testing)

Chạy toàn bộ bài kiểm thử:

```bash
uv run pytest -v
```

Kiểm tra chất lượng mã nguồn bằng Ruff:

```bash
uv run ruff check .
```

Kiểm tra lỗi khoảng trắng trong Git Diff:

```bash
git diff --check
```

### Phạm vi kiểm thử Day 6

Bộ kiểm thử bao gồm:

- Cache Hit và Cache Miss.
- TTL và cơ chế hết hạn Cache.
- Vô hiệu hóa Cache sau thao tác Update và Delete.
- Cache danh sách Task theo Project.
- Kiểm tra Cache Hit và thời gian hết hạn của Project Cache.
- Kiểm tra quyền sở hữu và quyền Administrator.
- Xử lý khi thao tác ghi Database thất bại.
- Xử lý Task không tồn tại.
- Xử lý lỗi kết nối Redis.
- Xử lý lỗi Timeout của Redis.
- Xử lý dữ liệu Cache bị hỏng hoặc không hợp lệ.
- Kiểm thử khi Redis Cache bị tắt.
- Kiểm thử API CRUD với Cache.
- Kiểm tra khả năng chuyển sang Database khi Redis gặp lỗi.

### Kết quả kiểm thử hiện tại

- **43 bài kiểm thử thành công**, gồm đường nâng cấp database từ Bài 2–5 và kiểm tra cấu hình JWT khi triển khai.
- **Ruff: All checks passed** – Không phát hiện lỗi từ Ruff.
- Còn một cảnh báo Deprecation liên quan đến Starlette/httpx.

Các bài kiểm thử hiện tại sử dụng Redis Client giả lập (Mock Redis Client). Vì vậy, kết quả này xác nhận hành vi Caching và xử lý lỗi nhưng chưa tự xác nhận việc tích hợp với Redis Server thực tế.

## 9. Các file quan trọng

| File | Chức năng |
|---|---|
| `app/core/cache.py` | Redis Cache Adapter và xử lý lỗi |
| `app/core/config.py` | Cấu hình Redis |
| `app/main.py` | Quản lý Application Lifespan và khởi tạo Cache |
| `app/services/task.py` | Triển khai Cache-aside và Cache Invalidation cho Task |
| `app/api/v1/endpoints/tasks.py` | Task API và Dependency Injection cho Cache |
| `app/schemas/workspace.py` | Schema phản hồi danh sách Task theo Project |
| `tests/test_day6.py` | Các bài kiểm thử Redis Caching |
| `tests/test_taskhub.py` | Kiểm thử tích hợp TaskHub và Project Cache |
| `compose.yaml` | Cấu hình các dịch vụ Docker Compose |
| `.env.example` | File mẫu cấu hình biến môi trường |

## 10. Kết luận

Day 6 triển khai cơ chế Redis Caching bất đồng bộ (Asynchronous Redis Caching) vào ứng dụng FastAPI TaskHub.

Bản triển khai đáp ứng yêu cầu Caching trọng tâm của đặc tả Sample App thông qua việc Cache danh sách Task thuộc Project tại API:

`GET /api/v1/projects/{id}/tasks`

Ngoài ra, hệ thống còn hỗ trợ Cache thông tin chi tiết Task, cấu hình TTL linh hoạt, vô hiệu hóa Cache, kiểm tra quyền truy cập và tự động chuyển sang PostgreSQL khi Redis không khả dụng.

Kiến trúc phân lớp và các quy tắc phân quyền hiện tại của ứng dụng vẫn được duy trì, trong khi Redis đóng vai trò là giải pháp tối ưu hiệu suất tùy chọn.
