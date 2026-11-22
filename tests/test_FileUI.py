"""
TEST FILE UI
1. Khởi tạo FileUI.

2. Hiển thị thông báo lỗi, thành công và menu.

3. Xử lý yêu cầu nhận file (Accept / Reject).

4. Gửi file cho peer.

5. Hiển thị trạng thái truyền file.

6. Hủy phiên truyền file.

7. Liệt kê file trong thư mục docs.

8. Kiểm tra và validate lệnh /send.

9. Kiểm tra vòng lặp start().
"""
import sys
import os
import queue
import tempfile
import threading
import unittest
from unittest.mock import MagicMock, patch

SRC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from file_transfer.file_ui import FileUI 


class TestFileUI(unittest.TestCase):

    def setUp(self):
        terminal = patch("file_transfer.file_ui.PromptSession")
        self.session_type = terminal.start()
        self.addCleanup(terminal.stop)
        self.file_manager = MagicMock()
        self.chat_manager = MagicMock()
        self.peer_manager = MagicMock()

        self.file_manager.file_request_queue = queue.Queue()
        self.file_manager.lock = threading.Lock()
        self.file_manager.active_transfers = []
        self.file_manager.completed_transfers = []

        # Tránh tạo thư mục docs/downloads thật trong project
        with patch("os.makedirs"):
            self.ui = FileUI(
                file_manager=self.file_manager,
                chat_manager=self.chat_manager,
                peer_manager=self.peer_manager
            )

        self.temp_dir = tempfile.TemporaryDirectory()
        self.ui.docs_dir = self.temp_dir.name
        self.ui.downloads_dir = self.temp_dir.name

    def tearDown(self):
        self.temp_dir.cleanup()

    # =====================================================
    # 1. INITIALIZATION
    # =====================================================

    def test_init(self):
        """Kiểm tra khởi tạo FileUI."""
        self.assertEqual(self.ui.file_manager, self.file_manager)
        self.assertEqual(self.ui.chat_manager, self.chat_manager)
        self.assertEqual(self.ui.peer_manager, self.peer_manager)

        self.assertEqual(
            self.file_manager.on_progress,
            self.ui.display_transfer_progress
        )

    def test_init_without_file_manager(self):
        """Khởi tạo khi không có FileManager."""
        with patch("os.makedirs"):
            ui = FileUI(
                file_manager=None,
                chat_manager=self.chat_manager,
                peer_manager=self.peer_manager
            )

        self.assertIsNone(ui.file_manager)

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

    def test_start_returns_after_help_and_sessions(self):
        self.ui.session.prompt.side_effect = ["/sessions", "/help", "/quit"]
        with (
            patch.object(self.ui, "show_transfer_status") as sessions,
            patch.object(self.ui, "display_help_menu") as help_menu,
            patch("builtins.input", side_effect=AssertionError("Menu must use PromptSession")) as user_input,
            patch("builtins.print") as output,
        ):
            self.ui.start()
        sessions.assert_called_once_with()
        self.assertEqual(help_menu.call_count, 2)
        self.assertEqual(self.ui.session.prompt.call_count, 3)
        output.assert_any_call("Return to Main Menu ...")
        user_input.assert_not_called()

    def test_display_transfer_progress_peer_fallback(self):
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
                self.peer_manager.get_peer.return_value = peer
                with patch("builtins.print") as output:
                    self.ui.display_transfer_progress(transfer)
                self.assertIn(f"Peer: {name}", output.call_args.args[0])
                self.assertIn("50.0%", output.call_args.args[0])

    # =====================================================
    # 2. DISPLAY FUNCTIONS
    # =====================================================

    @patch("builtins.print")
    def test_display_help_menu(self, mock_print):
        """Kiểm tra hiển thị menu hướng dẫn."""
        self.ui.display_help_menu()

        output = " ".join(
            str(call.args[0])
            for call in mock_print.call_args_list
        )

        self.assertIn("/requests", output)
        self.assertIn("/send", output)
        self.assertIn("/sessions", output)
        self.assertIn("/cancel", output)
        self.assertIn("/files", output)
        self.assertIn("/quit", output)

    @patch.object(FileUI, "print_styled")
    def test_display_error(self, mock_print):
        self.ui.display_error("Test error")

        mock_print.assert_called_once()

    @patch.object(FileUI, "print_styled")
    def test_display_success(self, mock_print):
        self.ui.display_success("Test success")

        mock_print.assert_called_once()

    # =====================================================
    # 3. PENDING FILE REQUESTS
    # =====================================================

    @patch("builtins.input", return_value="y")
    @patch.object(FileUI, "print_styled")
    @patch("builtins.print")
    def test_accept_pending_request(
        self, mock_print, mock_styled, mock_input
    ):
        """Người dùng đồng ý nhận file."""
        request = {
            "transfer_id": "T001",
            "sender_id": "A001",
            "filename": "demo.txt",
            "filesize": 1024
        }

        self.file_manager.file_request_queue.put(request)

        self.peer_manager.get_peer.return_value = {
            "username": "Peer A"
        }

        self.ui.process_pending_requests()

        self.file_manager.accept_file.assert_called_once_with("T001")
        self.file_manager.reject_file.assert_not_called()

    @patch("builtins.input", return_value="n")
    @patch.object(FileUI, "print_styled")
    @patch("builtins.print")
    def test_reject_pending_request(
        self, mock_print, mock_styled, mock_input
    ):
        """Người dùng từ chối nhận file."""
        request = {
            "transfer_id": "T002",
            "sender_id": "A001",
            "filename": "demo.txt",
            "filesize": 1024
        }

        self.file_manager.file_request_queue.put(request)

        self.ui.process_pending_requests()

        self.file_manager.reject_file.assert_called_once_with("T002")
        self.file_manager.accept_file.assert_not_called()

    @patch("builtins.print")
    def test_no_pending_requests(self, mock_print):
        """Không có yêu cầu nhận file đang chờ."""
        self.ui.process_pending_requests()

        mock_print.assert_any_call(
            "No pending file reception requests."
        )

    # =====================================================
    # 4. SEND FILE
    # =====================================================

    @patch.object(FileUI, "display_success")
    @patch("builtins.print")
    def test_send_file_success(self, mock_print, mock_success):
        """Gửi file thành công."""
        filename = "demo.txt"

        file_path = os.path.join(self.temp_dir.name, filename)

        with open(file_path, "w") as f:
            f.write("Hello World")

        self.peer_manager.get_online_peers.return_value = [
            {
                "peer_id": "B001",
                "username": "Peer B"
            }
        ]

        self.file_manager.send_file.return_value = "T001"

        self.ui.send_file_to_peer(filename, "B001")

        self.file_manager.send_file.assert_called_once_with(
            "B001", file_path
        )

        mock_success.assert_called_once()

    @patch.object(FileUI, "display_error")
    @patch("builtins.print")
    def test_send_file_peer_not_found(
        self, mock_print, mock_error
    ):
        """Không tìm thấy peer cần gửi."""
        self.peer_manager.get_online_peers.return_value = []

        self.ui.send_file_to_peer("demo.txt", "B001")

        mock_error.assert_called_once_with(
            "Selected peer not found."
        )

        self.file_manager.send_file.assert_not_called()

    @patch.object(FileUI, "display_error")
    @patch("builtins.print")
    def test_send_file_not_found(
        self, mock_print, mock_error
    ):
        """File không tồn tại."""
        self.peer_manager.get_online_peers.return_value = [
            {
                "peer_id": "B001",
                "username": "Peer B"
            }
        ]

        self.ui.send_file_to_peer("missing.txt", "B001")

        mock_error.assert_called_once()

        self.file_manager.send_file.assert_not_called()

    @patch.object(FileUI, "display_error")
    @patch("builtins.print")
    def test_send_file_exception(
        self, mock_print, mock_error
    ):
        """Xử lý exception khi gửi file."""
        filename = "demo.txt"

        file_path = os.path.join(self.temp_dir.name, filename)

        with open(file_path, "w") as f:
            f.write("Hello")

        self.peer_manager.get_online_peers.return_value = [
            {
                "peer_id": "B001",
                "username": "Peer B"
            }
        ]

        self.file_manager.send_file.side_effect = Exception(
            "Connection failed"
        )

        self.ui.send_file_to_peer(filename, "B001")

        mock_error.assert_called_once()

    # =====================================================
    # 5. TRANSFER STATUS
    # =====================================================

    @patch("builtins.print")
    def test_show_transfer_status_empty(self, mock_print):
        """Không có phiên truyền file."""
        self.ui.show_transfer_status()

        mock_print.assert_any_call(
            "No file transfer sessions found."
        )

    @patch("builtins.print")
    def test_show_active_transfer(self, mock_print):
        """Hiển thị phiên truyền file đang hoạt động."""
        self.file_manager.active_transfers = [
            {
                "transfer_id": "T001",
                "filename": "demo.txt",
                "direction": "send",
                "status": "transferring",
                "progress": 50.0
            }
        ]

        self.ui.show_transfer_status()

        output = " ".join(
            str(call.args[0])
            for call in mock_print.call_args_list
        )

        self.assertIn("T001", output)
        self.assertIn("demo.txt", output)
        self.assertIn("50.0%", output)

    @patch("builtins.print")
    def test_show_completed_transfer(self, mock_print):
        """Hiển thị phiên truyền file hoàn tất."""
        self.file_manager.completed_transfers = [
            {
                "transfer_id": "T002",
                "filename": "report.pdf",
                "direction": "receive",
                "status": "completed",
                "progress": 100.0
            }
        ]

        self.ui.show_transfer_status()

        output = " ".join(
            str(call.args[0])
            for call in mock_print.call_args_list
        )

        self.assertIn("T002", output)
        self.assertIn("report.pdf", output)
        self.assertIn("100.0%", output)

    # =====================================================
    # 6. CANCEL TRANSFER
    # =====================================================

    @patch("builtins.print")
    def test_cancel_transfer_success(self, mock_print):
        """Hủy phiên truyền file thành công."""
        self.file_manager.active_transfers = [
            {
                "transfer_id": "T001",
                "filename": "demo.txt",
                "status": "transferring"
            }
        ]

        self.file_manager.cancel_transfer.return_value = True

        with patch("builtins.input", return_value="1"):
            with patch.object(FileUI, "display_success") as mock_success:
                self.ui.cancel_active_transfer()

        self.file_manager.cancel_transfer.assert_called_once_with(
            "T001"
        )

        mock_success.assert_called_once()

    @patch("builtins.print")
    def test_cancel_transfer_invalid_id(self, mock_print):
        """Hủy phiên truyền file với ID không hợp lệ."""
        self.file_manager.active_transfers = [
            {
                "transfer_id": "T001",
                "filename": "demo.txt",
                "status": "transferring"
            }
        ]

        with patch("builtins.input", return_value="999"):
            with patch.object(FileUI, "display_error") as mock_error:
                self.ui.cancel_active_transfer()

        self.file_manager.cancel_transfer.assert_not_called()
        mock_error.assert_called_once()

    def test_cancel_without_active_transfers(self):
        """Không có phiên truyền file để hủy."""
        with patch("builtins.print") as mock_print:
            self.ui.cancel_active_transfer()

        mock_print.assert_any_call(
            "No active file transfer sessions available to cancel."
        )

    # =====================================================
    # 7. FILE LIST
    # =====================================================

    def test_list_docs_files(self):
        """Liệt kê các file trong docs."""
        filename = "demo.txt"

        file_path = os.path.join(self.temp_dir.name, filename)

        with open(file_path, "w") as f:
            f.write("Hello World")

        with patch("builtins.print") as mock_print:
            self.ui.list_docs_files()

        output = " ".join(
            str(call.args[0])
            for call in mock_print.call_args_list
        )

        self.assertIn(filename, output)

    def test_list_docs_empty(self):
        """Thư mục docs không có file."""
        with patch("builtins.print") as mock_print:
            self.ui.list_docs_files()

        mock_print.assert_any_call(
            "The docs/ directory is empty. You can add files here for quick file sharing."
        )

    def test_get_available_files(self):
        """Lấy danh sách file có sẵn."""
        for filename in ["a.txt", "b.pdf"]:
            with open(
                os.path.join(self.temp_dir.name, filename), "w"
            ) as f:
                f.write("test")

        files = self.ui.get_available_files()

        self.assertCountEqual(files, ["a.txt", "b.pdf"])

    # =====================================================
    # 8. VALIDATE COMMAND
    # =====================================================

    def test_validate_send_command_valid(self):
        """Lệnh /send hợp lệ."""
        result = self.ui.validate_send_command(
            "/send demo.txt B001 B002"
        )

        self.assertEqual(
            result,
            (True, "demo.txt", ["B001", "B002"])
        )

    def test_validate_send_command_missing_receiver(self):
        """Thiếu receiver."""
        result = self.ui.validate_send_command(
            "/send demo.txt"
        )

        self.assertEqual(result, (False, None, []))

    def test_validate_send_command_invalid_prefix(self):
        """Sai cú pháp lệnh."""
        result = self.ui.validate_send_command(
            "/upload demo.txt B001"
        )

        self.assertEqual(result, (False, None, []))

    # =====================================================
    # 9. FILENAME DETECTION
    # =====================================================

    def test_is_filename_in_send_command(self):
        """Nhận diện tên file từ lệnh /send."""
        result = self.ui.is_filename_in_message(
            "/send demo.txt B001"
        )

        self.assertEqual(result, "demo.txt")

    def test_is_filename_in_message(self):
        """Nhận diện tên file xuất hiện trong nội dung."""
        with open(
            os.path.join(self.temp_dir.name, "demo.txt"), "w"
        ) as f:
            f.write("test")

        result = self.ui.is_filename_in_message(
            "Please send demo.txt"
        )

        self.assertEqual(result, "demo.txt")

    def test_is_filename_in_empty_message(self):
        """Nội dung rỗng."""
        self.assertIsNone(
            self.ui.is_filename_in_message("")
        )


if __name__ == "__main__":
    unittest.main()
