"""
TEST CASES - CHAT UI

1. test_display_main_menu: Kiểm tra hiển thị menu chính và nhận lựa chọn.

2. test_display_online_peers: Kiểm tra hiển thị danh sách peer online.

3. test_display_online_peers_empty: Kiểm tra khi không có peer online.

4. test_display_chat_history: Kiểm tra hiển thị lịch sử trò chuyện.

5. test_display_chat_history_empty: Kiểm tra khi lịch sử trò chuyện trống.

6. test_display_chat_history_timestamp_interval: Kiểm tra hiển thị mốc thời gian giữa các nhóm tin nhắn.

7. test_display_unread_notifications: Kiểm tra hiển thị số lượng tin nhắn chưa đọc.

8. test_display_unread_notifications_unknown_peer: Kiểm tra khi không tìm thấy thông tin peer.

9. test_get_user_input: Kiểm tra nhận và xử lý nội dung người dùng nhập.

10. test_display_incoming_message: Kiểm tra hiển thị tin nhắn đến.

11. test_display_incoming_message_unknown_peer: Kiểm tra hiển thị tin nhắn khi không tìm thấy người gửi.

12. test_change_status_online: Kiểm tra chuyển trạng thái sang Online.

13. test_change_status_away: Kiểm tra chuyển trạng thái sang Away.

14. test_change_status_invalid: Kiểm tra khi nhập trạng thái không hợp lệ.

15. test_start_unread_messages: Kiểm tra chức năng xem tin nhắn chưa đọc từ menu.

16. test_start_change_status: Kiểm tra chức năng thay đổi trạng thái từ menu.

17. test_start_exit: Kiểm tra quay về menu chính khi nhập /quit.

18. test_start_invalid_option: Kiểm tra khi nhập lựa chọn menu không hợp lệ.

19. test_start_chat_success: Kiểm tra quá trình kết nối và bắt đầu trò chuyện thành công.

20. test_start_chat_connection_error: Kiểm tra xử lý lỗi khi không thể kết nối đến peer.
"""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch
import sys
import os
# Project root
PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

# Add project root and src to Python path
SRC_DIR = os.path.join(PROJECT_ROOT, "src")

for path in (PROJECT_ROOT, SRC_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)


from src.chat.chat_ui import ChatUI
import src.chat.chat_ui as chat_ui_module

class TestChatUI(unittest.TestCase):
    def setUp(self):
        # Avoid ChatUI.__init__: it starts a presence broadcaster/thread and
        # creates terminal-related objects. Each test gets a lightweight UI.
        self.ui = ChatUI.__new__(ChatUI)

        self.ui.peer_manager = MagicMock()
        self.ui.peer_manager.username = "Me"
        self.ui.peer_manager.self_peer_id = "self-id"
        self.ui.peer_manager.tcp_port = 5000

        self.ui.chat_manager = MagicMock()
        self.ui.chat_manager.self_peer_id = "self-id"
        self.ui.chat_manager.current_chat_peer = None
        self.ui.chat_manager.unread_counts = {}

        self.ui.style = None
        self.ui.session = MagicMock()
        self.ui.set_status = MagicMock()
        self.ui.last_message_time = {}
        self.ui.notifications = []
        self.ui.incoming_message_queue = MagicMock()
        self.ui.receive_stop_event = MagicMock()
        self.ui.receive_thread = None
        self.ui.file_manager = None
        self.ui.file_dir = "/tmp/docs"
        self.ui.peer_current = {}
        self.ui.end = False
        self.ui.leave = False

        # Keep tests focused on UI behavior, not prompt_toolkit rendering.
        self.ui.print_styled = MagicMock()

    # 1. Main menu
    def test_display_main_menu(self):
        with patch("builtins.print") as mocked_print:
            self.ui.display_help_menu()

        output = " ".join(str(c) for c in mocked_print.call_args_list)
        self.assertIn("/list", output)
        self.assertIn("/chat", output)
        self.assertIn("/status", output)
        self.assertIn("/quit", output)

    # 2. Online peers
    def test_display_online_peers(self):
        online = [
            {"username": "Alice", "peer_id": "a1", "status": "online"},
            {"username": "Bob", "peer_id": "b1", "status": "away"},
        ]
        self.ui.peer_manager.get_online_peers.return_value = [online[0]]
        self.ui.peer_manager.get_away_peers.return_value = [online[1]]

        with patch("builtins.print") as mocked_print:
            self.ui.display_online_peers()

        output = " ".join(str(c) for c in mocked_print.call_args_list)
        self.assertIn("Alice", output)
        self.assertIn("Bob", output)
        self.assertIn("ONLINE PEERS", output)

    # 3. No online peers
    def test_display_online_peers_empty(self):
        self.ui.peer_manager.get_online_peers.return_value = []
        self.ui.peer_manager.get_away_peers.return_value = []

        with patch("builtins.print") as mocked_print:
            result = self.ui.display_online_peers()

        self.assertEqual(result, [])
        self.assertIn(
            "No peers are currently online.",
            " ".join(str(c) for c in mocked_print.call_args_list),
        )

    # 4. Chat history
    def test_display_chat_history(self):
        peer = {"username": "Alice"}
        messages = [
            {"sender_id": "a1", "timestamp": 1000, "content": "Hello"},
            {"sender_id": "self-id", "timestamp": 1010, "content": "Hi"},
        ]
        self.ui.peer_manager.get_peer.side_effect = [
            {"username": "Alice"},
            None,
        ]

        with patch("builtins.print"):
            self.ui.display_chat_history(peer, messages)

        self.assertEqual(self.ui.print_styled.call_count, 2)
        self.assertIn("Hello", str(self.ui.print_styled.call_args_list))
        self.assertIn("Hi", str(self.ui.print_styled.call_args_list))

    # 5. Empty chat history
    def test_display_chat_history_empty(self):
        with patch("builtins.print") as mocked_print:
            self.ui.display_chat_history({"username": "Alice"}, [])

        self.assertIn(
            "No messages yet.",
            " ".join(str(c) for c in mocked_print.call_args_list),
        )
        self.ui.print_styled.assert_not_called()

    # 6. Timestamp interval is at least five minutes
    def test_display_chat_history_timestamp_interval(self):
        peer = {"username": "Alice"}

        messages = [
            {
                "sender_id": "peer1",
                "timestamp": 1000,
                "content": "Message 1"
            },
            {
                "sender_id": "peer1",
                "timestamp": 1100,
                "content": "Message 2"
            },
            {
                "sender_id": "peer1",
                "timestamp": 1400,
                "content": "Message 3"
            },
        ]

        self.ui.peer_manager.get_peer.return_value = {
            "username": "Alice"
        }

        with patch("builtins.print") as mock_print:
            self.ui.display_chat_history(peer, messages)

        printed_text = "\n".join(
            str(call.args[0])
            for call in mock_print.call_args_list
            if call.args
        )

        # Timestamp xuất hiện ở tin nhắn đầu và tin nhắn thứ ba
        timestamp_calls = [
            call for call in mock_print.call_args_list
            if call.args and "----------" in str(call.args[0])
        ]

        self.assertEqual(len(timestamp_calls), 2)

    # 7. Unread notifications
    def test_display_unread_notifications(self):
        self.ui.peer_manager.get_peer.return_value = {"username": "Alice"}

        with patch("builtins.print") as mocked_print:
            self.ui.display_unread_notifications({"a1": 3})

        output = " ".join(str(c) for c in mocked_print.call_args_list)
        self.assertIn("Alice", output)
        self.assertIn("3", output)

    # 8. Unknown peer in unread notifications.
    def test_display_unread_notifications_unknown_peer(self):
        self.ui.peer_manager.get_peer.return_value = None

        with patch("builtins.print") as mocked_print:
            self.ui.display_unread_notifications({"missing-peer": 2})

        output = " ".join(str(c) for c in mocked_print.call_args_list)
        self.assertIn("missing-peer", output)
        self.assertIn("2", output)

    # 9. Read and trim user input
    def test_get_user_input(self):
        session = MagicMock()
        session.prompt.return_value = "  hello world  "
        self.ui.session = session

        result = self.ui.get_user_input()

        self.assertEqual(result, "hello world")
        session.prompt.assert_called_once()

    def test_get_choice_uses_prompt_session(self):
        self.ui.session.prompt.return_value = "  /help  "

        with patch("builtins.input") as user_input:
            self.assertEqual(self.ui.get_choice(), "/help")

        self.ui.session.prompt.assert_called_once()
        user_input.assert_not_called()

    def test_get_choice_falls_back_to_input(self):
        for session in (None, MagicMock()):
            with self.subTest(session_available=session is not None):
                self.ui.session = session
                if session is not None:
                    session.prompt.side_effect = OSError("Terminal unavailable")
                with patch("builtins.input", return_value="  /quit  ") as user_input:
                    self.assertEqual(self.ui.get_choice(), "/quit")
                user_input.assert_called_once()

    def test_display_transfer_progress_peer_fallback(self):
        self.ui.file_manager = MagicMock()
        transfer = {
            "status": "transferring", "peer_id": "peer-1",
            "file_name": "sample.txt", "file_size": 100, "progress": 50.0,
        }
        for peer, name in (
            ({"username": "Alice"}, "Alice"),
            (None, "peer-1"),
            ({}, "peer-1"),
            ({"username": ""}, "peer-1"),
        ):
            with self.subTest(peer=peer):
                self.ui.peer_manager.get_peer.return_value = peer
                with patch("builtins.print") as output:
                    self.ui.display_transfer_progress(transfer)
                self.assertIn(f"Peer: {name}", output.call_args.args[0])
                self.assertIn("50.0%", output.call_args.args[0])

    # 10. Incoming message from a known peer
    def test_display_incoming_message(self):
        self.ui.peer_manager.get_peer.return_value = {"username": "Alice"}
        message = {
            "sender_id": "a1",
            "timestamp": 1_700_000_000,
            "content": "Incoming hello",
        }

        with patch.object(chat_ui_module, "datetime") as mocked_datetime:
            mocked_datetime.fromtimestamp.return_value.strftime.return_value = "12:00"
            self.ui.display_incoming_message(message)

        self.assertIn("Alice", str(self.ui.print_styled.call_args_list))
        self.assertIn("Incoming hello", str(self.ui.print_styled.call_args_list))
        self.assertEqual(
            self.ui.last_message_time["a1"],
            message["timestamp"],
        )

    # 11. Incoming message from an unknown peer
    def test_display_incoming_message_unknown_peer(self):
        self.ui.peer_manager.get_peer.return_value = None
        message = {
            "sender_id": "unknown-id",
            "timestamp": 1_700_000_000,
            "content": "Who are you?",
        }

        with patch.object(chat_ui_module, "datetime") as mocked_datetime:
            mocked_datetime.fromtimestamp.return_value.strftime.return_value = "12:00"
            self.ui.display_incoming_message(message)

        output = str(self.ui.print_styled.call_args_list)
        self.assertIn("unknown-id", output)
        self.assertIn("Who are you?", output)

    # 12–13. Change status to online / away
    def test_change_status_online(self):
        self.ui.peer_manager.set_status.return_value = True

        self.assertTrue(self.ui.change_status("online"))

        self.ui.set_status.assert_called_once_with("online")
        self.ui.peer_manager.set_status.assert_called_once_with("online")

    def test_change_status_away(self):
        self.ui.peer_manager.set_status.return_value = True

        self.assertTrue(self.ui.change_status("away"))

        self.ui.set_status.assert_called_once_with("away")
        self.ui.peer_manager.set_status.assert_called_once_with("away")

    # 14. Invalid status
    def test_change_status_invalid(self):
        self.assertFalse(self.ui.change_status("busy"))

        self.ui.set_status.assert_not_called()
        self.ui.peer_manager.set_status.assert_not_called()

    # 15. Broadcaster stopped
    def test_change_status_callback_failure(self):
        self.ui.set_status.side_effect = RuntimeError("Broadcaster stopped")

        with self.assertLogs(chat_ui_module.logger, level="ERROR"):
            self.assertFalse(self.ui.change_status("away"))

        self.ui.peer_manager.set_status.assert_not_called()

    # 16. Start menu: change status
    def test_start_change_status(self):
        self.ui.peer_manager.set_status.return_value = True

        self.ui.session.prompt.side_effect = ["/status online", "/quit"]
        with patch("builtins.input", side_effect=AssertionError("Menu must use PromptSession")) as user_input, patch(
            "builtins.print"
        ):
            self.ui.start()

        self.ui.peer_manager.set_status.assert_called_once_with("online")
        self.ui.set_status.assert_called_once_with("online")
        self.assertEqual(self.ui.session.prompt.call_count, 2)
        user_input.assert_not_called()

    # 17. Return to main menu
    def test_start_exit(self):
        self.ui.session.prompt.return_value = "/quit"
        with patch("builtins.input", side_effect=AssertionError("Menu must use PromptSession")) as user_input, patch(
            "builtins.print"
        ) as mocked_print:
            result = self.ui.start()

        self.assertIsNone(result)
        self.assertIn(
            "Return to Main Menu ...",
            " ".join(str(c) for c in mocked_print.call_args_list),
        )
        self.ui.session.prompt.assert_called_once()
        user_input.assert_not_called()

    # 18. Invalid menu option
    def test_start_invalid_option(self):
        self.ui.session.prompt.side_effect = ["/not-a-command", "/quit"]
        with (
            patch("builtins.input", side_effect=AssertionError("Menu must use PromptSession")) as user_input,
            patch("builtins.print") as mocked_print,
        ):
            self.ui.start()

        self.assertIn(
            "Invalid option. Please try again.",
            " ".join(str(c) for c in mocked_print.call_args_list),
        )
        self.assertEqual(self.ui.session.prompt.call_count, 2)
        user_input.assert_not_called()

    def _configure_one_online_peer(self):
        peer = {
            "username": "Alice",
            "peer_id": "a1",
            "ip": "127.0.0.1",
            "tcp_port": 6000,
            "status": "online",
        }
        self.ui.peer_manager.get_online_peers.return_value = [peer]
        self.ui.peer_manager.get_peer.return_value = peer
        return peer

    # 19. Start chat successfully
    @patch.object(chat_ui_module, "ChatClient")
    def test_start_chat_success(self, mocked_client_class):
        peer = self._configure_one_online_peer()
        conn = object()
        client = mocked_client_class.return_value
        client.connect.return_value = conn

        with patch.object(self.ui, "display_chat_header"), patch.object(
            self.ui, "display_chat_history"
        ), patch.object(self.ui, "chat_loop") as mocked_chat_loop:
            self.ui.start_chat("Alice")

        self.ui.chat_manager.select_chat_peer.assert_any_call("a1")
        self.ui.chat_manager.mark_messages_as_read.assert_called_once_with("a1")
        self.ui.chat_manager.add_connection.assert_called_once_with("a1", conn)
        mocked_chat_loop.assert_called_once_with(peer, conn, client)
        self.ui.chat_manager.remove_connection.assert_called_once_with("a1")
        client.close.assert_called_once_with(conn)

    # 20. Connection error while starting chat
    @patch.object(chat_ui_module, "ChatClient")
    def test_start_chat_connection_error(self, mocked_client_class):
        self._configure_one_online_peer()
        client = mocked_client_class.return_value
        client.connect.side_effect = OSError("connection refused")

        with patch.object(self.ui, "display_chat_header"), patch.object(
            self.ui, "display_chat_history"
        ), patch.object(self.ui, "display_error") as mocked_error:
            self.ui.start_chat("Alice")

        mocked_error.assert_called_once()
        self.assertIn("connection refused", str(mocked_error.call_args))
        self.ui.chat_manager.remove_connection.assert_called_once_with("a1")
        client.close.assert_called_once_with(None)


if __name__ == "__main__":
    unittest.main(verbosity=2)
