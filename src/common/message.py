import json
import socket
import struct

MAX_METADATA_SIZE = 64 * 1024

def encode_message(message: dict) -> bytes:
    """Chuyển dictionary thành JSON UTF-8 bytes."""
    if not isinstance(message, dict):
        raise TypeError("Message must be a dictionary")
    try:
        json_str = json.dumps(
            message,
            # quyết định có chuyển các ký tự Unicode thành dạng \uXXXX hay không
            ensure_ascii = False
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "Message cannot be serialized to JSON"
        ) from exc

    return json_str.encode("utf-8")


def decode_message(data: bytes) -> dict:
    """
    Giải mã JSON bytes thành dictionary.

    TypeError: data không phải bytes.
    UnicodeDecodeError: bytes không phải UTF-8 hợp lệ.
    ValueError: JSON không hợp lệ hoặc top-level
                không phải JSON object.
    """

    if not isinstance(data, bytes):
        raise TypeError("Data must be bytes")

    try:
        json_string = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise UnicodeDecodeError(
            exc.encoding,
            exc.object,
            exc.start,
            exc.end,
            "Message must use UTF-8 encoding"
        ) from exc

    """
    exc.encoding	Bảng mã đang được sử dụng
    exc.object	    Dữ liệu bytes gây ra lỗi
    exc.start	    Vị trí bắt đầu của đoạn bytes không giải mã được
    exc.end	        Vị trí kết thúc đoạn bytes đó
    """

    try:
        message = json.loads(json_string)
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid JSON message") from exc

    if not isinstance(message, dict):
        raise ValueError(
            "Top-level JSON value must be an object"
        )

    return message


def _close_connection(conn):
    """Đóng kết nối lỗi để dữ liệu dở dang không bị đọc thành frame mới."""
    try:
        conn.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    conn.close()


def recv_exact(conn: socket.socket, size: int) -> bytes | None:
    """
    Nhận đúng số byte yêu cầu, kể cả khi TCP chia dữ liệu thành nhiều lần nhận.

    :param conn: Socket TCP đang kết nối.
    :param size: Số byte không âm cần đọc. Giá trị 0 trả về bytes rỗng.
    :return: Dữ liệu đủ kích thước hoặc None khi mất kết nối, lỗi hay timeout.
    :raises ValueError: Nếu size không phải số nguyên không âm.
    """
    if type(size) is not int or size < 0:
        raise ValueError("Size must be a non-negative integer")
    data = bytearray()
    try:
        while len(data) < size:
            chunk = conn.recv(min(4096, size - len(data)))
            if not chunk:
                _close_connection(conn)
                return None
            data.extend(chunk)
    except OSError:
        _close_connection(conn)
        return None
    return bytes(data)


def send_framed_message(conn: socket.socket, message: dict) -> bool:
    """
    Gửi JSON UTF-8 với header độ dài 4 byte theo thứ tự byte mạng.

    :return: True nếu gửi đủ frame, False nếu JSON quá lớn, sai hoặc socket lỗi.
    """
    try:
        data = encode_message(message)
    except (TypeError, ValueError, RecursionError):
        return False
    if not 0 < len(data) <= MAX_METADATA_SIZE:
        return False
    try:
        conn.sendall(struct.pack("!I", len(data)) + data)
    except OSError:
        _close_connection(conn)
        return False
    return True


def receive_framed_message(conn: socket.socket) -> dict | None:
    """
    Nhận một frame JSON tối đa MAX_METADATA_SIZE byte, giữ nguyên byte phía sau.

    :return: Dictionary hoặc None nếu frame sai hay kết nối bị gián đoạn.
    """
    header = recv_exact(conn, 4)
    if header is None:
        return None
    size = struct.unpack("!I", header)[0]
    if not 0 < size <= MAX_METADATA_SIZE:
        _close_connection(conn)
        return None
    data = recv_exact(conn, size)
    if data is None:
        return None
    try:
        return decode_message(data)
    except (TypeError, ValueError, RecursionError):
        _close_connection(conn)
        return None
