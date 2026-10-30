def create_chat_message(sender_id: str, receiver_id: str, content: str) -> dict:
    return {
        "type": "chat",
        "sender_id": sender_id,
        "receiver_id": receiver_id,
        "content": content
    }

def validate_chat_message(message: dict) -> bool:
    if not isinstance(message, dict):
        return False

    required_fields = {
        "type",
        "sender_id",
        "receiver_id",
        "content"
    }

    if not required_fields.issubset(message.keys()):
        return False

    if message["type"] != "chat":
        return False

    if not isinstance(message["sender_id"], str) or not message["sender_id"].strip():
        return False

    if not isinstance(message["receiver_id"], str) or not message["receiver_id"].strip():
        return False

    if not isinstance(message["content"], str) or not message["content"].strip():
        return False

    return True

def handle_chat_message(message: dict):
    if not validate_chat_message(message):
        print("Invalid chat message")
        return

    sender_id = message["sender_id"]
    content = message["content"]

    print(f"Message from {sender_id}: {content}")