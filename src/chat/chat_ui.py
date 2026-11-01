""" Màn hình hiển thị trên terminal """
import threading

from sympy import content

from chat_manager import ChatManager
from peer_discovery.peer_manager import PeerManager
from datetime import datetime, time
from chat.chat_client import connect_to_peer, send_message, receive_messages
from threading import Thread

def display_online_peers(peer_manager: PeerManager) -> list:

    peers = peer_manager.get_online_peers()
    list_peer = []

    print("\n========== ONLINE PEERS ==========")

    if not peers:
        print("No peers are currently online.")
        return

    for index, peer in enumerate(peers, start=1):
        list_peer.append({"peer": peer, "index": index})
        status = peer["status"]

        print(
            f"{index}. {peer['username']} "
            f"({peer['peer_id']}) - {status}"
        )

    print("==================================")
    return list_peer


def display_chat_history(peer: dict, messages: list):

    peer_name = peer["username"] 

    if not messages:
        print("No messages yet.")
        return

    print(f"\n========== HISTORY CHAT WITH {peer_name} ==========")

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
            peer = peer_manager.get_peer(peer_id)

            try:
                # Lấy kết nối TCP đến peer từ peer_manager
                conn = connect_to_peer(
                    peer["ip"],
                    peer["tcp_port"]
                )

                # Tạo kết nối từ peer_id đến chat_manager để gửi và nhận tin nhắn
                chat_manager.connections[peer_id] = conn

                # Start receiving messages in background
                threading.Thread(
                    target=receive_messages,
                    args=(conn, chat_manager.handle_incoming_message),
                    daemon=True
                ).start()

            except OSError as e:
                print(f"Cannot connect to peer: {e}")
                chat_manager.current_chat_peer = None
                continue

            continue

        while True:

            message = get_user_input()

            if message == "/back":
                break

            if message == "/exit":
                return

            if message:
                chat_message = {
                    "type": "chat",
                    "sender_id": peer_manager.self_peer_id,
                    "receiver_id": peer_id,
                    "content": message,
                    "timestamp": time.time()
                }

                send_message(conn, chat_message)

def change_status():
    print("\n===== CHANGE STATUS =====")
    print("1. Online")
    print("2. Away")

    choice = input("Choose status: ").strip()

    if choice == "1":
        return "online"
    elif choice == "2":
        return "away"

    print("Invalid choice")
    return None