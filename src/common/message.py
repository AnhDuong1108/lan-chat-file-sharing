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