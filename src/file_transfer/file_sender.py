"""Gửi file sau khi FileManager đã xử lý Accept qua Chat TCP.

FileManager gọi connect(), send_file_data_start(transfer_info), rồi send_file_data().
Handshake File TCP là file_data_start chứa transfer_id có sẵn. Bên nhận xác thực
transfer rồi trả file_data_ready với cùng ID và status accept hoặc reject.
"""

import hashlib
import logging
import socket
import threading
from pathlib import Path

from common.message import receive_framed_message, send_framed_message
from config import BUFFER_SIZE, CONNECT_TIMEOUT, MAX_FILE_SIZE

logger = logging.getLogger(__name__)


class FileSender:
    """Mỗi đối tượng quản lý một kết nối và một lần gửi đang hoạt động."""

    def __init__(self, peer_id, ip, port, *, on_progress=None, cancel_event=None):
        """
        Chuẩn bị thông tin peer nhận và trạng thái truyền.

        :param on_progress: Callback của manager nhận (bytes_sent, filesize, progress).
        :param cancel_event: Event dùng chung với FileManager để yêu cầu hủy.
        """
        self.peer_id = peer_id
        self.ip = ip
        self.port = port
        self.conn = None
        self.transfer_info = None
        self.bytes_sent = 0
        self.progress = 0.0
        self.last_error = None
        self.cancel_event = cancel_event if cancel_event is not None else threading.Event()
        self.on_progress = on_progress

    def connect(self) -> bool:
        """Kết nối tới FileServer, giữ nguyên cờ hủy do FileManager quản lý."""
        self.close()
        self.last_error = None
        self.bytes_sent = 0
        self.progress = 0.0
        if self.cancel_event.is_set():
            self.last_error = "Transfer cancelled"
            return False
        try:
            self.conn = socket.create_connection((self.ip, self.port), CONNECT_TIMEOUT)
        except OSError as exc:
            self.last_error = str(exc)
            return False
        return True

    def verify_file(self, file_path) -> bool:
        """Dùng validate_file(file_path, mode='source') do Issue 2 cung cấp."""
        from file_transfer.file_utils import validate_file

        return validate_file(file_path, mode="source")

    def send_file_data_start(self, transfer_info) -> bool:
        """
        Gửi handshake cho transfer đã được chấp nhận và chờ FileManager bên nhận.

        :param transfer_info: Transfer do FileManager cấp, có transfer_id, peer_id
            hoặc receiver_id, filename, filesize, file_hash, direction và status.
            Chiều phải là send, trạng thái accepted hoặc transferring.
        :return: True khi nhận file_data_ready với status accept và đúng ID.
        """
        self.last_error = None
        if self.conn is None or self.transfer_info is not None or self.cancel_event.is_set():
            self.last_error = "Connection unavailable or handshake already completed"
            return False
        if not isinstance(transfer_info, dict):
            self.last_error = "Invalid transfer metadata"
            return False
        info = transfer_info.copy()
        transfer_id = info.get("transfer_id")
        if (
            not isinstance(transfer_id, str)
            or not transfer_id.strip()
            or info.get("direction") != "send"
            or info.get("status") not in ("accepted", "transferring")
            or info.get("receiver_id", info.get("peer_id")) != self.peer_id
        ):
            self.last_error = "Transfer has not been accepted for this peer"
            return False
        conn = self.conn
        try:
            start = {"type": "file_data_start", "transfer_id": transfer_id}
            if not send_framed_message(conn, start):
                raise OSError("Cannot send file_data_start")
            response = receive_framed_message(conn)
            if (
                response is None
                or response.get("type") != "file_data_ready"
                or response.get("transfer_id") != transfer_id
                or response.get("status") != "accept"
            ):
                raise OSError("File TCP handshake rejected or invalid")
            if self.cancel_event.is_set():
                raise OSError("Transfer cancelled")
            self.transfer_info = info
            return True
        except OSError as exc:
            self.last_error = str(exc)
            self.close()
            return False

    def send_file_data(self, file_path) -> bool:
        """
        Gửi đúng filesize byte sau khi handshake File TCP hoàn tất.

        Đọc theo chunk, so khớp nội dung với metadata của manager, báo tiến độ
        qua callback và kiểm tra Event dùng chung. FileManager cập nhật vòng đời
        transfer từ kết quả trả về. Bên nhận còn kiểm tra SHA-256 sau khi lưu.
        """
        info = self.transfer_info
        if self.conn is None or info is None:
            self.last_error = "File TCP handshake has not completed"
            return False
        conn = self.conn
        try:
            if self.cancel_event.is_set():
                raise OSError("Transfer cancelled")
            if (
                not self.verify_file(file_path)
                or Path(file_path).name != info.get("filename")
                or type(info.get("filesize")) is not int
                or not 0 <= info["filesize"] <= MAX_FILE_SIZE
                or not isinstance(info.get("file_hash"), str)
            ):
                raise ValueError("File unavailable or metadata does not match")
            expected_hash = info["file_hash"].lower()
            self.bytes_sent = 0
            self.progress = 0.0
            digest = hashlib.sha256()
            with open(file_path, "rb") as file:
                # Kiểm tra lại file vì file có thể đổi trong khi chờ Accept.
                for chunk in iter(lambda: file.read(BUFFER_SIZE), b""):
                    if self.cancel_event.is_set():
                        raise OSError("Transfer cancelled")
                    digest.update(chunk)
                if file.tell() != info["filesize"] or digest.hexdigest() != expected_hash:
                    raise ValueError("File changed after request")
                file.seek(0)
                digest = hashlib.sha256()
                while self.bytes_sent < info["filesize"]:
                    if self.cancel_event.is_set():
                        raise OSError("Transfer cancelled")
                    chunk = file.read(min(BUFFER_SIZE, info["filesize"] - self.bytes_sent))
                    if not chunk:
                        raise OSError("File ended before advertised size")
                    conn.sendall(chunk)
                    digest.update(chunk)
                    self.bytes_sent += len(chunk)
                    self._update_progress(info["filesize"])
                if digest.hexdigest() != expected_hash:
                    raise ValueError("File changed during transfer")
                if self.cancel_event.is_set():
                    raise OSError("Transfer cancelled")
                if info["filesize"] == 0:
                    self._update_progress(0)
            self.last_error = None
            return True
        except (OSError, TypeError, ValueError) as exc:
            self.last_error = str(exc)
            self.close()
            return False
        finally:
            # Một yêu cầu accepted chỉ được sử dụng để gửi dữ liệu một lần.
            self.transfer_info = None

    def _update_progress(self, filesize):
        """Cập nhật phần trăm và báo cho UI hoặc ghi log theo từng phần trăm."""
        previous = int(self.progress)
        self.progress = 100.0 if filesize == 0 else self.bytes_sent * 100.0 / filesize
        if self.on_progress is not None:
            try:
                self.on_progress(self.bytes_sent, filesize, self.progress)
            except Exception:
                logger.exception("Could not display file transfer progress")
        elif int(self.progress) != previous:
            logger.info("File transfer progress %.1f%%", self.progress)

    def cancel(self):
        """Báo hủy và đóng socket để đánh thức thao tác TCP đang chờ."""
        self.cancel_event.set()
        self.close()

    def close(self) -> None:
        """Đóng kết nối và bỏ metadata của handshake. Có thể gọi nhiều lần."""
        conn = self.conn
        self.conn = None
        self.transfer_info = None
        if conn is not None:
            try:
                conn.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            conn.close()
