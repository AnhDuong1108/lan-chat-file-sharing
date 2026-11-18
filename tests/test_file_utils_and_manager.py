import hashlib
import os
import queue
import socket
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

SRC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from chat.chat_manager import ChatManager
from common.message import encode_message, send_framed_message
from file_transfer.file_manager import FileManager
from file_transfer.file_utils import (
    calculate_file_hash,
    get_file_info,
    read_file_chunks,
    validate_file,
    write_file_chunks,
)
from peer_discovery.peer_manager import PeerManager


class TestFileUtils(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.sample_file = self.root / "sample.txt"
        self.sample_content = b"Hello, Computer Networking! This is a test file chunk."
        with open(self.sample_file, "wb") as f:
            f.write(self.sample_content)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_calculate_file_hash(self):
        expected_hash = hashlib.sha256(self.sample_content).hexdigest()
        actual_hash = calculate_file_hash(self.sample_file)
        self.assertEqual(actual_hash, expected_hash)

        # File not found
        with self.assertRaises(FileNotFoundError):
            calculate_file_hash(self.root / "non_existent.bin")

    def test_get_file_info(self):
        info = get_file_info(self.sample_file)
        self.assertEqual(info["filename"], "sample.txt")
        self.assertEqual(info["filesize"], len(self.sample_content))
        self.assertEqual(info["extension"], ".txt")
        self.assertEqual(info["filehash"], hashlib.sha256(self.sample_content).hexdigest())
        self.assertEqual(info["file_hash"], info["filehash"])

        with self.assertRaises(FileNotFoundError):
            get_file_info(self.root / "does_not_exist.pdf")

    def test_validate_file_source_mode(self):
        # Hợp lệ
        self.assertTrue(validate_file(self.sample_file, mode="source"))
        # Không tồn tại
        self.assertFalse(validate_file(self.root / "fake.txt", mode="source"))
        # Đường dẫn rỗng
        self.assertFalse(validate_file("", mode="source"))

    def test_validate_file_destination_mode(self):
        dest_file = self.root / "dest_subdir" / "output.pdf"
        self.assertTrue(validate_file(dest_file, mode="destination"))

        # Ký tự cấm trong tên file
        invalid_name = self.root / "invalid*name?.pdf"
        self.assertFalse(validate_file(invalid_name, mode="destination"))

    def test_read_and_write_file_chunks(self):
        chunks = list(read_file_chunks(self.sample_file, chunk_size=10))
        self.assertTrue(len(chunks) > 1)
        reconstructed = b"".join(chunks)
        self.assertEqual(reconstructed, self.sample_content)

        output_path = self.root / "written.txt"
        written_bytes = write_file_chunks(output_path, chunks)
        self.assertEqual(written_bytes, len(self.sample_content))
        with open(output_path, "rb") as f:
            self.assertEqual(f.read(), self.sample_content)


class TestFileManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.sample_file = self.root / "test_doc.bin"
        self.sample_content = b"Binary test content for file transfer"
        with open(self.sample_file, "wb") as f:
            f.write(self.sample_content)

        self.peer_manager = PeerManager("peer_sender", username="SenderUser", tcp_port=5000)
        self.chat_manager = ChatManager("peer_sender", self.peer_manager)
        self.file_manager = FileManager(self.peer_manager, self.chat_manager)
        self.chat_manager.set_file_manager(self.file_manager)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_file_request_and_register(self):
        req = self.file_manager.create_file_request("peer_receiver", str(self.sample_file))
        self.assertIn("transfer_id", req)
        self.assertEqual(req["filename"], "test_doc.bin")
        self.assertEqual(req["filesize"], len(self.sample_content))
        self.assertEqual(req["sender_id"], "peer_sender")
        self.assertEqual(req["receiver_id"], "peer_receiver")

        # Kiểm tra transfer trong active_transfers
        status = self.file_manager.get_transfer_status(req["transfer_id"])
        self.assertEqual(status, "pending")

        transfer = self.file_manager.get_transfer(req["transfer_id"])
        self.assertIsNotNone(transfer)
        self.assertEqual(transfer["direction"], "send")

    def test_receive_file_puts_into_queue(self):
        transfer_id = "transfer_recv_123"
        notification = {
            "type": "file_notification_request",
            "transfer_id": transfer_id,
            "sender_id": "peer_remote",
            "receiver_id": "peer_sender",
            "filename": "remote_doc.pdf",
            "filesize": 1024,
            "file_hash": "a" * 64,
        }

        success = self.file_manager.receive_file(notification)
        self.assertTrue(success)
        self.assertEqual(self.file_manager.get_transfer_status(transfer_id), "pending")

        # Kiểm tra đưa vào queue
        self.assertFalse(self.file_manager.file_request_queue.empty())
        item = self.file_manager.file_request_queue.get_nowait()
        self.assertEqual(item["transfer_id"], transfer_id)

    def test_accept_and_reject_file(self):
        transfer_id = "transfer_accept_test"
        notification = {
            "type": "file_notification_request",
            "transfer_id": transfer_id,
            "sender_id": "peer_remote",
            "receiver_id": "peer_sender",
            "filename": "remote_doc.pdf",
            "filesize": 1024,
            "file_hash": "b" * 64,
        }
        self.file_manager.receive_file(notification)

        # Chấp nhận file
        with patch.object(self.chat_manager, "send_file_response") as mock_response:
            res = self.file_manager.accept_file(transfer_id)
            self.assertTrue(res)
            self.assertEqual(self.file_manager.get_transfer_status(transfer_id), "accepted")
            mock_response.assert_called_once()
            args, kwargs = mock_response.call_args
            self.assertEqual(args[0], "peer_remote")
            self.assertEqual(args[1]["status"], "accept")

        # Từ chối file khác
        transfer_id_2 = "transfer_reject_test"
        notification2 = {
            "type": "file_notification_request",
            "transfer_id": transfer_id_2,
            "sender_id": "peer_remote",
            "receiver_id": "peer_sender",
            "filename": "unwanted.exe",
            "filesize": 2048,
            "file_hash": "c" * 64,
        }
        self.file_manager.receive_file(notification2)

        with patch.object(self.chat_manager, "send_file_response") as mock_response:
            res = self.file_manager.reject_file(transfer_id_2)
            self.assertTrue(res)
            self.assertEqual(self.file_manager.get_transfer_status(transfer_id_2), "rejected")
            mock_response.assert_called_once()
            args, kwargs = mock_response.call_args
            self.assertEqual(args[1]["status"], "reject")

    def test_cancel_transfer(self):
        req = self.file_manager.create_file_request("peer_target", str(self.sample_file))
        tid = req["transfer_id"]
        self.assertTrue(self.file_manager.cancel_transfer(tid))
        self.assertEqual(self.file_manager.get_transfer_status(tid), "cancelled")


class TestChatManagerFileNotifications(unittest.TestCase):
    def setUp(self):
        self.peer_manager = PeerManager("peer_A", username="Alice", tcp_port=5000)
        self.chat_manager = ChatManager("peer_A", self.peer_manager)

    def test_send_file_request_and_get_notifications(self):
        mock_conn = Mock()
        self.chat_manager.add_connection("peer_B", mock_conn)

        req = {
            "transfer_id": "transfer_999",
            "sender_id": "peer_A",
            "filename": "hello.png",
            "filesize": 500,
            "file_hash": "d" * 64,
        }

        res = self.chat_manager.send_file_request("peer_B", req)
        self.assertTrue(res)
        mock_conn.sendall.assert_called_once()

        notifs = self.chat_manager.get_file_notifications("peer_B")
        self.assertEqual(len(notifs), 1)
        self.assertEqual(notifs[0]["transfer_id"], "transfer_999")
        self.assertEqual(notifs[0]["status"], "pending")

        pending = self.chat_manager.get_pending_file_notifications()
        self.assertEqual(len(pending), 1)

    def test_send_file_response_and_update_status(self):
        mock_conn = Mock()
        self.chat_manager.add_connection("peer_B", mock_conn)

        notif = {
            "transfer_id": "transfer_888",
            "filename": "report.pdf",
            "filesize": 1000,
            "status": "accept",
        }

        res = self.chat_manager.send_file_response("peer_B", notif)
        self.assertTrue(res)
        mock_conn.sendall.assert_called_once()

        self.chat_manager.update_status_respone("transfer_888", "completed")
        notifs = self.chat_manager.get_file_notifications("peer_B")
        self.assertEqual(notifs[0]["status"], "completed")

    def test_handle_file_notification_routing(self):
        mock_file_manager = Mock()
        self.chat_manager.set_file_manager(mock_file_manager)

        req_notif = {
            "type": "file_notification_request",
            "transfer_id": "transfer_777",
            "sender_id": "peer_B",
            "receiver_id": "peer_A",
            "filename": "test.txt",
            "filesize": 100,
        }
        self.chat_manager.handle_file_notification(req_notif)
        mock_file_manager.receive_file.assert_called_once_with(req_notif)

        resp_notif = {
            "type": "file_notification_respone",
            "transfer_id": "transfer_777",
            "sender_id": "peer_B",
            "receiver_id": "peer_A",
            "status": "accept",
        }
        self.chat_manager.handle_file_notification(resp_notif)
        mock_file_manager.handle_notification.assert_called_once_with(resp_notif)


if __name__ == "__main__":
    unittest.main()
