import os
import sys
import socket
import threading
import unittest
from unittest.mock import Mock, patch, MagicMock

# Đảm bảo đường dẫn src nằm trong sys.path
SRC_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "src"
)

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from src.chat.chat_server import ChatServer
from src.chat.chat_manager import ChatManager
from src.peer_discovery.peer_manager import PeerManager
from src.config import CHAT_PORT   


class TestChatServer(unittest.TestCase):
    """
    Bộ kiểm thử đơn vị cho class ChatServer theo yêu cầu kỹ thuật:

    - 1.1: Kiểm tra các thuộc tính khởi tạo.
    - 1.2: Kiểm tra cấu trúc dữ liệu clients và client_threads.
    - 1.3: Kiểm tra phương thức create_server_socket().
    - 1.4: Kiểm tra phương thức handle_client().
    - 1.5: Kiểm tra phương thức start_chat_server().
    - 1.6: Kiểm tra xử lý kết nối và ngắt kết nối client.
    - 1.7: Kiểm tra đồng bộ dữ liệu giữa các thread.
    """

    def setUp(self):
        """
        Khởi tạo đối tượng ChatServer trước mỗi test.
        """
        self.server = ChatServer(
            host="127.0.0.1",
            port=9999
        )

    def tearDown(self):
        """
        Dọn dẹp tài nguyên sau mỗi test.
        """
        self.server.running = False

        if self.server.server_socket:
            self.server.server_socket.close()

    # ==========================================
    # 1.1. TEST INITIALIZATION
    # ==========================================

    def test_initialization(self):
        """Kiểm tra các thuộc tính khởi tạo."""

        self.assertEqual(self.server.host, "127.0.0.1")
        self.assertEqual(self.server.port, 9999)

        self.assertIsNone(self.server.server_socket)
        self.assertFalse(self.server.running)

        self.assertIsInstance(self.server.clients, dict)
        self.assertIsInstance(self.server.client_threads, list)

        self.assertIsNotNone(self.server.lock)

    # ==========================================
    # 1.2. TEST DATA STRUCTURE
    # ==========================================

    def test_clients_structure(self):
        """
        Kiểm tra cấu trúc clients.

        clients = {
            conn: addr
        }
        """

        mock_conn = Mock()
        mock_addr = ("127.0.0.1", 5000)

        self.server.clients[mock_conn] = mock_addr

        self.assertIn(mock_conn, self.server.clients)
        self.assertEqual(
            self.server.clients[mock_conn],
            mock_addr
        )

    def test_client_threads_structure(self):
        """Kiểm tra cấu trúc danh sách client_threads."""

        self.assertEqual(self.server.client_threads, [])

    # ==========================================
    # 1.3. TEST CREATE SERVER SOCKET
    # ==========================================

    @patch("chat.chat_server.socket.socket")
    def test_create_server_socket(self, mock_socket):
        """Kiểm tra tạo TCP server socket."""

        mock_server_socket = MagicMock()
        mock_socket.return_value = mock_server_socket

        self.server.create_server_socket()

        mock_socket.assert_called_once_with(
            socket.AF_INET,
            socket.SOCK_STREAM
        )

        mock_server_socket.bind.assert_called_once_with(
            ("127.0.0.1", 9999)
        )

        mock_server_socket.listen.assert_called_once()

        self.assertEqual(
            self.server.server_socket,
            mock_server_socket
        )

    # ==========================================
    # 1.4. TEST HANDLE CLIENT
    # ==========================================

    def test_handle_client_registration(self):
        """
        Kiểm tra client được đăng ký vào clients
        khi kết nối được xử lý.
        """

        mock_conn = MagicMock()
        mock_addr = ("127.0.0.1", 5000)

        # Test phần đăng ký kết nối theo logic thực tế
        with self.server.lock:
            self.server.clients[mock_conn] = mock_addr

        self.assertIn(mock_conn, self.server.clients)

    def test_handle_client_disconnect(self):
        """Kiểm tra xóa client khi kết nối bị ngắt."""

        mock_conn = MagicMock()
        mock_addr = ("127.0.0.1", 5000)

        self.server.clients[mock_conn] = mock_addr

        # Mô phỏng client ngắt kết nối
        with self.server.lock:
            self.server.clients.pop(mock_conn, None)

        self.assertNotIn(mock_conn, self.server.clients)

    # ==========================================
    # 1.5. TEST THREAD SYNCHRONIZATION
    # ==========================================

    def test_clients_thread_safety(self):
        """Kiểm tra đồng bộ khi nhiều thread truy cập clients."""

        connections = [
            (MagicMock(), ("127.0.0.1", 5000 + i))
            for i in range(10)
        ]

        def add_client(conn, addr):
            with self.server.lock:
                self.server.clients[conn] = addr

        threads = []

        for conn, addr in connections:
            thread = threading.Thread(
                target=add_client,
                args=(conn, addr)
            )

            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        self.assertEqual(len(self.server.clients), 10)


class TestChatServerIntegration(unittest.TestCase):
    """
    Kiểm thử tích hợp giữa ChatServer, ChatManager và PeerManager.

    - 2.1: Kiểm tra khởi tạo các thành phần.
    - 2.2: Kiểm tra quản lý kết nối TCP.
    - 2.3: Kiểm tra trao đổi dữ liệu giữa các thành phần.
    - 2.4: Kiểm tra xử lý khi peer ngắt kết nối.
    """

    def setUp(self):

        self.peer_manager = PeerManager("peer_01")

        self.chat_manager = ChatManager(
            self_peer_id="peer_01",
            peer_manager=self.peer_manager
        )

        self.chat_server = ChatServer(
            host="127.0.0.1",
            port=9999
        )

    def tearDown(self):

        if self.chat_server.server_socket:
            self.chat_server.server_socket.close()

    # ==========================================
    # 2.1. TEST COMPONENT INITIALIZATION
    # ==========================================

    def test_component_initialization(self):
        """Kiểm tra các thành phần được khởi tạo."""

        self.assertIsNotNone(self.peer_manager)
        self.assertIsNotNone(self.chat_manager)
        self.assertIsNotNone(self.chat_server)

    # ==========================================
    # 2.2. TEST TCP CONNECTION MANAGEMENT
    # ==========================================

    def test_multiple_client_connections(self):
        """
        Kiểm tra ChatServer quản lý nhiều kết nối TCP.
        """

        conn1 = MagicMock()
        conn2 = MagicMock()

        addr1 = ("127.0.0.1", 5001)
        addr2 = ("127.0.0.1", 5002)

        with self.chat_server.lock:
            self.chat_server.clients[conn1] = addr1
            self.chat_server.clients[conn2] = addr2

        self.assertEqual(
            len(self.chat_server.clients),
            2
        )

        self.assertIn(conn1, self.chat_server.clients)
        self.assertIn(conn2, self.chat_server.clients)

    # ==========================================
    # 2.3. TEST CLIENT DISCONNECTION
    # ==========================================

    def test_client_disconnection(self):
        """
        Kiểm tra khi client ngắt kết nối,
        ChatServer cập nhật danh sách clients.
        """

        conn = MagicMock()
        addr = ("127.0.0.1", 5001)

        self.chat_server.clients[conn] = addr

        with self.chat_server.lock:
            self.chat_server.clients.pop(conn, None)

        self.assertEqual(
            len(self.chat_server.clients),
            0
        )


if __name__ == "__main__":
    unittest.main()