import socket
from typing import Callable
from weakref import WeakKeyDictionary

from common.message import decode_message, encode_message
from config import BUFFER_SIZE, CONNECT_TIMEOUT


class ChatClient:
    def __init__(self, peer_id, ip, tcp_port):
        self.peer_id = peer_id
        self.ip = ip
        self.tcp_port = tcp_port
        self._buffers = WeakKeyDictionary()

    def connect(self) -> socket.socket:
        """Kết nối đến peer, chuyển lỗi kết nối cho bên gọi xử lý."""
        conn = socket.create_connection((self.ip, self.tcp_port), CONNECT_TIMEOUT)
        conn.settimeout(None)
        return conn

    def send_message(self, conn, message: dict) -> bool:
        if conn is None:
            return False
        try:
            data = encode_message(message) + b"\n"
        except (TypeError, ValueError, RecursionError):
            return False
        try:
            conn.sendall(data)
        except OSError:
            # Có thể một phần tin đã được gửi. Đóng socket để lần gửi sau
            # không nối tiếp vào dòng JSON còn dang dở.
            self.close(conn)
            return False
        return True

    def receive_messages(self, conn, callback: Callable[[dict], None]) -> bool|None:
        """Gọi callback cho một tin hợp lệ. Mỗi socket cần một luồng đọc."""
        if conn is None:
            return False

        buffer = self._buffers.pop(conn, b"")
        while True:
            raw_message, separator, remaining = buffer.partition(b"\n")
            if separator:
                buffer = remaining
                try:
                    message = decode_message(raw_message)
                except (ValueError, RecursionError):
                    continue
                if buffer:
                    self._buffers[conn] = buffer
                callback(message)
                return True

            try:
                data = conn.recv(BUFFER_SIZE)
            except socket.timeout:
                if buffer:
                    self._buffers[conn] = buffer
                return None
            except OSError:
                return False
            if not data:
                return False
            buffer += data

    def close(self, conn) -> None:
        if conn is None:
            return
        self._buffers.pop(conn, None)
        try:
            conn.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        conn.close()

    def is_connected(self, conn) -> bool:
        """Kiểm tra socket cục bộ đã kết nối và còn mở."""
        if conn is None:
            return False
        try:
            conn.getpeername()
        except OSError:
            return False
        return True
