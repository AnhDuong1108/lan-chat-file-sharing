import os
import sys
import threading
import time
import unittest

# Đảm bảo đường dẫn src nằm trong sys.path
SRC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from chat.chat_manager import ChatManager
from peer_discovery.peer_manager import PeerManager


class TestChatManager(unittest.TestCase):
    """
    Bộ kiểm thử đơn vị cho class ChatManager theo yêu cầu kỹ thuật:
    - 1.1: Thuộc tính khởi tạo.
    - 1.2: Định dạng dữ liệu (unread_counts, connections, conversations).
    - 1.3: Các method nghiệp vụ (select_chat_peer, handle_incoming_message, get_unread_count,
           mark_messages_as_read, get_messages).
    - 1.4: Quy tắc xử lý tin nhắn đến (trường hợp đang mở chat và không mở chat).
    """

    def setUp(self):
        self.self_peer_id = "pc-an-001"
        self.peer_manager = PeerManager(self.self_peer_id)
        self.chat_manager = ChatManager(self.self_peer_id, self.peer_manager)

    def test_01_init_attributes(self):
        """Kiểm tra khởi tạo đầy đủ các thuộc tính của ChatManager theo mục 1.1."""
        self.assertEqual(self.chat_manager.self_peer_id, self.self_peer_id)
        self.assertIs(self.chat_manager.peer_manager, self.peer_manager)
        self.assertEqual(self.chat_manager.conversations, {})
        self.assertIsNone(self.chat_manager.current_chat_peer)
        self.assertEqual(self.chat_manager.unread_counts, {})
        self.assertEqual(self.chat_manager.connections, {})

    def test_02_select_chat_peer(self):
        """Kiểm tra select_chat_peer đặt đúng peer_id làm đối tác chat hiện tại."""
        self.assertIsNone(self.chat_manager.current_chat_peer)

        # Chọn pc-binh-001
        self.chat_manager.select_chat_peer("pc-binh-001")
        self.assertEqual(self.chat_manager.current_chat_peer, "pc-binh-001")

        # Đổi sang pc-cuong-001
        self.chat_manager.select_chat_peer("pc-cuong-001")
        self.assertEqual(self.chat_manager.current_chat_peer, "pc-cuong-001")

        # Thoát chat
        self.chat_manager.select_chat_peer(None)
        self.assertIsNone(self.chat_manager.current_chat_peer)

    def test_03_handle_incoming_message_case_1_currently_chatting(self):
        """
        Quy tắc 1.4 - Trường hợp 1: Đang mở cuộc trò chuyện với người gửi.
        Điều kiện: current_chat_peer == peer_id.
        Kết quả: Không tăng số lượng tin nhắn chưa đọc.
        """
        peer_id = "pc-binh-001"
        self.chat_manager.select_chat_peer(peer_id)

        msg = {
            "type": "chat",
            "sender_id": peer_id,
            "receiver_id": self.self_peer_id,
            "content": "Hello An!",
            "timestamp": time.time(),
        }

        # Xử lý tin nhắn đến
        self.chat_manager.handle_incoming_message(peer_id, msg)

        # Tin nhắn phải được lưu vào conversations
        messages = self.chat_manager.get_messages(peer_id)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["content"], "Hello An!")

        # unread_counts không tăng
        self.assertEqual(self.chat_manager.get_unread_count(peer_id), 0)

    def test_04_handle_incoming_message_case_2_not_currently_chatting(self):
        """
        Quy tắc 1.4 - Trường hợp 2: Không mở cuộc trò chuyện với người gửi.
        Điều kiện: current_chat_peer != peer_id.
        Kết quả: Tăng unread_counts[peer_id] lên 1 cho mỗi tin nhắn đến.
        """
        peer_id = "pc-binh-001"
        # current_chat_peer đang là None (khác peer_id)
        self.assertNotEqual(self.chat_manager.current_chat_peer, peer_id)

        msg1 = {
            "type": "chat",
            "sender_id": peer_id,
            "receiver_id": self.self_peer_id,
            "content": "Message 1",
            "timestamp": time.time(),
        }
        self.chat_manager.handle_incoming_message(peer_id, msg1)
        self.assertEqual(self.chat_manager.get_unread_count(peer_id), 1)

        msg2 = {
            "type": "chat",
            "sender_id": peer_id,
            "receiver_id": self.self_peer_id,
            "content": "Message 2",
            "timestamp": time.time() + 1,
        }
        self.chat_manager.handle_incoming_message(peer_id, msg2)
        self.assertEqual(self.chat_manager.get_unread_count(peer_id), 2)

        # Chuyển sang chat với pc-cuong-001 (vẫn != pc-binh-001)
        self.chat_manager.select_chat_peer("pc-cuong-001")
        msg3 = {
            "type": "chat",
            "sender_id": peer_id,
            "receiver_id": self.self_peer_id,
            "content": "Message 3",
            "timestamp": time.time() + 2,
        }
        self.chat_manager.handle_incoming_message(peer_id, msg3)
        self.assertEqual(self.chat_manager.get_unread_count(peer_id), 3)

        # Kiểm tra lịch sử lưu đủ 3 tin nhắn
        messages = self.chat_manager.get_messages(peer_id)
        self.assertEqual(len(messages), 3)

    def test_05_handle_incoming_message_single_arg_callback(self):
        """Kiểm tra gọi handle_incoming_message(message) như dạng callback mạng."""
        msg = {
            "type": "chat",
            "sender_id": "pc-dung-001",
            "receiver_id": self.self_peer_id,
            "content": "Hi from callback!",
            "timestamp": time.time(),
        }
        self.chat_manager.handle_incoming_message(msg)

        self.assertEqual(self.chat_manager.get_unread_count("pc-dung-001"), 1)
        messages = self.chat_manager.get_messages("pc-dung-001")
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["content"], "Hi from callback!")

    def test_06_get_unread_count_int_and_dict(self):
        """Kiểm tra get_unread_count trả về int cho từng peer và dict cho toàn bộ."""
        # Peer chưa có tin nhắn -> 0 (int)
        self.assertIsInstance(self.chat_manager.get_unread_count("pc-unknown"), int)
        self.assertEqual(self.chat_manager.get_unread_count("pc-unknown"), 0)

        # Tạo tin nhắn cho 2 peer
        self.chat_manager.handle_incoming_message(
            "pc-binh-001",
            {"type": "chat", "sender_id": "pc-binh-001", "content": "A", "timestamp": 100.0}
        )
        self.chat_manager.handle_incoming_message(
            "pc-cuong-001",
            {"type": "chat", "sender_id": "pc-cuong-001", "content": "B1", "timestamp": 101.0}
        )
        self.chat_manager.handle_incoming_message(
            "pc-cuong-001",
            {"type": "chat", "sender_id": "pc-cuong-001", "content": "B2", "timestamp": 102.0}
        )

        # Lấy từng peer (kiểu int)
        self.assertEqual(self.chat_manager.get_unread_count("pc-binh-001"), 1)
        self.assertEqual(self.chat_manager.get_unread_count("pc-cuong-001"), 2)

        # Lấy toàn bộ (kiểu dict)
        all_unreads = self.chat_manager.get_unread_count()
        self.assertIsInstance(all_unreads, dict)
        self.assertEqual(all_unreads.get("pc-binh-001"), 1)
        self.assertEqual(all_unreads.get("pc-cuong-001"), 2)

    def test_07_mark_messages_as_read(self):
        """Kiểm tra mark_messages_as_read đặt số lượng tin nhắn chưa đọc về 0."""
        peer_id = "pc-binh-001"
        self.chat_manager.handle_incoming_message(
            peer_id,
            {"type": "chat", "sender_id": peer_id, "content": "Msg 1", "timestamp": 1.0}
        )
        self.chat_manager.handle_incoming_message(
            peer_id,
            {"type": "chat", "sender_id": peer_id, "content": "Msg 2", "timestamp": 2.0}
        )
        self.assertEqual(self.chat_manager.get_unread_count(peer_id), 2)

        # Đánh dấu đã đọc
        result = self.chat_manager.mark_messages_as_read(peer_id)
        self.assertIsNone(result)
        self.assertEqual(self.chat_manager.get_unread_count(peer_id), 0)

    def test_08_get_messages_format_and_immutability(self):
        """Kiểm tra get_messages trả về đúng cấu trúc list[dict] và bảo vệ dữ liệu gốc."""
        peer_id = "pc-binh-001"
        msg1 = {
            "type": "chat",
            "sender_id": "pc-an-001",
            "receiver_id": "pc-binh-001",
            "content": "Hello Binh!",
            "timestamp": 1793000000.0,
        }
        msg2 = {
            "type": "chat",
            "sender_id": "pc-binh-001",
            "receiver_id": "pc-an-001",
            "content": "Hello An!",
            "timestamp": 1793000005.0,
        }

        self.chat_manager.add_message(peer_id, msg1)
        self.chat_manager.handle_incoming_message(peer_id, msg2)

        messages = self.chat_manager.get_messages(peer_id)
        self.assertIsInstance(messages, list)
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["content"], "Hello Binh!")
        self.assertEqual(messages[1]["content"], "Hello An!")

        # Thay đổi dữ liệu trả về không làm biến đổi dữ liệu lưu trữ bên trong
        messages[0]["content"] = "Modified"
        fresh_messages = self.chat_manager.get_messages(peer_id)
        self.assertEqual(fresh_messages[0]["content"], "Hello Binh!")

        # Peer chưa có hội thoại trả về list rỗng
        self.assertEqual(self.chat_manager.get_messages("pc-nonexistent"), [])

    def test_09_connections_management(self):
        """Kiểm tra lưu trữ, truy xuất và xóa kết nối TCP socket."""
        # Giả lập đối tượng socket
        class MockSocket:
            def __init__(self, name):
                self.name = name

        sock_binh = MockSocket("conn_binh")
        sock_cuong = MockSocket("conn_cuong")

        self.chat_manager.add_connection("pc-binh-001", sock_binh)
        self.chat_manager.connections["pc-cuong-001"] = sock_cuong

        # Format lưu trữ dictionary theo mục 1.2
        self.assertEqual(self.chat_manager.connections["pc-binh-001"], sock_binh)
        self.assertEqual(self.chat_manager.connections["pc-cuong-001"], sock_cuong)

        # Lấy kết nối
        self.assertIs(self.chat_manager.get_connection("pc-binh-001"), sock_binh)
        self.assertIsNone(self.chat_manager.get_connection("pc-dung-001"))

        # Xóa kết nối
        self.chat_manager.remove_connection("pc-binh-001")
        self.assertIsNone(self.chat_manager.get_connection("pc-binh-001"))
        self.assertNotIn("pc-binh-001", self.chat_manager.connections)

    def test_10_multithreaded_incoming_messages(self):
        """Kiểm tra tính an toàn đa luồng (thread-safe) khi nhận đồng thời nhiều tin nhắn."""
        num_threads = 10
        messages_per_thread = 20

        def worker(thread_idx):
            for i in range(messages_per_thread):
                msg = {
                    "type": "chat",
                    "sender_id": f"peer-thread-{thread_idx}",
                    "receiver_id": self.self_peer_id,
                    "content": f"msg-{i}",
                    "timestamp": time.time(),
                }
                self.chat_manager.handle_incoming_message(f"peer-thread-{thread_idx}", msg)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Kiểm tra mỗi peer nhận đúng 20 tin nhắn và unread_count = 20
        for i in range(num_threads):
            peer_id = f"peer-thread-{i}"
            self.assertEqual(self.chat_manager.get_unread_count(peer_id), messages_per_thread)
            self.assertEqual(len(self.chat_manager.get_messages(peer_id)), messages_per_thread)


if __name__ == "__main__":
    unittest.main()
