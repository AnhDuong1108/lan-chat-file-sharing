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