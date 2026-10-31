""" Màn hình hiển thị trên terminal """
from chat_manager import ChatManager
from peer_discovery.peer_manager import PeerManager
from datetime import datetime
from chat.chat_client import send_message

def display_online_peers(peer_manager: PeerManager) -> list:

    peers = peer_manager.get_online_peers()
    list_peer = []

    print("\n========== ONLINE PEERS ==========")

    if not peers:
        print("No peers are currently online.")
        return

    for index, peer in enumerate(peers, start=1):
        list_peer.append({"peer": peer, "index": index})
        print(
            f"[{index}] "
            f"{peer['username']} - "
            f"{peer['ip']}"
        )

    print("==================================")
    return list_peer


def display_chat_history(peer: dict, messages: list):

    peer_name = peer["username"]

    print(f"\n========== HISTORY CHAT WITH {peer_name} ==========")

    if not messages:
        print("No messages yet.")
        return

    previous_timestamp = None

    for message in messages:

        current_timestamp = message["timestamp"]

        # Hiển thị timestamp nếu:
        # - Đây là tin nhắn đầu tiên
        # - Hoặc cách tin nhắn trước ít nhất 5 phút
        if (
            previous_timestamp is None
            or current_timestamp - previous_timestamp >= 300
        ):
            formatted_time = datetime.fromtimestamp(
                current_timestamp
            ).strftime("%H:%M")

            print(f"\n---------- {formatted_time} ----------")

        print(
            f"{message.get('sender_id', 'Unknown')}: "
            f"{message['content']}"
        )

        previous_timestamp = current_timestamp

    print("===================================================")


def display_unread_notifications(unread_data: dict):

    print("\n========== UNREAD MESSAGES ==========")

    for peer_name, count in unread_data.items():
        print(f"{peer_name}: {count}")

    print("=====================================")

def get_user_input():

    message = input("You: ").strip()

    return message

def display_incoming_message(message: dict):

    print("\n[NEW MESSAGE]")

    print(f"From: {message['sender_name']}")
    print(f"Content: {message['content']}")
    print(f"Time: {message['timestamp']}")


def start_chat_ui(peer_manager: PeerManager, chat_manager: ChatManager):

    while True:
        # Display online peers
        list_peer = display_online_peers(peer_manager)
        # nhập thứ tự peer trên màn hình terminal hoặc nhập tên peer
        peer_in4 = input("Select peer: ").strip()
        peer_id = None

        for item in list_peer:

            peer = item["peer"]
            index = item["index"]

            if (
                peer["username"].lower() == peer_in4.lower()
                or str(index) == peer_in4
            ):
                peer_id = peer["peer_id"]
                break

        if peer_id is None:
            print("Invalid peer selection!")
            continue
                

        # Select conversation
        chat_manager.select_chat_peer(peer_id)

        messages = chat_manager.get_messages(peer_id)

        display_chat_history(peer_id, messages)

        conn = chat_manager.connections.get(peer_id)

        if conn is None:
            print("Not connected to this peer!")
            continue

        while True:

            message = get_user_input()

            if message == "/back":
                break

            if message == "/exit":
                return

            if message:
                send_message(conn, message)