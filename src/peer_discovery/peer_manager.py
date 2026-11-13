import time
import threading
from typing import Any, Dict, List, Optional


class PeerManager:
    """
    Quản lý danh sách các peer (máy tính) được phát hiện trong mạng LAN
    thông qua giao thức UDP presence discovery.
    """

    def __init__(self, self_peer_id: str, username: str, tcp_port: int):
        """
        Khởi tạo trình quản lý peer.

        :param self_peer_id: ID duy nhất của chính máy đang chạy chương trình.
        """
        self.self_peer_id = str(self_peer_id)
        self.username = username
        self.status = "online"
        self.tcp_port = tcp_port

        self.peers: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()

    def init(self, self_peer_id: str, username: str, tcp_port: int) -> None:
      #  print("[DEBUG] PeerManager.init() called")
        """
        Khởi tạo hoặc cài đặt lại trình quản lý peer với self_peer_id mới.
        """
        with self._lock:
            self.self_peer_id = str(self_peer_id)
            self.username = username
            self.tcp_port = tcp_port
            self.status = "online"
            self.peers = {}

    def set_user_name(self, new_username: str):
        self.username = new_username

    def set_status(self, status: str) -> bool:
        """
        Cập nhật trạng thái của chính mình.

        :param status: online, away hoặc offline.
        :return: True nếu cập nhật thành công.
        """
        valid_statuses = {"online", "away"}

        if status not in valid_statuses:
            return False

        with self._lock:
      #      print("SET_STATUS ID:", id(self))
      #      print("Old status:", self.status)
            self.status = status
      #      print("New status:", self.status)

        return True

    def update_peer(self, message: dict, source_ip: str) -> bool:
        """
        Thêm peer mới hoặc cập nhật peer đã tồn tại; bỏ qua chính mình.
        Cập nhật last_seen mỗi khi nhận thông điệp hợp lệ.

        Format lưu trữ của peer:
        {
            "peer_id": str,
            "username": str,
            "ip": str,
            "tcp_port": int,
            "status": str,
            "last_seen": float
        }

        :param message: Dictionary thông điệp presence nhận từ UDP.
        :param source_ip: Địa chỉ IP nguồn (sender IP) từ UDP socket.
        :return: True nếu đã thêm/cập nhật thành công; False nếu bỏ qua hoặc không hợp lệ.
        """
        if not isinstance(message, dict):
            return False

        peer_id = message.get("peer_id")
        if not peer_id or not isinstance(peer_id, str):
            return False

        # Bỏ qua chính mình
        if peer_id == self.self_peer_id:
            return False

        username = message.get("username", "")
        tcp_port = message.get("tcp_port")
        status = message.get("status", "online")
        current_time = time.time()

        peer_data = {
            "peer_id": peer_id,
            "username": username,
            "ip": source_ip,
            "tcp_port": tcp_port,
            "status": status,
            "last_seen": current_time,
        }

        with self._lock:
            self.peers[peer_id] = peer_data
        return True

    def get_peer(self, peer_id: str) -> Optional[Dict[str, Any]]:
        """
        Lấy thông tin của một peer theo peer_id.

        :param peer_id: ID của peer cần lấy.
        :return: Dictionary thông tin peer hoặc None nếu không tồn tại.
        """
        with self._lock:
            peer = self.peers.get(peer_id)
            return peer.copy() if peer is not None else None

    def get_all_peers(self) -> List[Dict[str, Any]]:
        """
        Lấy danh sách tất cả các peer đã phát hiện.

        :return: Danh sách (list) các dictionary thông tin peer.
        """
        with self._lock:
            return [peer.copy() for peer in self.peers.values()]

    def get_online_peers(self, timeout: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        Lấy danh sách các peer đang có trạng thái online.

        :param timeout: (Tùy chọn) Thời gian timeout tính bằng giây. Nếu được chỉ định,
                        peer chỉ được coi là online nếu status == 'online' và
                        (thời gian hiện tại - last_seen) <= timeout.
                        Nếu không chỉ định (None), chỉ kiểm tra status == 'online'.
        :return: Danh sách các dictionary thông tin peer đang online.
        """
        with self._lock:
            now = time.time()
            online_peers = []
            for peer in self.peers.values():
                if peer.get("status") != "online":
                    continue
                if timeout is not None:
                    last_seen = peer.get("last_seen", 0.0)
                    if (now - last_seen) > timeout:
                        continue
                online_peers.append(peer.copy())
            return online_peers

    def get_away_peers(self, timeout: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        Lấy danh sách các peer có status = 'away'.

        :param timeout: (Tùy chọn) Thời gian timeout tính bằng giây. Nếu được chỉ định,
                        peer chỉ được coi là away nếu status == 'away' và
                        (thời gian hiện tại - last_seen) <= timeout.
                        Nếu không chỉ định (None), chỉ kiểm tra status == 'away'.
        :return: Danh sách (list) các dictionary thông tin peer có status == 'away'.
        """
        with self._lock:
            now = time.time()
            away_peers = []
            for peer in self.peers.values():
                if peer.get("status") != "away":
                    continue
                if timeout is not None:
                    last_seen = peer.get("last_seen", 0.0)
                    if (now - last_seen) > timeout:
                        continue
                away_peers.append(peer.copy())
            return away_peers

    def cleanup_inactive_peers(self, timeout: float = 10) -> None:
        """
        Đánh dấu peer là offline nếu thời gian không hoạt động vượt quá timeout.

        :param timeout: Thời gian không hoạt động tối đa tính bằng giây trước khi
                        được đánh dấu offline (mặc định: 10 giây).
        :return: None
        """
        with self._lock:
            now = time.time()
            for peer in self.peers.values():
                last_seen = peer.get("last_seen", 0.0)
                if (now - last_seen) > timeout:
                    peer["status"] = "offline"

    def remove_peer(self, peer_id: str) -> bool:
        """
        Xóa một peer khỏi danh sách khi cần.

        :param peer_id: ID của peer cần xóa.
        :return: True nếu xóa thành công, False nếu peer không tồn tại.
        """
        with self._lock:
            if peer_id in self.peers:
                del self.peers[peer_id]
                return True
            return False

    def clear(self) -> None:
        """Xóa toàn bộ danh sách peer."""
        with self._lock:
            self.peers.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self.peers)

    def __contains__(self, peer_id: str) -> bool:
        with self._lock:
            return peer_id in self.peers

    def __repr__(self) -> str:
        with self._lock:
            return f"PeerManager(self_peer_id={self.self_peer_id!r}, peers_count={len(self.peers)})"
