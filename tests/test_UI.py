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

17. test_start_exit: Kiểm tra chức năng thoát ứng dụng.

18. test_start_invalid_option: Kiểm tra khi nhập lựa chọn menu không hợp lệ.

19. test_start_chat_success: Kiểm tra quá trình kết nối và bắt đầu trò chuyện thành công.

20. test_start_chat_connection_error: Kiểm tra xử lý lỗi khi không thể kết nối đến peer.
"""


import unittest
import queue
from unittest.mock import Mock, patch, call
from io import StringIO
from contextlib import redirect_stdout
import sys
import os
SRC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from chat.chat_ui import ChatUI

class TestChatUI(unittest.TestCase):

    def setUp(self):
        self.peer_manager = Mock()
        self.chat_manager = Mock()

        self.peer_manager.self_peer_id = "peer_001"
        self.chat_manager.self_peer_id = "peer_001"
        self.chat_manager.current_chat_peer = None

        self.ui = ChatUI(
            peer_manager=self.peer_manager,
            chat_manager=self.chat_manager
        )

        self.peer = {
            "peer_id": "peer_002",
            "username": "Alice",
            "ip": "192.168.1.10",
            "tcp_port": 5000,
            "status": "online"
        }

        self.message = {
            "type": "chat",
            "sender_id": "peer_002",
            "receiver_id": "peer_001",
            "content": "Hello",
            "timestamp": 1700000000
        }

    # ==========================================
    # INITIALIZATION
    # ==========================================

    def test_init(self):
        self.assertIs(self.ui.peer_manager, self.peer_manager)
        self.assertIs(self.ui.chat_manager, self.chat_manager)
        self.assertIsNone(self.ui.set_status)

    def test_init_with_set_status(self):
        callback = Mock()

        ui = ChatUI(
            self.peer_manager,
            self.chat_manager,
            callback
        )

        self.assertIs(ui.set_status, callback)

    def test_init_receive_components(self):
        self.assertIsNone(self.ui.receive_thread)
        self.assertIsInstance(
            self.ui.incoming_message_queue,
            queue.Queue
        )
        self.assertFalse(self.ui.receive_stop_event.is_set())

    # ==========================================
    # DISPLAY MAIN MENU
    # ==========================================

    @patch("builtins.input", return_value="1")
    def test_display_main_menu(self, mock_input):
        output = StringIO()

        with redirect_stdout(output):
            result = self.ui.display_main_menu()

        self.assertEqual(result, "1")
        self.assertIn("P2P CHAT", output.getvalue())
        self.assertIn("Show online peers", output.getvalue())
        self.assertIn("Exit", output.getvalue())

    @patch("builtins.input", return_value="  5  ")
    def test_display_main_menu_strip_input(self, mock_input):
        result = self.ui.display_main_menu()

        self.assertEqual(result, "5")

    # ==========================================
    # DISPLAY CHAT HEADER
    # ==========================================

    def test_display_chat_header(self):
        output = StringIO()

        with redirect_stdout(output):
            self.ui.display_chat_header(self.peer)

        result = output.getvalue()

        self.assertIn("Alice", result)
        self.assertIn("peer_002", result)
        self.assertIn("192.168.1.10", result)
        self.assertIn("online", result)
        self.assertIn("/back", result)
        self.assertIn("/exit", result)

    # ==========================================
    # DISPLAY ERROR / SUCCESS
    # ==========================================

    def test_display_error(self):
        output = StringIO()

        with redirect_stdout(output):
            self.ui.display_error("Connection failed")

        self.assertIn("[ERROR]", output.getvalue())
        self.assertIn("Connection failed", output.getvalue())

    def test_display_success(self):
        output = StringIO()

        with redirect_stdout(output):
            self.ui.display_success("Connected")

        self.assertIn("[SUCCESS]", output.getvalue())
        self.assertIn("Connected", output.getvalue())

    # ==========================================
    # DISPLAY ONLINE PEERS
    # ==========================================

    def test_display_online_peers_empty(self):
        self.peer_manager.get_online_peers.return_value = []

        output = StringIO()

        with redirect_stdout(output):
            result = self.ui.display_online_peers()

        self.assertEqual(result, [])
        self.assertIn(
            "No peers are currently online.",
            output.getvalue()
        )

    def test_display_online_peers(self):
        peers = [
            self.peer,
            {
                "peer_id": "peer_003",
                "username": "Bob",
                "status": "away"
            }
        ]

        self.peer_manager.get_online_peers.return_value = peers

        output = StringIO()

        with redirect_stdout(output):
            result = self.ui.display_online_peers()

        self.assertEqual(len(result), 2)

        self.assertEqual(result[0]["peer"], peers[0])
        self.assertEqual(result[0]["index"], 1)

        self.assertEqual(result[1]["peer"], peers[1])
        self.assertEqual(result[1]["index"], 2)

        self.assertIn("Alice", output.getvalue())
        self.assertIn("Bob", output.getvalue())

        self.peer_manager.get_online_peers.assert_called_once()

    # ==========================================
    # DISPLAY CHAT HISTORY
    # ==========================================

    def test_display_chat_history_empty(self):
        output = StringIO()

        with redirect_stdout(output):
            self.ui.display_chat_history(self.peer, [])

        self.assertIn("No messages yet.", output.getvalue())

    def test_display_chat_history(self):
        messages = [
            {
                "sender_id": "peer_001",
                "content": "Hello",
                "timestamp": 1700000000
            },
            {
                "sender_id": "peer_002",
                "content": "Hi",
                "timestamp": 1700000010
            }
        ]

        output = StringIO()

        with redirect_stdout(output):
            self.ui.display_chat_history(
                self.peer,
                messages
            )

        result = output.getvalue()

        self.assertIn("Alice", result)
        self.assertIn("peer_001: Hello", result)
        self.assertIn("peer_002: Hi", result)

    def test_display_chat_history_unknown_sender(self):
        messages = [
            {
                "content": "Hello",
                "timestamp": 1700000000
            }
        ]

        output = StringIO()

        with redirect_stdout(output):
            self.ui.display_chat_history(
                self.peer,
                messages
            )

        self.assertIn("Unknown: Hello", output.getvalue())

    def test_display_chat_history_timestamp_interval(self):
        messages = [
            {
                "sender_id": "peer_001",
                "content": "Message 1",
                "timestamp": 1700000000
            },
            {
                "sender_id": "peer_002",
                "content": "Message 2",
                "timestamp": 1700000100
            },
            {
                "sender_id": "peer_001",
                "content": "Message 3",
                "timestamp": 1700000300
            },
            {
                "sender_id": "peer_002",
                "content": "Message 4",
                "timestamp": 1700000400
            }
        ]

        output = StringIO()

        with redirect_stdout(output):
            self.ui.display_chat_history(
                self.peer,
                messages
            )

        # Chỉ có một timestamp vì các tin nhắn cách nhau
        # dưới 5 phút so với tin nhắn liền trước.
        self.assertEqual(
            output.getvalue().count("----------"),
            2
        )

    def test_display_chat_history_after_five_minutes(self):
        messages = [
            {
                "sender_id": "peer_001",
                "content": "Message 1",
                "timestamp": 1700000000
            },
            {
                "sender_id": "peer_002",
                "content": "Message 2",
                "timestamp": 1700000300
            }
        ]

        output = StringIO()

        with redirect_stdout(output):
            self.ui.display_chat_history(
                self.peer,
                messages
            )

        self.assertEqual(
            output.getvalue().count("----------"),
            4
        )

    # ==========================================
    # DISPLAY UNREAD NOTIFICATIONS
    # ==========================================

    def test_display_unread_notifications(self):
        self.peer_manager.get_peer.return_value = self.peer

        output = StringIO()

        with redirect_stdout(output):
            self.ui.display_unread_notifications({
                "peer_002": 3
            })

        self.assertIn("Alice: 3", output.getvalue())

    def test_display_unread_notifications_unknown_peer(self):
        self.peer_manager.get_peer.return_value = None

        output = StringIO()

        with redirect_stdout(output):
            self.ui.display_unread_notifications({
                "peer_999": 2
            })

        self.assertIn("peer_999: 2", output.getvalue())

    def test_display_unread_notifications_empty(self):
        output = StringIO()

        with redirect_stdout(output):
            self.ui.display_unread_notifications({})

        self.assertIn("UNREAD MESSAGES", output.getvalue())

    # ==========================================
    # GET USER INPUT
    # ==========================================

    @patch("chat.chat_ui.PromptSession.prompt", return_value="Hello")
    def test_get_user_input(self, mock_prompt):
        result = self.ui.get_user_input()

        self.assertEqual(result, "Hello")
        mock_prompt.assert_called_once_with("You: ")

    @patch("chat.chat_ui.PromptSession.prompt", return_value="  Hello  ")
    def test_get_user_input_strip(self, mock_prompt):
        result = self.ui.get_user_input()

        self.assertEqual(result, "Hello")

    # ==========================================
    # DISPLAY INCOMING MESSAGE
    # ==========================================

    def test_display_incoming_message(self):
        self.peer_manager.get_peer.return_value = self.peer

        output = StringIO()

        with redirect_stdout(output):
            self.ui.display_incoming_message(self.message)

        result = output.getvalue()

        self.assertIn("Alice: Hello", result)
        self.assertIn("Time:", result)

    def test_display_incoming_message_same_sender(self):
        self.peer_manager.get_peer.return_value = self.peer

        second_message = {
            **self.message,
            "content": "How are you?",
            "timestamp": self.message["timestamp"] + 10
        }

        with redirect_stdout(StringIO()):
            self.ui.display_incoming_message(self.message)

        output = StringIO()

        with redirect_stdout(output):
            self.ui.display_incoming_message(second_message)

        result = output.getvalue()

        self.assertIn("Alice: How are you?", result)
        self.assertNotIn("Time:", result)

    def test_display_incoming_message_after_five_minutes(self):
        self.peer_manager.get_peer.return_value = self.peer

        second_message = {
            **self.message,
            "content": "New message",
            "timestamp": self.message["timestamp"] + 300
        }

        with redirect_stdout(StringIO()):
            self.ui.display_incoming_message(self.message)

        output = StringIO()

        with redirect_stdout(output):
            self.ui.display_incoming_message(second_message)

        self.assertIn("Time:", output.getvalue())

    def test_display_incoming_message_unknown_peer(self):
        self.peer_manager.get_peer.return_value = None

        output = StringIO()

        with redirect_stdout(output):
            self.ui.display_incoming_message(self.message)

        self.assertIn("peer_002: Hello", output.getvalue())

    # ==========================================
    # HANDLE INCOMING MESSAGE
    # ==========================================

    @patch("chat.chat_ui.validate_chat_message", return_value=False)
    def test_handle_incoming_message_invalid(self, mock_validate):
        self.ui.handle_incoming_message(self.message)

        mock_validate.assert_called_once_with(self.message)

        self.chat_manager.handle_incoming_message.assert_not_called()

    @patch("chat.chat_ui.validate_chat_message", return_value=True)
    def test_handle_incoming_message_wrong_receiver(self, mock_validate):
        message = {
            **self.message,
            "receiver_id": "peer_999"
        }

        self.ui.handle_incoming_message(message)

        self.chat_manager.handle_incoming_message.assert_not_called()

    @patch("chat.chat_ui.validate_chat_message", return_value=True)
    def test_handle_incoming_message_self_sender(self, mock_validate):
        message = {
            **self.message,
            "sender_id": "peer_001"
        }

        self.ui.handle_incoming_message(message)

        self.chat_manager.handle_incoming_message.assert_not_called()

    @patch("chat.chat_ui.validate_chat_message", return_value=True)
    def test_handle_incoming_message_invalid_timestamp(self, mock_validate):
        message = {
            **self.message,
            "timestamp": "invalid"
        }

        self.ui.handle_incoming_message(message)

        self.chat_manager.handle_incoming_message.assert_not_called()

    @patch("chat.chat_ui.validate_chat_message", return_value=True)
    def test_handle_incoming_message_valid(self, mock_validate):
        self.chat_manager.current_chat_peer = "peer_999"

        self.ui.handle_incoming_message(self.message)

        self.chat_manager.handle_incoming_message.assert_called_once_with(
            self.message
        )

    @patch("chat.chat_ui.validate_chat_message", return_value=True)
    @patch.object(ChatUI, "display_incoming_message")
    def test_handle_incoming_message_current_chat(
        self,
        mock_display,
        mock_validate
    ):
        self.chat_manager.current_chat_peer = "peer_002"

        self.ui.handle_incoming_message(self.message)

        self.chat_manager.handle_incoming_message.assert_called_once_with(
            self.message
        )

        mock_display.assert_called_once_with(self.message)

    # ==========================================
    # HANDLE RECEIVED MESSAGE
    # ==========================================

    @patch.object(ChatUI, "display_incoming_message")
    def test_handle_received_message(self, mock_display):
        self.ui.handle_received_message(self.message)

        self.chat_manager.handle_incoming_message.assert_called_once_with(
            self.message
        )

        mock_display.assert_called_once_with(self.message)

    # ==========================================
    # CHANGE STATUS
    # ==========================================

    @patch("builtins.input", return_value="1")
    def test_change_status_online(self, mock_input):
        result = self.ui.change_status()

        self.assertEqual(result, "online")

    @patch("builtins.input", return_value="2")
    def test_change_status_away(self, mock_input):
        result = self.ui.change_status()

        self.assertEqual(result, "away")

    @patch("builtins.input", return_value="3")
    def test_change_status_invalid(self, mock_input):
        output = StringIO()

        with redirect_stdout(output):
            result = self.ui.change_status()

        self.assertIsNone(result)
        self.assertIn("Invalid choice", output.getvalue())

    # ==========================================
    # PROCESS INCOMING MESSAGES
    # ==========================================

    @patch.object(ChatUI, "display_incoming_message")
    def test_process_incoming_messages(self, mock_display):
        self.ui.incoming_message_queue.put(self.message)

        self.ui.process_incoming_messages()

        self.chat_manager.handle_incoming_message.assert_called_once_with(
            self.message
        )

        mock_display.assert_called_once_with(self.message)

        self.assertTrue(self.ui.incoming_message_queue.empty())

    def test_process_incoming_messages_empty(self):
        self.ui.process_incoming_messages()

        self.chat_manager.handle_incoming_message.assert_not_called()

    # ==========================================
    # START MAIN MENU
    # ==========================================

    @patch.object(ChatUI, "display_main_menu", return_value="5")
    def test_start_exit(self, mock_menu):
        result = self.ui.start()

        self.assertIsNone(result)
        mock_menu.assert_called_once()

    @patch.object(ChatUI, "display_main_menu", side_effect=["1", "5"])
    @patch.object(ChatUI, "display_online_peers")
    def test_start_show_online_peers(self, mock_peers, mock_menu):
        self.ui.start()

        mock_peers.assert_called_once()

    @patch.object(ChatUI, "display_main_menu", side_effect=["2", "5"])
    def test_start_unread_messages(self, mock_menu):

        self.chat_manager.get_unread_count.return_value = {}

        self.ui.start()

        self.chat_manager.get_unread_count.assert_called_once()
    @patch.object(ChatUI, "display_main_menu", side_effect=["3", "5"])
    @patch.object(ChatUI, "change_status", return_value="online")
    def test_start_change_status(self, mock_status, mock_menu):
        callback = Mock()
        self.ui.set_status = callback

        self.ui.start()

        callback.assert_called_once_with("online")

    @patch.object(ChatUI, "display_main_menu", side_effect=["3", "5"])
    @patch.object(ChatUI, "change_status", return_value=None)
    def test_start_invalid_status(self, mock_status, mock_menu):
        callback = Mock()
        self.ui.set_status = callback

        self.ui.start()

        callback.assert_not_called()

    @patch.object(ChatUI, "display_main_menu", side_effect=["3", "5"])
    @patch.object(ChatUI, "change_status", return_value="away")
    def test_start_without_status_callback(self, mock_status, mock_menu):
        self.ui.set_status = None

        self.ui.start()

        mock_status.assert_called_once()

    @patch.object(ChatUI, "display_main_menu", side_effect=["invalid", "5"])
    def test_start_invalid_option(self, mock_menu):
        output = StringIO()

        with redirect_stdout(output):
            self.ui.start()

        self.assertIn("Invalid option", output.getvalue())

    @patch.object(ChatUI, "display_main_menu", side_effect=["4", "5"])
    @patch.object(ChatUI, "start_chat")
    def test_start_chat(self, mock_start_chat, mock_menu):
        self.ui.start()

        mock_start_chat.assert_called_once()

    
    # ==========================================
    # START CHAT
    # ==========================================

    @patch("builtins.input", return_value="")
    @patch.object(ChatUI, "display_online_peers", return_value=[])
    def test_start_chat_no_online_peers(self, mock_display, mock_input):
        self.ui.start_chat()

        mock_display.assert_called_once()

    @patch("builtins.input", side_effect=["/exit"])
    @patch.object(ChatUI, "display_online_peers", return_value=[])
    def test_start_chat_exit_without_peers(self, mock_display, mock_input):
        self.ui.start_chat()

        mock_display.assert_called_once()

    @patch("builtins.input", side_effect=["invalid", "/exit"])
    @patch.object(ChatUI, "display_online_peers")
    def test_start_chat_invalid_peer(self, mock_display, mock_input):
        mock_display.return_value = [
            {"peer": self.peer, "index": 1}
        ]

        output = StringIO()

        with redirect_stdout(output):
            self.ui.start_chat()

        self.assertIn("Invalid peer selection", output.getvalue())

    @patch("builtins.input", side_effect=["1", "/exit"])
    @patch.object(ChatUI, "display_online_peers")
    def test_start_chat_peer_unavailable(self, mock_display, mock_input):
        mock_display.return_value = [
            {"peer": self.peer, "index": 1}
        ]

        self.peer_manager.get_peer.return_value = None

        output = StringIO()

        with redirect_stdout(output):
            self.ui.start_chat()

        self.assertIn(
            "Peer is no longer available.",
            output.getvalue()
        )

    @patch("builtins.input", side_effect=["Alice", ""])
    @patch("chat.chat_ui.ChatClient")
    @patch.object(ChatUI, "chat_loop")
    @patch.object(ChatUI, "display_chat_history")
    @patch.object(ChatUI, "display_chat_header")
    @patch.object(ChatUI, "display_online_peers")
    def test_start_chat_success(
        self,
        mock_display_peers,
        mock_header,
        mock_history,
        mock_chat_loop,
        mock_client,
        mock_input
    ):
        mock_display_peers.side_effect = [
            [{"peer": self.peer, "index": 1}],
            []
        ]

        self.peer_manager.get_peer.return_value = self.peer
        self.chat_manager.get_messages.return_value = []

        conn = Mock()
        mock_client.return_value.connect.return_value = conn

        self.chat_manager.get_messages.return_value = []

        self.ui.start_chat()

        self.chat_manager.select_chat_peer.assert_has_calls([
            call("peer_002"),
            call(None)
        ])

        self.chat_manager.mark_messages_as_read.assert_called_once_with(
            "peer_002"
        )

        self.chat_manager.add_connection.assert_called_once_with(
            "peer_002",
            conn
        )

        self.chat_manager.remove_connection.assert_called_once_with(
            "peer_002"
        )

        mock_chat_loop.assert_called_once()
        mock_client.return_value.close.assert_called_once_with(conn)

    @patch("builtins.input", side_effect=["1", ""])
    @patch("chat.chat_ui.ChatClient")
    @patch.object(ChatUI, "display_online_peers")
    def test_start_chat_connection_error(
        self,
        mock_display,
        mock_client,
        mock_input
    ):
        mock_display.return_value = [
            {"peer": self.peer, "index": 1}
        ]

        self.peer_manager.get_peer.return_value = self.peer 
        self.chat_manager.get_messages.return_value = []

        mock_client.return_value.connect.side_effect = OSError(
            "Connection refused"
        )

        output = StringIO()

        with redirect_stdout(output):
            self.ui.start_chat()

        self.assertIn(
            "Cannot connect to peer",
            output.getvalue()
        )

        self.chat_manager.remove_connection.assert_called_once_with(
            "peer_002"
        )

        mock_client.return_value.close.assert_called_once_with(None)

    # ==========================================
    # RECEIVE MESSAGE WORKER
    # ==========================================

    def test_receive_message_worker(self):
        client = Mock()
        conn = Mock()

        client.receive_messages.side_effect = [
            True,
            False
        ]

        self.ui.receive_message_worker(client, conn)

        self.assertEqual(
            client.receive_messages.call_count,
            2
        )

        for received_call in client.receive_messages.call_args_list:
            self.assertEqual(received_call.args[0], conn)
            self.assertEqual(
                received_call.kwargs["callback"],
                self.ui.incoming_message_queue.put
            )

    def test_receive_message_worker_stop_event(self):
        client = Mock()
        conn = Mock()

        self.ui.receive_stop_event.set()

        self.ui.receive_message_worker(client, conn)

        client.receive_messages.assert_not_called()

    # ==========================================
    # CHAT LOOP
    # ==========================================

    @patch("chat.chat_ui.patch_stdout")
    @patch("chat.chat_ui.threading.Thread")
    @patch.object(ChatUI, "get_user_input", side_effect=["/back"])
    def test_chat_loop_exit(
        self,
        mock_input,
        mock_thread,
        mock_patch_stdout
    ):
        thread = mock_thread.return_value
        thread.is_alive.return_value = False

        client = Mock()
        conn = Mock()

        output = StringIO()

        with redirect_stdout(output):
            self.ui.chat_loop(self.peer, conn, client)

        mock_thread.assert_called_once()
        thread.start.assert_called_once()

        self.assertTrue(self.ui.receive_stop_event.is_set())

        self.assertIn("Exiting chat", output.getvalue())

        client.send_message.assert_not_called()

    @patch("chat.chat_ui.patch_stdout")
    @patch("chat.chat_ui.threading.Thread")
    @patch.object(ChatUI, "get_user_input", side_effect=["Hello", "/back"])
    def test_chat_loop_send_message(
        self,
        mock_input,
        mock_thread,
        mock_patch_stdout
    ):
        thread = mock_thread.return_value
        thread.is_alive.return_value = False

        client = Mock()
        client.send_message.return_value = True

        conn = Mock()

        self.ui.chat_loop(self.peer, conn, client)

        client.send_message.assert_called_once()

        sent_message = client.send_message.call_args.args[1]

        self.assertEqual(sent_message["type"], "chat")
        self.assertEqual(sent_message["sender_id"], "peer_001")
        self.assertEqual(sent_message["receiver_id"], "peer_002")
        self.assertEqual(sent_message["content"], "Hello")
        self.assertIn("timestamp", sent_message)

        self.chat_manager.add_message.assert_called_once_with(
            "peer_002",
            sent_message
        )

        self.assertTrue(self.ui.receive_stop_event.is_set())

    @patch("chat.chat_ui.patch_stdout")
    @patch("chat.chat_ui.threading.Thread")
    @patch.object(ChatUI, "get_user_input", return_value="Hello")
    def test_chat_loop_send_failed(
        self,
        mock_input,
        mock_thread,
        mock_patch_stdout
    ):
        thread = mock_thread.return_value
        thread.is_alive.return_value = False

        client = Mock()
        client.send_message.return_value = False

        output = StringIO()

        with redirect_stdout(output):
            self.ui.chat_loop(self.peer, Mock(), client)

        self.assertIn(
            "Could not send message.",
            output.getvalue()
        )

        self.chat_manager.add_message.assert_not_called()

        self.assertTrue(self.ui.receive_stop_event.is_set())

    @patch("chat.chat_ui.patch_stdout")
    @patch("chat.chat_ui.threading.Thread")
    @patch.object(ChatUI, "get_user_input", return_value="")
    def test_chat_loop_empty_message_exit(
        self,
        mock_input,
        mock_thread,
        mock_patch_stdout
    ):
        thread = mock_thread.return_value
        thread.is_alive.return_value = False

        client = Mock()

        self.ui.chat_loop(self.peer, Mock(), client)

        client.send_message.assert_not_called()

        self.assertTrue(self.ui.receive_stop_event.is_set())

    @patch("chat.chat_ui.patch_stdout")
    @patch("chat.chat_ui.threading.Thread")
    @patch.object(ChatUI, "get_user_input", return_value="/quit")
    def test_chat_loop_quit_command(
        self,
        mock_input,
        mock_thread,
        mock_patch_stdout
    ):
        thread = mock_thread.return_value
        thread.is_alive.return_value = False

        self.ui.chat_loop(self.peer, Mock(), Mock())

        self.assertTrue(self.ui.receive_stop_event.is_set())

    @patch("chat.chat_ui.patch_stdout")
    @patch("chat.chat_ui.threading.Thread")
    @patch.object(ChatUI, "get_user_input", return_value="/exit")
    def test_chat_loop_exit_command(
        self,
        mock_input,
        mock_thread,
        mock_patch_stdout
    ):
        thread = mock_thread.return_value
        thread.is_alive.return_value = False

        self.ui.chat_loop(self.peer, Mock(), Mock())

        self.assertTrue(self.ui.receive_stop_event.is_set())



if __name__ == "__main__":
    unittest.main()
