"""Nhận file theo kích thước và chỉ công bố file khi SHA-256 hợp lệ."""

import os
import logging
import re
import tempfile
import threading
from pathlib import Path

from common.message import receive_framed_message
from config import BUFFER_SIZE, MAX_FILE_SIZE

logger = logging.getLogger(__name__)


def receive_file_data_start(conn):
    """
    Đọc handshake File TCP để FileManager tra cứu transfer_id đã đăng ký.

    FileManager kiểm tra peer, chiều nhận và trạng thái rồi gửi frame
    file_data_ready với cùng transfer_id và status accept hoặc reject.
    :return: Dictionary handshake hoặc None nếu frame sai.
    """
    message = receive_framed_message(conn)
    if (
        message is None
        or message.get("type") != "file_data_start"
        or not isinstance(message.get("transfer_id"), str)
        or not message["transfer_id"].strip()
    ):
        return None
    return message


class FileReceiver:
    """Mỗi đối tượng xử lý một transfer tại một thời điểm, sau xác thực của manager."""

    def __init__(self, download_dir, *, on_progress=None, cancel_event=None):
        """Lưu thư mục đích, callback tiến độ và Event hủy dùng chung với manager."""
        self.download_dir = Path(download_dir)
        self.bytes_received = 0
        self.progress = 0.0
        self.output_path = None
        self.last_error = None
        self.on_progress = on_progress
        self.cancel_event = cancel_event if cancel_event is not None else threading.Event()

    @staticmethod
    def _validate_transfer_info(info):
        """Kiểm tra metadata lưu file sau khi manager đã đối chiếu handshake."""
        if not isinstance(info, dict):
            return False
        if info.get("direction") != "receive" or info.get("status") not in ("accepted", "transferring"):
            return False
        transfer_id = info.get("transfer_id")
        filename = info.get("filename")
        filesize = info.get("filesize")
        file_hash = info.get("file_hash")
        if not isinstance(transfer_id, str) or not transfer_id.strip():
            return False
        if type(filesize) is not int or not 0 <= filesize <= MAX_FILE_SIZE:
            return False
        if not isinstance(file_hash, str) or re.fullmatch(r"[0-9a-fA-F]{64}", file_hash) is None:
            return False
        if not isinstance(filename, str) or not filename or filename in (".", ".."):
            return False
        if filename.endswith((" ", ".")) or any(
            ord(char) < 32 or char in '<>:"/\\|?*' for char in filename
        ):
            return False
        stem = filename.split(".", 1)[0].rstrip(" ").upper()
        reserved = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
        return stem not in reserved and re.fullmatch(r"(COM|LPT)[1-9¹²³]", stem) is None

    def receive_file_data(self, conn, transfer_info) -> bool:
        """
        Nhận đúng filesize byte vào file tạm rồi kiểm tra SHA-256 trước khi lưu.

        :param conn: Socket đã xử lý file_data_start, có timeout do FileServer đặt.
        :param transfer_info: Transfer có sẵn do FileManager xác thực.
        :return: True nếu lưu thành công. File dở dang bị xóa khi lỗi.
        """
        self.bytes_received = 0
        self.progress = 0.0
        self.output_path = None
        self.last_error = None
        temporary_path = None
        try:
            if not self._validate_transfer_info(transfer_info):
                raise ValueError("Invalid transfer metadata")
            info = transfer_info.copy()
            self.download_dir.mkdir(parents=True, exist_ok=True)
            destination = self.download_dir.resolve() / info["filename"]
            # File tạm riêng cho mỗi lần nhận để tránh ghi đè giữa các transfer.
            descriptor, name = tempfile.mkstemp(prefix=".transfer-", suffix=".part", dir=self.download_dir)
            os.close(descriptor)
            temporary_path = Path(name)
            while self.bytes_received < info["filesize"]:
                if self.cancel_event.is_set():
                    raise OSError("Transfer cancelled")
                remaining = info["filesize"] - self.bytes_received
                chunk = conn.recv(min(BUFFER_SIZE, remaining))
                if not chunk:
                    raise OSError("Connection closed before file was complete")
                self.save_file(temporary_path, chunk)
                self.bytes_received += len(chunk)
                self._update_progress(info["filesize"])
            if not self.verify_file(temporary_path, info["file_hash"]):
                raise ValueError("File SHA-256 does not match metadata")
            if self.cancel_event.is_set():
                raise OSError("Transfer cancelled")
            # Công bố file đã kiểm tra, thất bại nếu tên đích đã tồn tại.
            os.link(temporary_path, destination)
            self.output_path = destination
            self.progress = 100.0
            if info["filesize"] == 0:
                self._update_progress(0)
            return True
        except (OSError, TypeError, ValueError) as exc:
            self.last_error = str(exc)
            # Phần dữ liệu chưa đọc thuộc transfer lỗi, đóng để tránh lệch framing.
            try:
                conn.close()
            except OSError:
                pass
            return False
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    def save_file(self, file_path, data):
        """Ghi nối tiếp một chunk nhị phân xuống file tạm."""
        with open(file_path, "ab") as file:
            file.write(data)

    def verify_file(self, file_path, expected_hash) -> bool:
        """Dùng calculate_file_hash() của Issue 2 để so với file_hash trong metadata."""
        from file_transfer.file_utils import calculate_file_hash

        try:
            return calculate_file_hash(file_path) == expected_hash.lower()
        except (OSError, AttributeError):
            return False

    def _update_progress(self, filesize):
        """Báo số byte và phần trăm cho FileManager mà không sửa vòng đời transfer."""
        self.progress = 100.0 if filesize == 0 else self.bytes_received * 100.0 / filesize
        if self.on_progress is not None:
            try:
                self.on_progress(self.bytes_received, filesize, self.progress)
            except Exception:
                logger.exception("Could not display file transfer progress")
