""" Màn hình hiển thị trên terminal """
from datetime import datetime

from chat.chat_client import ChatClient
from chat.chat_manager import ChatManager
from chat.chat_message import create_chat_message, validate_chat_message
from peer_discovery.peer_manager import PeerManager


class ChatUI:

    def __init__(self, peer_manager: PeerManager, chat_manager: ChatManager, set_status=None):

        self.peer_manager = peer_manager
        self.chat_manager = chat_manager
        self.set_status = set_status

    # ==========================================
    # DISPLAY MAIN MENU
    # ==========================================
    

    def display_main_menu(self):
        print("\n========== P2P CHAT ==========")
        print("1. Show online peers")
        print("2. View unread messages")
        print("3. Change status")
        print("4. Start chat")
        print("5. Exit")
        print("==============================")

        return input("Choose option: ").strip()

    def display_chat_header(self, peer):
        print(f"\n========== CHAT WITH {peer['username']} ==========")
        print(f"Peer ID: {peer['peer_id']}")
        print(f"IP: {peer['ip']}")
        print(f"Status: {peer['status']}")
        print("Commands: /back | /exit")
        print("==========================================")    

    def display_error(self, message):
        print(f"\n[ERROR] {message}")

    def display_success(self, message):
        print(f"\n[SUCCESS] {message}")

    # ==========================================
    # DISPLAY ONLINE PEERS
    # ==========================================

    def display_online_peers(self) -> list:

        peers = self.peer_manager.get_online_peers()
        list_peer = []

        print("\n========== ONLINE PEERS ==========")

        if not peers:
            print("No peers are currently online.")
            return []

        for index, peer in enumerate(peers, start=1):

            list_peer.append({
                "peer": peer,
                "index": index
            })

            status = peer["status"]

            print(
                f"{index}. {peer['username']} "
                f"({peer['peer_id']}) - {status}"
            )

        print("==================================")

        return list_peer

    # ==========================================
    # DISPLAY CHAT HISTORY
    # ==========================================

    def display_chat_history(self, peer: dict, messages: list):

        peer_name = peer["username"]

        if not messages:
            print("No messages yet.")
            return

        print(
            f"\n========== HISTORY CHAT WITH {peer_name} =========="
        )

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

    # ==========================================
    # DISPLAY UNREAD NOTIFICATIONS
    # ==========================================

    def display_unread_notifications(self, unread_data: dict):

        print("\n========== UNREAD MESSAGES ==========")

        for peer_name, count in unread_data.items():

            print(f"{peer_name}: {count}")

        print("=====================================")

    # ==========================================
    # GET USER INPUT
    # ==========================================

    def get_user_input(self) -> str:

        message = input("You: ").strip()

        return message

    # ==========================================
    # DISPLAY INCOMING MESSAGE
    # ==========================================

    def display_incoming_message(self, message: dict):

        print("\n[NEW MESSAGE]")

        print(f"From: {message.get('sender_name', message['sender_id'])}")
        print(f"Content: {message['content']}")
        print(f"Time: {message['timestamp']}")

    def handle_incoming_message(self, message: dict):
        if not validate_chat_message(message):
            return
        sender_id = message["sender_id"]
        if message["receiver_id"] != self.chat_manager.self_peer_id:
            return
        if sender_id == self.chat_manager.self_peer_id:
            return
        try:
            datetime.fromtimestamp(message["timestamp"])
        except (TypeError, ValueError, OverflowError, OSError):
            return

        self.chat_manager.handle_incoming_message(message)
        if self.chat_manager.current_chat_peer == sender_id:
            self.display_incoming_message(message)

    # ==========================================
    # CHANGE STATUS
    # ==========================================

    def change_status(self):

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

    # ==========================================
    # START CHAT UI
    # ==========================================

    def start_chat(self):

        while True:

            # ==================================
            # DISPLAY ONLINE PEERS
            # ==================================

            list_peer = self.display_online_peers()

            if not list_peer:
                choice = input(
                    "\nPress Enter to refresh or /exit to quit: "
                ).strip()

                if choice == "/exit":
                    return

                continue

            # ==================================
            # SELECT PEER
            # ==================================

            peer_in4 = input("\nSelect peer: ").strip()

            if peer_in4 == "/exit":
                return

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

            # ==================================
            # SELECT CONVERSATION
            # ==================================

            peer = self.peer_manager.get_peer(peer_id)

            if peer is None:
                print("Peer is no longer available.")
                continue

            client = ChatClient(peer_id, peer["ip"], peer["tcp_port"])
            self.chat_manager.select_chat_peer(peer_id)
            conn = None
            try:
                self.chat_manager.mark_messages_as_read(peer_id)
                self.display_chat_header(peer)
                self.display_chat_history(peer, self.chat_manager.get_messages(peer_id))
                try:
                    conn = client.connect()
                except OSError as exc:
                    self.display_error(f"Cannot connect to peer: {exc}")
                    continue

                self.chat_manager.add_connection(peer_id, conn)
                self.chat_loop(peer, conn)
            finally:
                self.chat_manager.select_chat_peer(None)
                self.chat_manager.remove_connection(peer_id)
                client.close(conn)

    def chat_loop(self, peer, conn):
        client = ChatClient(peer["peer_id"], peer["ip"], peer["tcp_port"])
        
        while True:

            message = self.get_user_input()
            
            if message in ("/back", "/exit"):
                print("Exiting chat...")
                return

            if not message:
                continue

            chat_message = create_chat_message(
                sender_id=self.peer_manager.self_peer_id,
                receiver_id=peer["peer_id"],
                content=message
            )

            success = client.send_message(conn, chat_message)

            if not success:
                self.display_error("Could not send the message.")
                return
            self.chat_manager.add_message(peer["peer_id"], chat_message)

    def start(self):

        while True:

            choice = self.display_main_menu()

            # 1. View online peers
            if choice == "1":

                self.display_online_peers()

            # 2. View unread messages
            elif choice == "2":

                self.display_unread_notifications(
                    self.chat_manager.get_unread_count()
                )

            # 3. Change status
            elif choice == "3":

                status = self.change_status()
                if status is not None and self.set_status is not None:
                    self.set_status(status)

            # 4. Chat with a peer
            elif choice == "4":

                self.start_chat()

            # 5. Exit
            elif choice == "5":

                print("Exiting P2P Chat App...")
                return

            else:

                print("Invalid option. Please try again.")
