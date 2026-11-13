""" Màn hình hiển thị trên terminal """
"""
Lỗi hiện tại:
1. không cập nhật được status
"""
from datetime import datetime
import os
import queue
import re
import threading
from chat.chat_client import ChatClient
from chat.chat_manager import ChatManager
from chat.chat_message import create_chat_message, validate_chat_message
from peer_discovery.broadcast import PresenceBroadcaster, broadcast_presence
from peer_discovery.peer_manager import PeerManager
from file_transfer.file_manager import FileManager
from typing import Dict, Optional
from config import FILE_REQUEST_TIMEOUT

from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit import print_formatted_text

import logging
logger = logging.getLogger(__name__)

class ChatUI:
    def __init__(self, peer_manager: PeerManager, chat_manager: ChatManager, set_status=None):

        self.peer_manager = peer_manager
        self.chat_manager = chat_manager
        self.set_status = set_status
        self.end = False
        self.leave = False

        #In màu
        self.style = Style.from_dict({
            "prompt": "#00ff87 bold",
            "command": "#00afff bold",
            "success": "#00ff91fd",
            "error": "#ff5f5f bold",
            "warning": "#ffaf00",
            "system": "#888888",
            "peer": "#5fd7ff bold",
            "timestamp": "#888888 italic",
        })

        self.session = PromptSession(style=self.style,
                                    erase_when_done=True)

        self.receive_thread = None
        self.incoming_message_queue = queue.Queue()
        self.receive_stop_event = threading.Event()

        self.file_dir = os.path.abspath("docs")

        self.file_manager: Optional[FileManager] = None
        self.presence_broadcaster = PresenceBroadcaster(
            self.peer_manager.self_peer_id, 
            self.peer_manager.username,
            self.peer_manager.tcp_port)
        self.presence_broadcaster._thread.start()

        # Current chat peer
        self.peer_current = {}

        # Message timestamps
        self.last_message_time = {}
        # Lưu thông báo
        self.notifications = []

    # ==========================================
    # DISPLAY MAIN MENU
    # ==========================================
    
    def set_file_manager(self, file_manager: FileManager):
        self.file_manager = file_manager

    def display_chat_header(self, peer):
        print(f"\n========== CHAT WITH {peer['username']} ==========")
        print(f"Peer ID: {peer['peer_id']}")
        print(f"IP: {peer['ip']}")
        print(f"Status: {peer['status']}")
        print("Commands: /leave | /quit")
        print("==========================================")    

    def display_error(self, message):
        self.print_styled(
            ("class:error", "[ERROR] "),
            ("", message)
        )

    def display_success(self, message):
        self.print_styled(
            ("class:success", "[SUCCESS] "),
            ("", message)
        )
    # ==========================================
    # DISPLAY ONLINE PEERS
    # ==========================================

    def get_username(self, args, list_peer) -> str | None:
        for item in list_peer:
            if item["peer"]["username"] == args:
                return item["peer"]["username"]

            if str(item["index"]) == args:
                return item["peer"]["username"]
        return None

    def display_online_peers(self):

        peers = self.peer_manager.get_online_peers() + self.peer_manager.get_away_peers()
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

    def get_online_peers_list(self) -> list:
    
        peers = self.peer_manager.get_online_peers()
        list_peer = []

        if not peers:
            return []

        for index, peer in enumerate(peers, start=1):

            list_peer.append({
                "peer": peer,
                "index": index
            })

        return list_peer

    # ==========================================
    # DISPLAY CHAT HISTORY
    # ==========================================

    def display_chat_history(self, peer: dict, messages: list[Dict]):
        
        peer_name = peer["username"]

        if not messages:
            print("No messages yet.")
            return

        print(
            f"\n========== HISTORY CHAT WITH {peer_name} =========="
        )

        previous_timestamp = None

        for message in messages:
            sender = self.peer_manager.get_peer(message.get("sender_id"))

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

            if sender is None:
                username = self.peer_manager.username
            else:
                username = sender["username"]

            self.print_styled(
                ("class:peer", f"[{username}] "),
                ("", message["content"])
            )
           

            previous_timestamp = current_timestamp

        print("===================================================")

    # ==========================================
    # DISPLAY UNREAD NOTIFICATIONS
    # ==========================================

    def display_unread_notifications(self, unread_data: dict):

        print("\n========== UNREAD MESSAGES ==========")

        for peer_id, count in unread_data.items():
            peer_name = self.peer_manager.get_peer(peer_id).get("username", peer_id)

            print(f"{peer_name}: {count}")

        print("=====================================")

    # ==========================================
    # GET USER INPUT
    # ==========================================

    def get_user_input(self) -> str:

        message = self.session.prompt(
        [("class:prompt", "> ")]
        )

        return message.strip()

    # ==========================================
    # DISPLAY INCOMING MESSAGE
    # ==========================================

    def print_styled(self, *fragments):
        """In nội dung có định dạng màu trên terminal."""

        print_formatted_text(
            FormattedText(fragments),
            style=self.style
        )

    def display_incoming_message(self, message: dict):

        sender_id = message["sender_id"]
        peer = self.peer_manager.get_peer(sender_id)

        sender_name = (
            message.get("sender_name")
            or (peer or {}).get("username", sender_id)
        )

        timestamp = message["timestamp"]

        last_time = self.last_message_time.get(sender_id)

        is_new_message = (
            last_time is None or timestamp - last_time >= 300
        )

        if is_new_message:
            formatted_time = datetime.fromtimestamp(
                timestamp
            ).strftime("%H:%M")

            self.print_styled(
                ("class:timestamp", f"\n---------- {formatted_time} ----------")
            )

        self.print_styled(
            ("class:peer", f"[{sender_name}] "),
            ("", message["content"])
        )

        self.last_message_time[sender_id] = timestamp

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

        # Lưu tin nhắn
        self.chat_manager.handle_incoming_message(message)

        # Peer hiện tại
        if self.chat_manager.current_chat_peer == sender_id:
            self.display_incoming_message(message)

        # Peer khác
        else:
            peer = self.peer_manager.get_peer(sender_id)

            username = peer["username"] if peer else sender_id

            print(
                f"\n[*] New message from {username} [{self.chat_manager.unread_counts[sender_id]}]"
            )


    def handle_received_message(self, message):

        self.chat_manager.handle_incoming_message(message)

        self.display_incoming_message(message)
    # ==========================================
    # CHANGE STATUS
    # ==========================================

    def change_status(self, status: str) -> bool:

        try:
            #print("PeerManager ID:", id(self.peer_manager))
            #print("Status before:", self.peer_manager.status)

            #result = self.peer_manager.set_status(status)

            #print("Status after:", self.peer_manager.status)  
            
            if not self.peer_manager.set_status(status):  
               return False
            
            broadcast_presence(self.presence_broadcaster._socket,
                               self.peer_manager.self_peer_id, self.peer_manager.username,
                               self.peer_manager.tcp_port, status)
            
            return True

        except (RuntimeError, ValueError) as e:
            logger.error("Could not change status: %s", e)
            return False

    # ==========================================
    # START CHAT UI
    # ==========================================

    def start_chat(self, peer_in4: str):

        list_peer = self.get_online_peers_list()

        if peer_in4 == "/quit" or peer_in4 == "/leave":
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
            return

        # ==================================
        # SELECT CONVERSATION
        # ==================================

        peer = self.peer_manager.get_peer(peer_id)

        if peer is None:
            print("Peer is no longer available.")
            return

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
                return

            self.chat_manager.add_connection(peer_id, conn)
            self.chat_loop(peer, conn, client)
        finally:
            self.chat_manager.select_chat_peer(None)
            self.chat_manager.remove_connection(peer_id)
            client.close(conn)

    def receive_message_worker(self, client, conn):

        while not self.receive_stop_event.is_set():

            received = client.receive_messages(
                conn,
                callback=self.incoming_message_queue.put
            )

            if received is False:
                break

        
    def process_incoming_messages(self):

        while True:
            try:
                message = self.incoming_message_queue.get_nowait()

            except queue.Empty:
                break

            try:
                message_type = message.get("type")

                if message_type == "chat":
                    self.handle_incoming_message(message)

                elif "file_notification" in message_type:
                    self.file_manager.handle_notification(message)

                else:
                    self.display_error(
                        f"Unknown message type: {message_type}"
                    )
                    
                print(f"[DEBUG] Received presence: {message}")
            finally:
                self.incoming_message_queue.task_done()

    def chat_loop(self, peer, conn, client: ChatClient):

        self.receive_stop_event.clear()

        self.receive_thread = threading.Thread(
            target=self.receive_message_worker,
            args=(client, conn),
            daemon=True
        )

        self.receive_thread.start()

        try:
            with patch_stdout():

                while True:

                    message = self.get_user_input()

                    if message in ("/back", "/exit", "/leave"):

                        self.leave = True
                        print(f"Leaving chat with {peer['username']}...")
                        return

                    if message == "/quit":
                        self.end = True
                        return

                    # Xử lý tin nhắn mới

                    if "/send" in message:
                        self.handle_file_input(message, peer)
                        continue

                    if self.handle_file_receive():
                        continue

                    # Xử lý tin nhắn chat thông thường
                    chat_message = create_chat_message(
                        sender_id=self.peer_manager.self_peer_id,
                        receiver_id=peer["peer_id"],
                        content=message
                    )

                    success = client.send_message(conn, chat_message)

                    if not success:
                        self.display_error("Could not send message.")
                        return

                    self.print_styled(
                        ("class:peer", f"[{self.peer_manager.username}] "),
                        ("", message)
                    )
                    
                    self.chat_manager.add_message(
                        peer["peer_id"],
                        chat_message
                    )

        finally:
            self.receive_stop_event.set()

            if self.receive_thread.is_alive():
                self.receive_thread.join(timeout=1)

    # ==========================================================
    # =                FILE TRANSFER IN CHAT                   =
    # ==========================================================

    def handle_file_input(self, message, peer):
        """
        Xử lý lệnh gửi file hoặc tên file trong tin nhắn.
        """
        if "/file" in message.strip().lower():

            files = self.display_available_files()
            choice = self.get_user_input()

            for item in files:
            
                file = item["filename"]
                index = item["index"]

                if (
                    file.lower() == choice.lower()
                    or str(index) == choice
                ):
                    file_path =  self.find_file(file)
                    break

            self.confirm_file_transfer(file_path, peer)

            return

        elif "/send" in message:

            filename = self.is_filename_in_message(message)

            if filename is not None:

                file_path = self.find_file(filename)

                if not file_path:
                    self.display_error("File không tồn tại.")
                    return

                self.confirm_file_transfer(file_path, peer)

                return
            else:
                self.display_error("file không tồn tại")

    def handle_file_receive(self) -> bool:
        """
        Kiểm tra và xử lý các yêu cầu nhận file đang chờ.
        """

        if not self.file_manager:
            return False

        if not self.file_manager.file_request_queue.empty():
            self.process_notifications()
            return True

        return False
        

    ## ===============================================
    #               Kiểm tra đầu vào 
    # ================================================

    def is_filename_in_message(self, user_input) -> str | None:
        """Kiểm tra user_input có chứa tên file hợp lệ không."""
        if not user_input:
            return False

        available_files = self.get_available_files()
        filename = None
        for file in available_files:
            if file.lower() in user_input.lower():
                filename = file

        return filename


    def get_available_files(self) -> list:
        """Lấy danh sách file trong thư mục docs."""
        
        if not os.path.isdir(self.file_dir):
            return []

        return [
            filename
            for filename in os.listdir(self.file_dir)
            if os.path.isfile(os.path.join(self.file_dir, filename))
        ]


    def display_available_files(self):
        """Hiển thị danh sách file có thể gửi."""
        files = self.get_available_files()

        if not files:
            print("[File] Không có file nào trong thư mục docs.")
            return

        id_files = []
        print("\n========== AVAILABLE FILES ==========")

        for index, filename in enumerate(files, start=1):
            id_files.append({"index" : index,
                             "filename": filename})
            print(f"{index}. {filename}")

        print("=====================================")

        return id_files


    def find_file(self, filename) -> str | None:
        """Tìm file trong thư mục docs và trả về đường dẫn đầy đủ."""

        if not filename:
            return None

        base_dir = os.path.abspath(self.file_dir)

        file_path = os.path.abspath(
            os.path.join(base_dir, filename)
        )

        # Không cho phép truy cập ra ngoài thư mục docs.
        try:
            if os.path.commonpath(
                [base_dir, file_path]
            ) != base_dir:
                return None
        except ValueError:
            return None

        if not os.path.isfile(file_path):
            return None

        return file_path

    ##=============================================== 
    #           Xử lý thông báo nhận 
    # ===============================================

    def process_notifications(
        self,
        time_out= FILE_REQUEST_TIMEOUT
    ) -> None:
        """
        Xử lý các yêu cầu nhận file đang chờ từ FileManager
        trên UI thread.
        """

        if not self.file_manager:
            return

        while True:
            try:
                request = self.file_manager.file_request_queue.get_nowait()

            except queue.Empty:
                break

            transfer_id = request.get("transfer_id")
            sender_id = request.get("sender_id")
            name = self.peer_manager.get_peer(sender_id)
            filename = request.get("file_name")

            self.print_styled("\n========== FILE REQUEST ==========")
            print(f"From: {name}")
            print(f"File: {filename}")
            print("[Y] Accept    [N] Reject")

            choice = self.get_user_input().strip().lower()

            if choice in ("y", "yes"):
                self.file_manager.accept_file(transfer_id)

                self.display_success(
                    f"Đã chấp nhận file: {filename}"
                )

            else:
                self.file_manager.reject_file(transfer_id)

                print(f"Đã từ chối nhận file: {filename}")

            self.file_manager.file_request_queue.task_done()


    ##  ====== display transfer file ======
    def display_transfer_progress(self):
        """Hiển thị tiến độ các phiên truyền file đang hoạt động."""

        if not self.file_manager:
            return

        with self.file_manager.lock:
            transfers = list(self.file_manager.transfers)

        for transfer in transfers:

            if transfer.get("status") != "transferring":
                continue

            filename = transfer.get("file_name", "Unknown")
            peer_id = transfer.get("peer_id", "Unknown")
            progress = transfer.get("progress")

            file_size = transfer.get("file_size")
            transferred = float(file_size)*float(progress) / 100

            print(
                f"\n[File Transfer] {filename} | "
                f"Peer: {peer_id} | "
                f"{progress:.1f}% "
                f"({transferred}/{file_size} bytes)"
            )

    ## ====== Gửi file =======
    def file_transfer(self, file_path, peer) -> bool:
        """
        Gửi yêu cầu FileManager truyền file đến peer đang được chọn.
        """

        if not file_path or not os.path.isfile(file_path):
            self.display_error("File không tồn tại.")
            return False

        if not peer:
            self.display_error("Chưa chọn peer.")
            return False

        peer_id = (
            peer.get("peer_id")
            if isinstance(peer, dict)
            else peer.peer_id
        )

        try:
            # Tạo file request và đăng ký transfer.
            request = self.file_manager.create_file_request(
                peer_id,
                file_path
            )

            if not request:
                self.display_error("Không thể tạo yêu cầu gửi file.")
                return False

            # Gửi notification qua Chat TCP.
            result = self.chat_manager.send_file_request(
                peer_id,
                request
            )

            if result is False:
                self.display_error("Không thể gửi yêu cầu truyền file.")
                return False

            self.display_success(
                f"Đã gửi yêu cầu truyền file: "
                f"{os.path.basename(file_path)}"
            )

            return True

        except Exception as e:
            self.display_error(f"Lỗi gửi file: {e}")
            return False

    def confirm_file_transfer(self, file_path, peer):
        """Xác nhận trước khi gửi yêu cầu truyền file."""

        filename = os.path.basename(file_path)

        print(f"\nBạn có muốn gửi file '{filename}' không?")
        print("[Y] Yes    [N] No")

        choice = self.get_user_input().strip().lower()

        if choice in ("y", "yes"):
            self.file_transfer(file_path, peer)
        else:
            self.display_error("Đã hủy gửi file.")

    #Khởi động

    def start(self):

        self.end = False

        while True:

            self.leave = False
            choice = input()

            # 1. View online peers
            if choice == "/list":
                self.display_online_peers()

            # 2. help command
            elif choice == "/help":
                print("""
                    /list : Show online users with number, name, IP and status
                    /chat <name|number> : Open a chat with the selected user (TCP connection) 
                    <any text> : Send a message to the current chat partner 
                    /send <file> : Send a file to the current chat partner 
                    /leave : Close the current chat 
                    /status <online|away>: Change your status (sent via UDP) 
                    /help : Show all commands
                    /quit : Exit the program 
                    """)

            # 3. Change status
            elif match := re.match(r"^/status\s+(online|away)$", choice):

                [command, args] = choice.split(" ")
                
                if self.change_status(args):
                    self.display_success(f"Status changed to {args}")
                else:
                    self.display_error("Could not change status")

            # 4. Chat with a peer
            elif match := re.match(r"^/chat\s+(.+)$", choice):
                [command, args] = choice.split(" ")
                list_peer = self.get_online_peers_list()

                while True:     
                    username = self.get_username(args, list_peer)
                    if args == "/quit" or args == '/leave':
                        self.end = True
                        break
                   
                    if username is None:
                        print("Peer is not online")

                    else: 
                        self.start_chat(args)
                    
                    if self.end == True or self.leave == True:
                        break

                    args = input()

            # 5. Exit
            elif choice == "/quit":
                print("Exiting P2P Chat App...")
                
                return

            else:
                print("Invalid option. Please try again.")
                
            if (self.end == True):
                print("Exiting P2P Chat App...")         
                return

