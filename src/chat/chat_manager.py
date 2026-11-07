import threading
from typing import Any, Dict, List, Optional, Union


class ChatManager:
    """
    Quản lý trạng thái và lịch sử hội thoại trong ứng dụng LAN Chat.

    Lưu trữ danh sách hội thoại, số tin nhắn chưa đọc, socket kết nối TCP
    và quản lý peer đang được chọn để chat.
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
        - Trường hợp 1: Đang mở cuộc trò chuyện với người gửi (current_chat_peer == peer_id)
          -> Không tăng số lượng tin nhắn chưa đọc.
        - Trường hợp 2: Không mở cuộc trò chuyện với người gửi (current_chat_peer != peer_id)
          -> Tăng unread_counts[peer_id] lên 1.

        :param peer_id: ID của peer gửi tin nhắn, hoặc dict tin nhắn (khi gọi dạng callback).
        :param message: Dict tin nhắn chat (nếu peer_id là chuỗi ID).
        """
        with self._lock:
            # Hỗ trợ cả 2 dạng: handle_incoming_message(peer_id, message)
            # và handle_incoming_message(message)
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

            # Lưu tin nhắn vào lịch sử hội thoại của peer này
            if target_peer_id not in self.conversations:
                self.conversations[target_peer_id] = []
            self.conversations[target_peer_id].append(msg)

            # Đảm bảo trường unread_counts đã được khởi tạo
            if target_peer_id not in self.unread_counts:
                self.unread_counts[target_peer_id] = 0

            # Áp dụng quy tắc tin nhắn đến
            if self.current_chat_peer == target_peer_id:
                # Đang mở chat với peer này -> Không tăng số tin nhắn chưa đọc
                pass
            else:
                # Không mở chat với peer này -> Tăng lên 1
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
        """
        Lấy kết nối TCP socket đã lưu của một peer.

        :param peer_id: ID của peer.
        :param conn: (Tùy chọn) Tham số dự phòng.
        :return: Socket kết nối hoặc None.
        """
        with self._lock:
            return self.connections.get(str(peer_id))

    def add_connection(self, peer_id: str, conn: Any) -> None:
        """
        Lưu kết nối TCP socket với peer.

        :param peer_id: ID của peer.
        :param conn: TCP socket đã kết nối.
        """
        with self._lock:
            self.connections[str(peer_id)] = conn

    def remove_connection(self, peer_id: str) -> None:
        """
        Xóa kết nối TCP socket của một peer khỏi danh sách lưu trữ.

        :param peer_id: ID của peer cần xóa kết nối.
        """
        with self._lock:
            self.connections.pop(str(peer_id), None)

    def add_message(self, peer_id: str, message: Dict[str, Any]) -> None:
        """
        Lưu một tin nhắn gửi đi vào lịch sử hội thoại của peer tương ứng.

        :param peer_id: ID của peer đối tác trò chuyện.
        :param message: Dict tin nhắn chat.
        """
        with self._lock:
            p_id = str(peer_id)
            if p_id not in self.conversations:
                self.conversations[p_id] = []
            self.conversations[p_id].append(message)
