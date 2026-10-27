
# config.py

# ===== Network Discovery =====
DISCOVERY_PORT = 9999
## Khoảng thời gian giữa hai lần phát thông báo presence
BROADCAST_INTERVAL = 3
## Thời gian tối đa mà một peer có thể không gửi thông báo mới trước khi được xem là offline.
PEER_TIMEOUT = 10

# ===== TCP Communication =====
## Port TCP dùng để nhận kết nối chat
CHAT_PORT = 5000
## Port TCP dùng để nhận kết nối truyền file
FILE_PORT = 5001
## Thời gian chờ kết nối TCP, tính bằng giây
CONNECT_TIMEOUT = 5

# ===== Data Processing =====
BUFFER_SIZE = 4096
ENCODING = "utf-8"

# ===== File Sharing =====
MAX_FILE_SIZE = 100 * 1024 * 1024
## Là tên thư mục dùng để lưu các file được tải về.
DOWNLOAD_DIR = "downloads"

# ===== Message Configuration =====
MAX_MESSAGE_SIZE = 1024 * 1024