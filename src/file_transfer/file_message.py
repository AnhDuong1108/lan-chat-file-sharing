import time
import re


FILE_RESPONSE_STATUS = {
    "accept",
    "reject"
}


def create_file_request(
    transfer_id: str,
    sender_id: str,
    receiver_id: str,
    filename: str,
    filesize: int,
    file_hash: str
) -> dict:
    """
    Tạo thông điệp yêu cầu truyền file.
    """

    return {
        "type": "file_request",
        "transfer_id": transfer_id,
        "sender_id": sender_id,
        "receiver_id": receiver_id,
        "filename": filename,
        "filesize": filesize,
        "file_hash": file_hash,
        "timestamp": time.time()
    }


def create_file_response(
    transfer_id: str,
    status: str,
) -> dict:
    """
    Tạo thông điệp phản hồi yêu cầu truyền file.
    """

    return {
        "type": "file_response",
        "transfer_id": transfer_id,
        "status": status,
        "timestamp": time.time()
    }


def validate_file_message(message: dict) -> bool:
    """
    Kiểm tra tính hợp lệ của thông điệp truyền file.
    """

    if not isinstance(message, dict):
        return False

    msg_type = message.get("type")

    # Kiểm tra timestamp
    timestamp = message.get("timestamp")

    if (
        isinstance(timestamp, bool)
        or not isinstance(timestamp, (int, float))
        or timestamp <= 0
    ):
        return False

    # File request
    if msg_type == "file_request":

        required_fields = [
            "transfer_id",
            "sender_id",
            "receiver_id",
            "filename",
            "filesize",
            "file_hash"
        ]

        if not all(field in message for field in required_fields):
            return False

        transfer_id = message["transfer_id"]
        sender_id = message["sender_id"]
        receiver_id = message["receiver_id"]
        filename = message["filename"]
        filesize = message["filesize"]
        file_hash = message["file_hash"]

        if not all(
            isinstance(value, str) and value.strip()
            for value in (
                transfer_id,
                sender_id,
                receiver_id,
                filename,
                file_hash
            )
        ):
            return False

        if sender_id == receiver_id:
            return False

        if (
            isinstance(filesize, bool)
            or not isinstance(filesize, int)
            or filesize < 0
        ):
            return False

        # SHA-256 gồm 64 ký tự hexadecimal
        if not re.fullmatch(r"[a-fA-F0-9]{64}", file_hash):
            return False

        return True

    # File response
    elif msg_type == "file_response":

        transfer_id = message.get("transfer_id")
        status = message.get("status")

        if not isinstance(transfer_id, str) or not transfer_id.strip():
            return False

        if status not in FILE_RESPONSE_STATUS:
            return False

        # message là trường tùy chọn
        if "message" in message:
            if not isinstance(message["message"], str):
                return False

        return True

    return False