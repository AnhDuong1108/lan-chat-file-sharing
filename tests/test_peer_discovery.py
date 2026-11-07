import os
import sys
import time
import unittest

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Đảm bảo đường dẫn src nằm trong sys.path
SRC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from peer_discovery.peer_manager import PeerManager
from peer_discovery.presense_message import create_presence_message, validate_presence_message
from peer_discovery.listen import process_received_message
from common.message import encode_message
import main


class TestPeerManager(unittest.TestCase):
    """Kiểm thử các chức năng của PeerManager theo yêu cầu."""

    def setUp(self):
        self.self_id = "pc-local-001"
        self.manager = PeerManager(self.self_id)

    def test_01_add_new_peer_success(self):
        """Yêu cầu: Thêm peer mới thành công."""
        msg = {
            "type": "presence",
            "peer_id": "pc-an-001",
            "username": "An",
            "tcp_port": 5000,
            "status": "online",
        }
        source_ip = "192.168.1.102"
        success = self.manager.update_peer(msg, source_ip)

        self.assertTrue(success)
        peer = self.manager.get_peer("pc-an-001")
        self.assertIsNotNone(peer)
        self.assertEqual(peer["peer_id"], "pc-an-001")
        self.assertEqual(peer["username"], "An")
        self.assertEqual(peer["ip"], source_ip)
        self.assertEqual(peer["tcp_port"], 5000)
        self.assertEqual(peer["status"], "online")
        self.assertIsInstance(peer["last_seen"], float)

        all_peers = self.manager.get_all_peers()
        self.assertEqual(len(all_peers), 1)

        online_peers = self.manager.get_online_peers()
        self.assertEqual(len(online_peers), 1)
        self.assertEqual(online_peers[0]["peer_id"], "pc-an-001")

    def test_02_update_existing_peer_no_duplicates(self):
        """Yêu cầu: Cập nhật peer cũ mà không tạo bản ghi trùng."""
        msg_v1 = {
            "type": "presence",
            "peer_id": "pc-binh-002",
            "username": "Binh",
            "tcp_port": 5000,
            "status": "online",
        }
        self.manager.update_peer(msg_v1, "192.168.1.103")
        self.assertEqual(len(self.manager.get_all_peers()), 1)

        # Cập nhật username và IP mới
        time.sleep(0.01)
        msg_v2 = {
            "type": "presence",
            "peer_id": "pc-binh-002",
            "username": "BinhPro",
            "tcp_port": 5001,
            "status": "online",
        }
        self.manager.update_peer(msg_v2, "192.168.1.104")

        # Không tạo bản ghi trùng
        all_peers = self.manager.get_all_peers()
        self.assertEqual(len(all_peers), 1)

        peer = self.manager.get_peer("pc-binh-002")
        self.assertEqual(peer["username"], "BinhPro")
        self.assertEqual(peer["ip"], "192.168.1.104")
        self.assertEqual(peer["tcp_port"], 5001)

    def test_03_ignore_self_peer_id(self):
        """Yêu cầu: Bỏ qua peer có ID trùng với máy hiện tại."""
        self_msg = {
            "type": "presence",
            "peer_id": self.self_id,
            "username": "Myself",
            "tcp_port": 5000,
            "status": "online",
        }
        result = self.manager.update_peer(self_msg, "192.168.1.100")
        self.assertFalse(result)
        self.assertEqual(len(self.manager.get_all_peers()), 0)
        self.assertIsNone(self.manager.get_peer(self.self_id))

    def test_04_save_source_ip_and_update_last_seen(self):
        """Yêu cầu: Lưu đúng IP nguồn và cập nhật last_seen."""
        msg = {
            "type": "presence",
            "peer_id": "pc-cuong-003",
            "username": "Cuong",
            "tcp_port": 6000,
            "status": "online",
        }
        ip = "10.0.0.55"
        before = time.time()
        self.manager.update_peer(msg, ip)
        after = time.time()

        peer = self.manager.get_peer("pc-cuong-003")
        self.assertEqual(peer["ip"], ip)
        self.assertTrue(before <= peer["last_seen"] <= after)

        # Nhận tin nhắn tiếp theo sau một khoảng trễ
        time.sleep(0.05)
        new_before = time.time()
        self.manager.update_peer(msg, ip)
        new_after = time.time()

        updated_peer = self.manager.get_peer("pc-cuong-003")
        self.assertTrue(new_before <= updated_peer["last_seen"] <= new_after)
        self.assertGreater(updated_peer["last_seen"], peer["last_seen"])

    def test_05_remove_peer(self):
        """Kiểm tra chức năng xóa peer khi cần."""
        msg = {
            "type": "presence",
            "peer_id": "pc-dung-004",
            "username": "Dung",
            "tcp_port": 5000,
            "status": "online",
        }
        self.manager.update_peer(msg, "192.168.1.150")
        self.assertEqual(len(self.manager.get_all_peers()), 1)

        removed = self.manager.remove_peer("pc-dung-004")
        self.assertTrue(removed)
        self.assertEqual(len(self.manager.get_all_peers()), 0)

        # Xóa lại một peer không tồn tại
        removed_again = self.manager.remove_peer("pc-dung-004")
        self.assertFalse(removed_again)

    def test_06_listen_integration_with_peer_manager(self):
        """Kết nối process_received_message từ listen.py vào PeerManager."""
        msg = create_presence_message("pc-hoa-005", "Hoa", 5000)
        data = encode_message(msg)

        # Giả lập gói tin UDP nhận từ IP 192.168.1.200
        success = process_received_message(data, "192.168.1.200", self.manager)
        self.assertTrue(success)

        peer = self.manager.get_peer("pc-hoa-005")
        self.assertIsNotNone(peer)
        self.assertEqual(peer["username"], "Hoa")
        self.assertEqual(peer["ip"], "192.168.1.200")

    def test_07_get_away_peers(self):
        """Kiểm tra get_away_peers trả về danh sách peer có status = away."""
        # Thêm peer online
        self.manager.update_peer(
            {"type": "presence", "peer_id": "pc-online", "username": "UserOnline", "tcp_port": 5000, "status": "online"},
            "192.168.1.101"
        )
        # Thêm peer away
        self.manager.update_peer(
            {"type": "presence", "peer_id": "pc-away-1", "username": "UserAway1", "tcp_port": 5000, "status": "away"},
            "192.168.1.102"
        )
        self.manager.update_peer(
            {"type": "presence", "peer_id": "pc-away-2", "username": "UserAway2", "tcp_port": 5000, "status": "away"},
            "192.168.1.103"
        )
        # Thêm peer offline
        self.manager.update_peer(
            {"type": "presence", "peer_id": "pc-offline", "username": "UserOffline", "tcp_port": 5000, "status": "offline"},
            "192.168.1.104"
        )

        away_peers = self.manager.get_away_peers()
        self.assertIsInstance(away_peers, list)
        self.assertEqual(len(away_peers), 2)
        away_ids = {p["peer_id"] for p in away_peers}
        self.assertEqual(away_ids, {"pc-away-1", "pc-away-2"})
        for p in away_peers:
            self.assertEqual(p["status"], "away")

    def test_08_cleanup_inactive_peers(self):
        """Kiểm tra cleanup_inactive_peers đánh dấu peer là offline nếu quá timeout."""
        # Thêm peer 1: vừa mới hoạt động
        self.manager.update_peer(
            {"type": "presence", "peer_id": "pc-active", "username": "ActiveUser", "tcp_port": 5000, "status": "online"},
            "192.168.1.110"
        )
        # Thêm peer 2: không hoạt động quá 15 giây
        self.manager.update_peer(
            {"type": "presence", "peer_id": "pc-inactive", "username": "InactiveUser", "tcp_port": 5000, "status": "online"},
            "192.168.1.111"
        )
        # Giả lập last_seen cách đây 15s
        with self.manager._lock:
            self.manager.peers["pc-inactive"]["last_seen"] = time.time() - 15.0

        # Gọi cleanup_inactive_peers với timeout = 10s
        result = self.manager.cleanup_inactive_peers(timeout=10)
        self.assertIsNone(result)

        # Peer inactive phải bị chuyển sang offline
        inactive_peer = self.manager.get_peer("pc-inactive")
        self.assertEqual(inactive_peer["status"], "offline")

        # Peer active vẫn giữ nguyên online
        active_peer = self.manager.get_peer("pc-active")
        self.assertEqual(active_peer["status"], "online")

        # get_online_peers giờ chỉ còn pc-active
        online_peers = self.manager.get_online_peers()
        online_ids = [p["peer_id"] for p in online_peers]
        self.assertIn("pc-active", online_ids)
        self.assertNotIn("pc-inactive", online_ids)


class TestMainOrchestration(unittest.TestCase):
    """Kiểm thử main.py khởi chạy và phối hợp các thành phần discovery."""

    def test_07_main_init_and_stop_discovery(self):
        """Yêu cầu: main.py khởi chạy, phối hợp và đóng tài nguyên an toàn."""
        peer_id = "test-node-coord"
        username = "Tester"
        tcp_port = 5555

        # Khởi chạy discovery
        peer_mgr, broadcaster, listener = main.init_discovery(peer_id, username, tcp_port)

        self.assertIsInstance(peer_mgr, PeerManager)
        self.assertEqual(peer_mgr.self_peer_id, peer_id)
        self.assertTrue(broadcaster.is_running)
        self.assertTrue(listener.is_running)

        # Đóng tài nguyên an toàn
        main.stop_discovery(broadcaster, listener)
        self.assertFalse(broadcaster.is_running)
        self.assertFalse(listener.is_running)

    def test_08_main_run_with_duration(self):
        """Kiểm thử main chạy với tham số duration và tự dừng an toàn."""
        # Chạy trong 1 giây rồi dừng
        code = main.main(["--peer-id", "test-auto-exit", "--username", "AutoTest", "--duration", "1.0", "--interval", "0.5"])
        self.assertEqual(code, 0)

    def test_09_end_to_end_network_discovery(self):
        """Kiểm thử gửi nhận gói tin broadcast thực tế trên mạng nội bộ qua UDP."""
        from peer_discovery.broadcast import create_broadcast_socket, broadcast_presence
        from peer_discovery.listen import start_listener

        peer_mgr_a = PeerManager("node-alice")
        listener_a = start_listener(peer_mgr_a)
        sock_b = create_broadcast_socket()

        try:
            # Node B gửi broadcast
            broadcast_presence(sock_b, "node-bob", "Bob", 5002, "online")
            
            # Chờ gói tin UDP được nhận và xử lý
            deadline = time.time() + 2.0
            found = False
            while time.time() < deadline:
                peer_b = peer_mgr_a.get_peer("node-bob")
                if peer_b is not None:
                    found = True
                    break
                time.sleep(0.05)

            self.assertTrue(found, "Node A không nhận được thông điệp broadcast từ Node B")
            self.assertEqual(peer_b["username"], "Bob")
            self.assertEqual(peer_b["tcp_port"], 5002)
            self.assertEqual(peer_b["status"], "online")
            self.assertTrue(len(peer_b["ip"]) > 0)

            # Node A tự gửi broadcast mang ID của chính nó
            broadcast_presence(sock_b, "node-alice", "Alice", 5001, "online")
            time.sleep(0.2)
            # Node A phải bỏ qua chính mình
            self.assertIsNone(peer_mgr_a.get_peer("node-alice"))
        finally:
            listener_a.stop()
            sock_b.close()



if __name__ == "__main__":
    unittest.main()
