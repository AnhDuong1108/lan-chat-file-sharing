"""Kiểm thử framing TCP, bắt tay, truyền file theo chunk và điều hướng UI."""

import hashlib
import socket
import struct
import sys
import tempfile
import threading
import unittest
from types import ModuleType
from pathlib import Path
from unittest.mock import Mock, patch

SRC_DIR = str(Path(__file__).resolve().parents[1] / "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from common.message import (
    MAX_METADATA_SIZE,
    encode_message,
    receive_framed_message,
    recv_exact,
    send_framed_message,
)
from config import BUFFER_SIZE, MAX_FILE_SIZE
from file_transfer.file_receiver import FileReceiver, receive_file_data_start
from file_transfer.file_sender import FileSender
from ui import UI


WAIT = 3


def metadata(data, filename="received.bin"):
    """Tạo metadata kiểm thử khớp kích thước và SHA-256 của dữ liệu."""
    return {
        "transfer_id": "transfer-1",
        "peer_id": "B",
        "status": "accepted",
        "direction": "receive",
        "filename": filename,
        "filesize": len(data),
        "file_hash": hashlib.sha256(data).hexdigest(),
    }


class FragmentedSocket:
    """Mô phỏng stream chia nhỏ, tuân thủ giới hạn kích thước của recv."""

    def __init__(self, data, fragment_size=2):
        self.data = data
        self.fragment_size = fragment_size
        self.closed = False

    def recv(self, size):
        chunk = self.data[:min(size, self.fragment_size)]
        self.data = self.data[len(chunk):]
        return chunk

    def shutdown(self, how):
        self.closed = True

    def close(self):
        self.closed = True


class TestFraming(unittest.TestCase):
    def test_fragmented_header_and_coalesced_messages(self):
        """Header bị chia nhỏ và hai frame đi liền vẫn được đọc riêng chính xác."""
        first = {"type": "file_request", "filename": "Tài liệu.txt"}
        second = {"type": "file_response", "status": "accepted"}
        wire = b""
        for message in (first, second):
            data = encode_message(message)
            wire += struct.pack("!I", len(data)) + data
        conn = FragmentedSocket(wire + b"raw-file-data")
        self.assertEqual(receive_framed_message(conn), first)
        self.assertEqual(receive_framed_message(conn), second)
        self.assertEqual(conn.data, b"raw-file-data")

    def test_invalid_header_and_json_close_connection(self):
        """Từ chối frame quá lớn, rỗng, JSON sai, UTF-8 sai hoặc JSON dạng list."""
        frames = [
            struct.pack("!I", MAX_METADATA_SIZE + 1),
            struct.pack("!I", 0),
            struct.pack("!I", 1) + b"{",
            struct.pack("!I", 1) + b"\xff",
            struct.pack("!I", 2) + b"[]",
        ]
        for wire in frames:
            with self.subTest(wire=wire):
                conn = FragmentedSocket(wire)
                self.assertIsNone(receive_framed_message(conn))
                self.assertTrue(conn.closed)

    def test_disconnect_during_header_or_body(self):
        """Mất kết nối giữa frame trả None và đóng stream dở dang."""
        for wire in (b"\x00\x00", struct.pack("!I", 20) + b"{}"):
            conn = FragmentedSocket(wire)
            self.assertIsNone(receive_framed_message(conn))
            self.assertTrue(conn.closed)

    def test_recv_exact_sizes_and_timeout(self):
        """Đọc 0 byte trả bytes rỗng, kích thước sai báo lỗi và timeout trả None."""
        conn = FragmentedSocket(b"abc")
        self.assertEqual(recv_exact(conn, 0), b"")
        for size in (-1, True, 1.5):
            with self.assertRaises(ValueError):
                recv_exact(conn, size)
        failing = Mock()
        failing.recv.side_effect = TimeoutError()
        self.assertIsNone(recv_exact(failing, 4))
        failing.close.assert_called_once()

    def test_send_framing_and_errors(self):
        """sendall gửi header và JSON đầy đủ, từ chối metadata quá lớn hoặc sai."""
        conn = Mock()
        message = {"filename": "ảnh.png"}
        self.assertTrue(send_framed_message(conn, message))
        wire = conn.sendall.call_args.args[0]
        self.assertEqual(struct.unpack("!I", wire[:4])[0], len(wire[4:]))
        self.assertEqual(receive_framed_message(FragmentedSocket(wire)), message)
        self.assertFalse(send_framed_message(conn, []))
        self.assertFalse(send_framed_message(conn, {"data": "x" * MAX_METADATA_SIZE}))
        conn.sendall.side_effect = BrokenPipeError()
        self.assertFalse(send_framed_message(conn, message))
        conn.close.assert_called_once()


class TestFileTransfer(unittest.TestCase):
    def setUp(self):
        """Giả lập API file_utils của Issue 2 và tạo socket có timeout cho mỗi test."""
        utilities = ModuleType("file_transfer.file_utils")
        utilities.validate_file = Mock(
            side_effect=lambda path, mode="source": Path(path).is_file()
        )

        def calculate_hash(path):
            """Tính hash trong test thay cho module chưa được bạn phụ trách cung cấp."""
            with open(path, "rb") as file:
                return hashlib.file_digest(file, "sha256").hexdigest()

        utilities.calculate_file_hash = Mock(side_effect=calculate_hash)
        self.utilities = utilities
        patcher = patch.dict(sys.modules, {"file_transfer.file_utils": utilities})
        patcher.start()
        self.addCleanup(patcher.stop)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.downloads = self.root / "downloads"
        self.sender_socket, self.receiver_socket = socket.socketpair()
        for conn in (self.sender_socket, self.receiver_socket):
            conn.settimeout(WAIT)
            self.addCleanup(conn.close)
        self.sender = FileSender("B", "127.0.0.1", 5001)
        self.sender.conn = self.sender_socket
        self.addCleanup(self.sender.close)
        self.receiver = FileReceiver(self.downloads)

    def run_peer(self, operation):
        """Chạy bên nhận song song và chuyển lỗi của thread về test chính."""
        failures = []

        def worker():
            """Lưu lỗi để test chính kiểm tra sau khi join."""
            try:
                operation()
            except Exception as exc:
                failures.append(exc)

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

        def finish():
            """Đóng socket trước khi join nếu test đã thất bại giữa chừng."""
            self.receiver_socket.close()
            self.sender.close()
            thread.join(WAIT)
            self.assertFalse(thread.is_alive())

        self.addCleanup(finish)
        return thread, failures

    def test_accept_and_transfer_real_tcp(self):
        """Dùng transfer đã Accept qua Chat, đối chiếu ID trên File TCP rồi truyền."""
        listener = socket.socket()
        self.addCleanup(listener.close)
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        listener.settimeout(WAIT)
        self.sender.port = listener.getsockname()[1]
        self.assertTrue(self.sender.connect())
        accepted, _ = listener.accept()
        self.addCleanup(accepted.close)
        accepted.settimeout(WAIT)
        self.receiver_socket = accepted
        data = bytes(range(256)) * 80
        source = self.root / "Tài liệu.bin"
        source.write_bytes(data)
        info = metadata(data, source.name)
        file_manager = Mock()
        file_manager.get_transfer.return_value = info
        progress = []
        self.sender.on_progress = lambda sent, size, percent: progress.append((sent, size, percent))

        def receive():
            """Mô phỏng manager tra transfer đã đăng ký trước khi giao cho receiver."""
            start = receive_file_data_start(accepted)
            self.assertEqual(start, {"type": "file_data_start", "transfer_id": "transfer-1"})
            registered = file_manager.get_transfer(start["transfer_id"])
            self.assertEqual(registered["direction"], "receive")
            self.assertEqual(registered["status"], "accepted")
            self.assertTrue(send_framed_message(accepted, {
                "type": "file_data_ready", "transfer_id": start["transfer_id"], "status": "accept",
            }))
            self.assertTrue(self.receiver.receive_file_data(accepted, registered), self.receiver.last_error)
            self.assertEqual(receive_framed_message(accepted), {"type": "next"})

        thread, failures = self.run_peer(receive)
        sending_info = dict(info, direction="send")
        self.assertTrue(self.sender.send_file_data_start(sending_info), self.sender.last_error)
        self.assertTrue(self.sender.send_file_data(source), self.sender.last_error)
        self.assertTrue(send_framed_message(self.sender.conn, {"type": "next"}))
        thread.join(WAIT)
        self.assertFalse(thread.is_alive())
        self.assertEqual(failures, [])
        file_manager.get_transfer.assert_called_once_with("transfer-1")
        self.assertEqual(sending_info["status"], "accepted")
        self.assertEqual((self.downloads / source.name).read_bytes(), data)
        self.assertEqual(self.sender.bytes_sent, len(data))
        self.assertEqual(self.receiver.bytes_received, len(data))
        self.assertEqual(progress[-1], (len(data), len(data), 100.0))
        self.assertGreater(len(progress), 1)
        self.assertEqual(list(self.downloads.glob("*.part")), [])

    def test_rejected_request_sends_no_file_bytes(self):
        """Transfer pending, rejected hoặc của peer khác không được bắt tay File TCP."""
        info = dict(metadata(b"content"), direction="send")
        with patch("file_transfer.file_sender.send_framed_message") as send:
            for status in ("pending", "rejected", "cancelled", "failed"):
                self.assertFalse(self.sender.send_file_data_start(dict(info, status=status)))
            self.assertFalse(self.sender.send_file_data_start(dict(info, receiver_id="other")))
            self.assertFalse(self.sender.send_file_data(self.root / "source.bin"))
        send.assert_not_called()
        self.assertEqual(self.sender.bytes_sent, 0)

    def test_invalid_response_closes_sender(self):
        """Handshake trả sai transfer_id không được dùng để cho phép gửi bytes."""
        self.assertTrue(send_framed_message(self.receiver_socket, {
            "type": "file_data_ready", "transfer_id": "other", "status": "accept",
        }))
        info = dict(metadata(b"content"), direction="send")
        self.assertFalse(self.sender.send_file_data_start(info))
        self.assertIsNone(self.sender.conn)

    def prepare_accepted_transfer(self, source, data):
        """Cấp metadata đã Accept và giả lập xác nhận handshake từ manager bên nhận."""
        source.write_bytes(data)
        info = dict(metadata(data, source.name), direction="send")
        self.assertTrue(send_framed_message(self.receiver_socket, {
            "type": "file_data_ready", "transfer_id": info["transfer_id"], "status": "accept",
        }))
        self.assertTrue(self.sender.send_file_data_start(info))
        self.assertEqual(
            receive_file_data_start(self.receiver_socket),
            {"type": "file_data_start", "transfer_id": info["transfer_id"]},
        )
        return info

    def test_changed_source_is_rejected_before_data(self):
        """File đổi sau metadata bị từ chối trước khi gửi nội dung."""
        source = self.root / "source.bin"
        self.prepare_accepted_transfer(source, b"original")
        source.write_bytes(b"modified")
        self.assertFalse(self.sender.send_file_data(source))
        self.assertEqual(self.sender.bytes_sent, 0)
        self.assertIsNone(self.sender.conn)

    def test_cancel_during_send_closes_socket(self):
        """Hủy sau chunk đầu đóng socket và kết thúc lần gửi với False."""
        source = self.root / "source.bin"
        self.prepare_accepted_transfer(source, b"x" * (BUFFER_SIZE * 2))
        self.sender.on_progress = lambda *args: self.sender.cancel()
        self.assertFalse(self.sender.send_file_data(source))
        self.assertEqual(self.sender.bytes_sent, BUFFER_SIZE)
        self.assertIsNone(self.sender.conn)

    def test_manager_cancel_event_is_shared_and_not_cleared(self):
        """FileSender dùng đúng Event của manager và không mở lại transfer đã hủy."""
        cancel_event = threading.Event()
        sender = FileSender("B", "127.0.0.1", 5001, cancel_event=cancel_event)
        self.assertIs(sender.cancel_event, cancel_event)
        cancel_event.set()
        with patch("file_transfer.file_sender.socket.create_connection") as connect:
            self.assertFalse(sender.connect())
        connect.assert_not_called()
        self.assertTrue(cancel_event.is_set())

    def test_receiver_obeys_manager_cancel_and_reports_progress(self):
        """Receiver báo tiến độ qua callback và xóa file dở khi Event được bật."""
        cancel_event = threading.Event()
        progress = Mock(side_effect=lambda *args: cancel_event.set())
        receiver = FileReceiver(self.downloads, cancel_event=cancel_event, on_progress=progress)
        self.assertFalse(receiver.receive_file_data(FragmentedSocket(b"abcdef"), metadata(b"abcdef")))
        self.assertEqual(list(self.downloads.iterdir()), [])
        progress.assert_called_once_with(2, 6, 100.0 / 3)

    def test_file_tcp_rejection_closes_sender(self):
        """Manager bên nhận có thể từ chối handshake dù Chat TCP đã Accept trước đó."""
        info = dict(metadata(b"abc"), direction="send")
        self.assertTrue(send_framed_message(self.receiver_socket, {
            "type": "file_data_ready", "transfer_id": info["transfer_id"], "status": "reject",
        }))
        self.assertFalse(self.sender.send_file_data_start(info))
        self.assertIsNone(self.sender.conn)

    def test_receive_empty_file(self):
        """File rỗng được tạo, kiểm tra SHA-256 và hoàn thành với 100 phần trăm."""
        info = metadata(b"")
        self.assertTrue(self.receiver.receive_file_data(self.receiver_socket, info))
        self.assertEqual(self.receiver.output_path.read_bytes(), b"")
        self.assertEqual(self.receiver.progress, 100.0)

    def test_sender_empty_file_and_duplicate_send(self):
        """File rỗng báo 100%, mỗi handshake chỉ cho phép gọi gửi dữ liệu một lần."""
        source = self.root / "empty.bin"
        self.prepare_accepted_transfer(source, b"")
        progress = Mock()
        self.sender.on_progress = progress
        self.assertTrue(self.sender.send_file_data(source))
        progress.assert_called_once_with(0, 0, 100.0)
        self.assertFalse(self.sender.send_file_data(source))

    def test_progress_callback_error_does_not_interrupt_stream(self):
        """Callback tiến độ lỗi vẫn cho phép gửi đủ nội dung."""
        source = self.root / "source.bin"
        self.prepare_accepted_transfer(source, b"abc")
        self.sender.on_progress = Mock(side_effect=RuntimeError("UI unavailable"))
        with self.assertLogs("file_transfer.file_sender", level="ERROR"):
            self.assertTrue(self.sender.send_file_data(source))
        self.assertEqual(recv_exact(self.receiver_socket, 3), b"abc")

    def test_receive_fragmented_data_without_consuming_next_frame(self):
        """Nhiều lần recv nhỏ ghép đủ file và giữ nguyên metadata tiếp theo."""
        data = b"binary\x00\xff" * 4
        info = metadata(data)
        conn = FragmentedSocket(data + b"NEXT", fragment_size=3)
        self.assertTrue(self.receiver.receive_file_data(conn, info))
        self.assertEqual(conn.data, b"NEXT")
        self.assertEqual(self.receiver.output_path.read_bytes(), data)

    def test_incomplete_file_and_hash_mismatch_remove_partial(self):
        """File thiếu byte hoặc sai SHA-256 bị xóa và không xuất hiện ở đích."""
        for data in (b"short", b"x" * 8):
            with self.subTest(data=data):
                info = metadata(b"expected")
                conn = FragmentedSocket(data)
                self.assertFalse(self.receiver.receive_file_data(conn, info))
                self.assertEqual(list(self.downloads.iterdir()), [])
                self.assertTrue(conn.closed)

    def test_existing_destination_is_preserved(self):
        """File trùng tên bị từ chối và dữ liệu đã có vẫn nguyên vẹn."""
        self.downloads.mkdir()
        destination = self.downloads / "received.bin"
        destination.write_bytes(b"old")
        self.assertFalse(self.receiver.receive_file_data(FragmentedSocket(b"new"), metadata(b"new")))
        self.assertEqual(destination.read_bytes(), b"old")
        self.assertEqual(list(self.downloads.iterdir()), [destination])

    def test_concurrent_receivers_do_not_overwrite_each_other(self):
        """Hai transfer cùng tên chỉ công bố một file hoàn chỉnh và xóa file tạm."""
        results = []
        barrier = threading.Barrier(2)

        def receive(data):
            """Bắt đầu hai lần nhận cùng lúc với receiver riêng."""
            receiver = FileReceiver(self.downloads)
            barrier.wait(WAIT)
            results.append(receiver.receive_file_data(FragmentedSocket(data), metadata(data)))

        workers = [
            threading.Thread(target=receive, args=(data,), daemon=True)
            for data in (b"first", b"second")
        ]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(WAIT)
            self.assertFalse(worker.is_alive())
        self.assertCountEqual(results, [True, False])
        self.assertIn((self.downloads / "received.bin").read_bytes(), (b"first", b"second"))
        self.assertEqual(len(list(self.downloads.iterdir())), 1)

    def test_invalid_metadata_is_rejected_before_writing(self):
        """Từ chối đường dẫn vượt thư mục, tên thiết bị và kích thước, hash sai."""
        updates = [
            {"filename": "../escape.bin"}, {"filename": "C:\\escape.bin"},
            {"filename": "sub/file"}, {"filename": "file:stream"},
            {"filename": "NUL.txt"}, {"filename": "bad."}, {"filename": "bad\x00name"},
            {"filesize": -1}, {"filesize": True}, {"filesize": MAX_FILE_SIZE + 1},
            {"file_hash": "bad"}, {"transfer_id": ""},
            {"status": "pending"}, {"direction": "send"},
        ]
        for update in updates:
            with self.subTest(update=update):
                info = metadata(b"")
                info.update(update)
                self.assertFalse(self.receiver.receive_file_data(FragmentedSocket(b""), info))
                self.assertIsNone(self.receiver.output_path)
        self.assertFalse(self.downloads.exists())

    def test_handshake_is_separate_from_file_data(self):
        """FileManager đọc handshake riêng, receiver chỉ đọc nội dung sau xác thực."""
        info = metadata(b"abc")
        self.assertTrue(send_framed_message(self.sender_socket, {
            "type": "file_data_start", "transfer_id": info["transfer_id"],
        }))
        self.sender_socket.sendall(b"abc")
        self.assertEqual(receive_file_data_start(self.receiver_socket)["transfer_id"], info["transfer_id"])
        self.assertTrue(self.receiver.receive_file_data(self.receiver_socket, info))

    def test_receiver_rejects_invalid_handshake(self):
        """Handshake sai loại hoặc thiếu ID không được đưa cho manager tra transfer."""
        for message in ({"type": "file_request"}, {"type": "file_data_start", "transfer_id": ""}):
            self.assertTrue(send_framed_message(self.sender_socket, message))
            self.assertIsNone(receive_file_data_start(self.receiver_socket))

    def test_receiver_disk_error_removes_partial(self):
        """Lỗi ghi đĩa không để lại file dở dang trong thư mục tải xuống."""
        with patch.object(self.receiver, "save_file", side_effect=OSError("disk full")):
            self.assertFalse(self.receiver.receive_file_data(FragmentedSocket(b"abc"), metadata(b"abc")))
        self.assertEqual(list(self.downloads.iterdir()), [])

    def test_connection_and_file_errors(self):
        """Kết nối lỗi trả False, kiểm tra file dùng đúng API validate_file của Issue 2."""
        with patch("file_transfer.file_sender.socket.create_connection", side_effect=TimeoutError()):
            self.assertFalse(self.sender.connect())
        self.assertFalse(self.sender.verify_file(self.root / "missing"))
        self.utilities.validate_file.assert_called_with(self.root / "missing", mode="source")
        self.assertFalse(self.sender.verify_file(self.root))
        self.sender.close()
        self.sender.close()


class TestCombinedUI(unittest.TestCase):
    def test_real_chat_ui_returns_to_main_menu(self):
        """UI thật mở menu chat rồi trở về menu chính với đầu vào, đầu ra giả lập."""
        from prompt_toolkit.application import create_app_session
        from prompt_toolkit.input import DummyInput
        from prompt_toolkit.output import DummyOutput

        with create_app_session(input=DummyInput(), output=DummyOutput()):
            ui = UI(Mock(), Mock(), None)
            with patch("builtins.input", side_effect=["2", "5", "3", "4"]), patch("builtins.print"):
                ui.start()

    def test_injected_chat_ui_is_reused_by_file_ui(self):
        """Issue 2 có thể truyền ChatUI đã nối FileManager, cùng đối tượng được FileUI dùng."""
        chat_ui, file_manager = Mock(), Mock()
        file_ui_module = ModuleType("file_transfer.file_ui")
        file_ui_module.FileUI = Mock()
        ui = UI(Mock(), Mock(), file_manager, chat_ui=chat_ui)
        with patch.dict(sys.modules, {"file_transfer.file_ui": file_ui_module}):
            ui.display_file_menu()
            ui.display_file_menu()
        file_ui_module.FileUI.assert_called_once_with(
            file_manager, ui.chat_manager, ui.peer_manager, chat_ui
        )
        self.assertEqual(file_ui_module.FileUI.return_value.start.call_count, 2)
        self.assertIs(ui.chat_ui, chat_ui)

    def test_menu_routes_to_chat_and_injected_file_ui(self):
        """Menu gọi ChatUI và FileUI bên ngoài rồi quay lại để xử lý lựa chọn tiếp."""
        peers, chats, files, file_ui = Mock(), Mock(), Mock(), Mock()
        peers.get_all_peers.return_value = []
        with patch("ui.ChatUI") as chat_type:
            ui = UI(peers, chats, files, file_ui=file_ui)
        with patch("builtins.input", side_effect=["bad", "1", "2", "3", "4"]), patch("builtins.print"):
            ui.start()
        peers.get_all_peers.assert_called_once()
        chat_type.return_value.start.assert_called_once()
        file_ui.start.assert_called_once()
        self.assertIs(ui.file_manager, files)

    def test_file_menu_reports_missing_dependencies(self):
        """Menu File Manager báo rõ khi các thành phần phụ thuộc chưa được cung cấp."""
        with patch("ui.ChatUI"):
            ui = UI(Mock(), Mock(), None)
        with patch("builtins.print") as output:
            ui.display_file_menu()
        self.assertIn("FileManager", output.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
