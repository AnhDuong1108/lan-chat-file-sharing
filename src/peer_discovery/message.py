import json

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

def create_presence_message(peer_id: str, username: str, tcp_port: int) -> dict:
    """Tạo dictionary chứa thông tin presence."""

    return {
        "type": "presence",
        "peer_id": peer_id,
        "username": username,
        "tcp_port": tcp_port,
        "status": "online"
    }

def validate_presence_message(message: dict) -> bool:
    """Kiểm tra cấu trúc và giá trị của presence message."""

    if not isinstance(message, dict):
        return False

    required_fields = { 
        "type",
        "peer_id",
        "username",
        "tcp_port",
        "status"
    }

    # Phải có đủ trường bắt buộc.
    if not required_fields.issubset(message.keys()):
        return False

    # Kiểm tra loại message.
    if message["type"] != "presence":
        return False

    # Kiểm tra peer_id và username.
    if not isinstance(message["peer_id"], str):
        return False

    if not message["peer_id"].strip():
        return False

    if not isinstance(message["username"], str):
        return False

    if not message["username"].strip():
        return False

    # bool là subclass của int trong Python,
    # nên cần kiểm tra kiểu chính xác.
    if type(message["tcp_port"]) is not int:
        return False

    if not 1 <= message["tcp_port"] <= 65535:
        return False

    # Phiên bản hiện tại chỉ hỗ trợ presence online.
    if message["status"] != "online":
        return False

    return True