import threading
import queue

class FileManager:

    def __init__(self, peer_manager):
        self.peer_manager = peer_manager

        # Quản lý các phiên truyền file
        self.active_transfers = []
        self.completed_transfers = []

        # Lưu thông tin và trạng thái tất cả transfer
        self.transfers = []

        # Đồng bộ dữ liệu giữa các thread
        self.lock = threading.Lock()

        # Quản lý các worker thread
        self.transfer_threads = []

        # Hàng đợi yêu cầu nhận file
        self.file_request_queue = queue.Queue()

    def handle_incoming_connection(self, conn, addr):
        """
        Tiếp nhận kết nối TCP từ FileServer,
        xác thực transfer và chuyển socket cho FileReceiver.
        """
        pass

    def create_file_request(self, peer_id, file_path) -> dict:
        """
        Nhiệm vụ:
            1. Sinh transfer_id.
            2. Tạo file request bằng file_message.create_file_request().
            3. Đăng ký transfer vào active_transfers với trạng thái pending.
            4. Trả về notification để ChatManager gửi qua Chat TCP.
        """
        pass

    def send_file(self, file_notification: dict):
        # gọi register với direction = "send"
        pass

    def receive_file(self, file_notification: dict):
        # gọi register với direction = "receive"
        pass

    def handle_notification(self, file_notification: dict):
        """ 
        Nhận notification handshake từ ChatManager và xử lý
        1. Accept -> send_file / receive_file tùy loại notification
        2. Reject/ expired -> pop request
        """
        pass

    def get_transfer_status(self, transfer_id):
        pass

    def cancel_transfer(self, transfer_id):
        """Yêu cầu worker dừng transfer thông qua Event. Hủy khi truyền thất bại hoặc quá hạn"""
        pass

    def update_transfer_status(
        self,
        transfer_id: str,
        status: str
    ) -> bool:
        pass

    def get_transfer(self, transfer_id: str):
        pass

    def register_transfer(self, request: dict, direction) -> bool:
        """Đăng ký một phiên truyền file."""
        # Chỉ direction = receive mới được đưa vào queue.
        pass

    def accept_file(self, transfer_id):
        pass

    def reject_file(self, transfer_id):
        pass