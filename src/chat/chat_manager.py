import socket
import threading
import time
from typing import Any, Dict, List, Optional, Union

from common.message import decode_message, encode_message


class ChatManager:
    """
    Quản lý trạng thái và lịch sử hội thoại trong ứng dụng LAN Chat.

    Lưu trữ danh sách hội thoại, số tin nhắn chưa đọc, socket kết nối TCP,
    quản lý peer đang được chọn để chat và thông báo gửi nhận file.
    """

    def __init__(self, self_peer_id: str, peer_manager: Optional[Any] = None):
        """
        Khởi tạo ChatManager.

        :param self_peer_id: ID của peer hiện tại (chuỗi định danh máy cục bộ).
        :param peer_manager: Đối tượng PeerManager quản lý danh sách peer trong mạng LAN.
        """
        self.self_peer_id = str(self_peer_id)
        self.peer_manager = peer_manager
        self.conversations: Dict[str, List[Dict[str, Any]]] = {}
        self.current_chat_peer: Optional[str] = None
        self.unread_counts: Dict[str, int] = {}
        self.connections: Dict[str, Any] = {}
        self._lock = threading.RLock()

        # Quản lý thông báo truyền file
        self.file_notifications: Dict[str, List[Dict[str, Any]]] = {}
        self.file_notification_lock = threading.RLock()
        self.file_manager: Optional[Any] = None

    def set_file_manager(self, file_manager: Any) -> None:
        """Inject FileManager dependency."""
        with self._lock:
            self.file_manager = file_manager

    def select_chat_peer(self, peer_id: Optional[str]) -> None:
        """
        Đặt peer được chọn làm đối tác chat hiện tại.

        :param peer_id: ID của peer cần trò chuyện (hoặc None khi đóng/thoát phiên chat).
        """
        with self._lock:
            self.current_chat_peer = str(peer_id) if peer_id is not None else None

    def handle_incoming_message(
        self, peer_id: Any, message: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Xử lý tin nhắn đến và quyết định có tăng số lượng tin nhắn chưa đọc hay không.

        Quy tắc:
        - Nếu message là thông báo file -> chuyển tới handle_file_notification.
        - Trường hợp 1: Đang mở cuộc trò chuyện với người gửi (current_chat_peer == peer_id)
          -> Không tăng số lượng tin nhắn chưa đọc.
        - Trường hợp 2: Không mở cuộc trò chuyện với người gửi (current_chat_peer != peer_id)
          -> Tăng unread_counts[peer_id] lên 1.

        :param peer_id: ID của peer gửi tin nhắn, hoặc dict tin nhắn (khi gọi dạng callback).
        :param message: Dict tin nhắn chat (nếu peer_id là chuỗi ID).
        """
        with self._lock:
            if message is None and isinstance(peer_id, dict):
                msg = peer_id
                sender_id = msg.get("sender_id")
                if not sender_id:
                    return
                target_peer_id = str(sender_id)
            else:
                target_peer_id = str(peer_id) if peer_id is not None else ""
                msg = message if isinstance(message, dict) else {}

            if not target_peer_id:
                return

            # Kiểm tra nếu là thông điệp liên quan đến file notification
            msg_type = msg.get("type", "")
            if "file" in msg_type and (
                "request" in msg_type or "respon" in msg_type or "notification" in msg_type
            ):
                self.handle_file_notification(msg)
                return

            # Lưu tin nhắn vào lịch sử hội thoại của peer này
            if target_peer_id not in self.conversations:
                self.conversations[target_peer_id] = []
            self.conversations[target_peer_id].append(msg)

            # Đảm bảo trường unread_counts đã được khởi tạo
            if target_peer_id not in self.unread_counts:
                self.unread_counts[target_peer_id] = 0

            # Áp dụng quy tắc tin nhắn đến
            if self.current_chat_peer == target_peer_id:
                pass
            else:
                self.unread_counts[target_peer_id] += 1

    def get_unread_count(self, peer_id: Optional[str] = None) -> Any:
        """
        Trả về số tin nhắn chưa đọc của một peer (kiểu int).
        Nếu không truyền peer_id (None), trả về toàn bộ dictionary unread_counts.

        :param peer_id: (Tùy chọn) ID của peer cần lấy số tin nhắn chưa đọc.
        :return: int số tin nhắn chưa đọc của peer; hoặc dict toàn bộ unread_counts.
        """
        with self._lock:
            if peer_id is None:
                return self.unread_counts.copy()
            return int(self.unread_counts.get(str(peer_id), 0))

    def mark_messages_as_read(self, peer_id: str) -> None:
        """
        Đánh dấu tin nhắn đã đọc và cập nhật số lượng chưa đọc về 0.

        :param peer_id: ID của peer cần đánh dấu đã đọc.
        """
        with self._lock:
            self.unread_counts[str(peer_id)] = 0

    def get_messages(self, peer_id: str) -> List[Dict[str, Any]]:
        """
        Lấy lịch sử trò chuyện với một peer.

        :param peer_id: ID của đối tác chat.
        :return: Danh sách các tin nhắn trong cuộc trò chuyện (list[dict]).
        """
        with self._lock:
            messages = self.conversations.get(str(peer_id), [])
            return [msg.copy() for msg in messages]

    # Alias để hỗ trợ tương thích mã nguồn gọi get_message
    get_message = get_messages

    # ==========================================
    # QUẢN LÝ KẾT NỐI VÀ TIN NHẮN BỔ TRỢ
    # ==========================================

    def get_connection(self, peer_id: str, conn: Any = None) -> Any:
        """Lấy kết nối TCP socket đã lưu của một peer."""
        with self._lock:
            return self.connections.get(str(peer_id))

    def add_connection(self, peer_id: str, conn: Any) -> None:
        """Lưu kết nối TCP socket với peer."""
        with self._lock:
            self.connections[str(peer_id)] = conn

    def remove_connection(self, peer_id: str) -> None:
        """Xóa kết nối TCP socket của một peer khỏi danh sách lưu trữ."""
        with self._lock:
            self.connections.pop(str(peer_id), None)

    def add_message(self, peer_id: str, message: Dict[str, Any]) -> None:
        """Lưu một tin nhắn gửi đi vào lịch sử hội thoại của peer tương ứng."""
        with self._lock:
            p_id = str(peer_id)
            if p_id not in self.conversations:
                self.conversations[p_id] = []
            self.conversations[p_id].append(message)

    # ======================================================
    # QUẢN LÝ VÀ GỬI/NHẬN FILE NOTIFICATION QUA CHAT TCP
    # ======================================================

    def send_file_request(self, peer_id: str, file_request: dict) -> bool:
        """
        Gửi file_notification_request (file_request + trạng thái pending) thông báo
        muốn gửi file qua Chat TCP. Lưu notification vào file_notifications.
        """
        if not isinstance(file_request, dict):
            return False

        transfer_id = file_request.get("transfer_id")
        filename = file_request.get("filename")
        filesize = file_request.get("filesize")
        file_hash = file_request.get("file_hash") or file_request.get("filehash", "")

        notification = {
            "type": "file_notification_request",
            "transfer_id": str(transfer_id),
            "sender_id": str(file_request.get("sender_id", self.self_peer_id)),
            "receiver_id": str(peer_id),
            "filename": str(filename),
            "filesize": int(filesize) if filesize is not None else 0,
            "file_hash": str(file_hash),
            "timestamp": file_request.get("timestamp", time.time()),
            "status": "pending",
        }

        with self.file_notification_lock:
            p_id = str(peer_id)
            if p_id not in self.file_notifications:
                self.file_notifications[p_id] = []
            self.file_notifications[p_id].append(notification)

        conn = self.get_connection(peer_id)
        if conn is not None:
            try:
                data = encode_message(notification) + b"\n"
                conn.sendall(data)
                return True
            except OSError:
                pass

        if self.peer_manager is not None:
            peer = self.peer_manager.get_peer(peer_id)
            if peer and "ip" in peer and "tcp_port" in peer:
                try:
                    sock = socket.create_connection((peer["ip"], peer["tcp_port"]), timeout=5)
                    data = encode_message(notification) + b"\n"
                    sock.sendall(data)
                    self.add_connection(peer_id, sock)
                    return True
                except OSError:
                    pass

        return False

    def send_file_response(self, peer_id: str, file_notification: dict) -> bool:
        """
        Gửi file_notification_response (cập nhật lại trạng thái accept/reject)
        thông báo có nhận file hay không qua Chat TCP.
        """
        if not isinstance(file_notification, dict):
            return False

        transfer_id = str(file_notification.get("transfer_id", ""))
        status = str(file_notification.get("status", "accept"))

        response_msg = {
            "type": "file_notification_respone",
            "transfer_id": transfer_id,
            "sender_id": self.self_peer_id,
            "receiver_id": str(peer_id),
            "filename": file_notification.get("filename", ""),
            "filesize": file_notification.get("filesize", 0),
            "file_port": file_notification.get("file_port"),
            "timestamp": time.time(),
            "status": status,
        }

        with self.file_notification_lock:
            p_id = str(peer_id)
            if p_id not in self.file_notifications:
                self.file_notifications[p_id] = []
            self.file_notifications[p_id].append(response_msg)

            for notif in self.file_notifications[p_id]:
                if notif.get("transfer_id") == transfer_id:
                    notif["status"] = status

        conn = self.get_connection(peer_id)
        if conn is not None:
            try:
                data = encode_message(response_msg) + b"\n"
                conn.sendall(data)
                return True
            except OSError:
                pass

        if self.peer_manager is not None:
            peer = self.peer_manager.get_peer(peer_id)
            if peer and "ip" in peer and "tcp_port" in peer:
                try:
                    sock = socket.create_connection((peer["ip"], peer["tcp_port"]), timeout=5)
                    data = encode_message(response_msg) + b"\n"
                    sock.sendall(data)
                    self.add_connection(peer_id, sock)
                    return True
                except OSError:
                    pass

        return False

    def receive_file_notification(
        self, conn: Any, transfer_id: Optional[str] = None, notification_type: Optional[str] = None
    ) -> Optional[dict]:
        """Nhận message có chọn lọc qua Chat TCP."""
        if conn is None:
            return None

        buffer = b""
        try:
            while True:
                data = conn.recv(4096)
                if not data:
                    break
                buffer += data
                while b"\n" in buffer:
                    raw_message, buffer = buffer.split(b"\n", 1)
                    if not raw_message:
                        continue
                    try:
                        msg = decode_message(raw_message)
                        if transfer_id and msg.get("transfer_id") != transfer_id:
                            continue
                        if notification_type and msg.get("type") != notification_type:
                            continue
                        return msg
                    except Exception:
                        continue
        except OSError:
            pass
        return None

    def handle_file_notification(self, notification: dict) -> bool:
        """Phân loại và chuyển tiếp thông báo file lên UI hoặc FileManager."""
        if not isinstance(notification, dict):
            return False

        msg_type = notification.get("type", "")
        transfer_id = notification.get("transfer_id")
        if not transfer_id:
            return False

        sender_id = notification.get("sender_id")
        receiver_id = notification.get("receiver_id")
        peer_id = sender_id if sender_id != self.self_peer_id else receiver_id
        if not peer_id:
            peer_id = sender_id or receiver_id or "unknown"

        with self.file_notification_lock:
            p_id = str(peer_id)
            if p_id not in self.file_notifications:
                self.file_notifications[p_id] = []

            existing = None
            for n in self.file_notifications[p_id]:
                if n.get("transfer_id") == transfer_id:
                    existing = n
                    break

            if existing is not None:
                existing.update(notification)
            else:
                self.file_notifications[p_id].append(notification.copy())

        # Chuyển tiếp tới FileManager nếu có
        if self.file_manager is not None:
            if msg_type in ("file_notification_request", "file_request"):
                try:
                    self.file_manager.receive_file(notification)
                except Exception:
                    pass
            elif msg_type in (
                "file_notification_respone",
                "file_notification_response",
                "file_response",
            ):
                try:
                    self.file_manager.handle_notification(notification)
                except Exception:
                    pass

        return True

    def update_status_respone(self, transfer_id: str, status: str) -> bool:
        """Đổi trạng thái của file_notification_respone khi user nhập."""
        with self.file_notification_lock:
            for notifications in self.file_notifications.values():
                for notif in notifications:
                    if notif.get("transfer_id") == transfer_id:
                        notif["status"] = status
                        return True
        return False

    update_status_response = update_status_respone

    def update_status_request(self, transfer_id: str, status: Optional[str] = None) -> bool:
        """Cập nhật file_notification_request status theo respone tương ứng mà receive_file_notification() nhận được qua TCP."""
        with self.file_notification_lock:
            target_status = status
            if target_status is None:
                for notifs in self.file_notifications.values():
                    for n in notifs:
                        if n.get("transfer_id") == transfer_id and "respon" in n.get("type", ""):
                            target_status = n.get("status")
                            break
                    if target_status is not None:
                        break

            for notifications in self.file_notifications.values():
                for notif in notifications:
                    if notif.get("transfer_id") == transfer_id:
                        if target_status is not None:
                            notif["status"] = target_status
                        return True
        return False

    def get_file_notifications(self, peer_id: str) -> list:
        """Lấy danh sách thông báo file trong cuộc hội thoại với peer."""
        with self.file_notification_lock:
            return [n.copy() for n in self.file_notifications.get(str(peer_id), [])]

    def get_pending_file_notifications(self) -> list:
        """Lấy toàn bộ yêu cầu nhận file đang chờ xác nhận."""
        with self.file_notification_lock:
            pending = []
            for notifications in self.file_notifications.values():
                for notif in notifications:
                    if notif.get("status") == "pending":
                        pending.append(notif.copy())
            return pending
