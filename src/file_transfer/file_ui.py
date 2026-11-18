import os
import queue
from typing import Any, Optional
from peer_discovery.peer_manager import PeerManager
from chat.chat_manager import ChatManager
from file_transfer.file_manager import FileManager
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit import print_formatted_text

class FileUI:
    """
    Giao diện dòng lệnh tương tác cho tính năng truyền file P2P.
    Hỗ trợ:
    - Xem và xử lý các yêu cầu nhận file đang chờ (Accept / Reject).
    - Gửi file tới một peer đang online trong mạng LAN.
    - Xem danh sách và tiến độ các phiên truyền file (đang truyền / hoàn tất / đã hủy).
    - Hủy một phiên truyền file đang hoạt động.
    - Quản lý các file có sẵn trong thư mục docs/ để gửi.
    """

    def __init__(
        self,
        file_manager: FileManager,
        chat_manager: ChatManager,
        peer_manager: PeerManager,
        chat_ui: Optional[Any] = None,
    ):
        
        self.style = Style.from_dict({
                "prompt": "#00ff87 bold",
                "command": "#00afff bold",
                "success": "#00ff91",
                "error": "#ff5f5f bold",
                "warning": "#ffaf00",
                "system": "#888888",
                "peer": "#5fd7ff bold",
                "timestamp": "#888888 italic",
            })
        
        self.file_manager = file_manager
        if self.file_manager:
            self.file_manager.on_progress = self.display_transfer_progress

        self.chat_manager = chat_manager
        self.peer_manager = peer_manager
        self.chat_ui = chat_ui
        self.docs_dir = os.path.abspath("docs")
        self.downloads_dir = os.path.abspath("downloads")
        os.makedirs(self.docs_dir, exist_ok=True)
        os.makedirs(self.downloads_dir, exist_ok=True)

    def print_styled(self, *fragments):
        """In nội dung có định dạng màu trên terminal."""
        try:
            print_formatted_text(
                FormattedText(fragments),
                style=self.style
            )
        except Exception:
            plain_text = "".join(f[1] if isinstance(f, tuple) and len(f) > 1 else str(f) for f in fragments)
            print(plain_text)

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

    def display_help_menu(self):
        print("\n========================= FILE MANAGER =========================")
        print("/requests        - View and handle pending file reception requests")
        print("/list            - View online peers ")
        print("/send <filename> <receiver1> <receiver2> ... - Send a file to a device on the LAN")
        print("/sessions        - View file transfer sessions and their progress")
        print("/cancel          - Cancel an active file transfer session")
        print("/files           - View available files in the docs/ directory")
        print("/help            - Show all commands")
        print("/quit            - Return to the main menu")
        
        print("==================================================================")

    def process_pending_requests(self) -> None:
        print("\n--- PENDING FILE RECEPTION REQUESTS ---")
        if self.file_manager.file_request_queue.empty():
            print("No pending file reception requests.")
            return

        while not self.file_manager.file_request_queue.empty():
            try:
                req = self.file_manager.file_request_queue.get_nowait()
            except queue.Empty:
                break

            transfer_id = req.get("transfer_id")
            sender_id = req.get("sender_id")
            peer_obj = (
                self.peer_manager.get_peer(sender_id)
                if self.peer_manager
                else None
            )
            sender_name = (
                peer_obj.get("username", sender_id)
                if peer_obj
                else sender_id
            )
            filename = (
                req.get("filename")
                or req.get("file_name", "Unknown")
            )
            filesize = (
                req.get("filesize")
                if req.get("filesize") is not None
                else req.get("file_size", 0)
            )

            self.print_styled(("class:warning", f"\n[*] File transfer request from: {sender_name} (Peer ID: {sender_id})"))
            print(f"    File name: {filename} ({filesize} bytes)")
            choice = input("    Do you want to accept this file? (Y/N): ").strip().lower()

            if choice in ("y", "yes"):
                    self.file_manager.accept_file(transfer_id)
                    self.print_styled(("class:warning", f"[+] Accepted file '{filename}'. The file will be saved to '{self.downloads_dir}'."))
            else:
                    self.file_manager.reject_file(transfer_id)
                    self.print_styled(("class:warning", f"[-] Rejected file '{filename}'."))

                    self.file_manager.file_request_queue.task_done()

    def send_file_to_peer(self, filename: str, receiver: str) -> None:
        print("\n--- SEND FILE TO PEER ---")
        peers = (
            self.peer_manager.get_online_peers()
            if self.peer_manager
            else []
        )

        target_peer = None
        for idx, p in enumerate(peers, start=1):
            if (
                receiver == str(idx)
                or receiver.lower() == p["peer_id"].lower()
                or receiver.lower() == p["username"].lower()
            ):
                target_peer = p
                break

        if not target_peer:
            self.display_error("Selected peer not found.")
            return

        if not filename:
            return

        file_path = filename
        if not os.path.isfile(file_path):
            in_docs = os.path.join(self.docs_dir, filename)
            if os.path.isfile(in_docs):
                file_path = in_docs
            else:
                self.display_error(f"File '{filename}' does not exit.")
                return

        try:
            tid = self.file_manager.send_file(target_peer["peer_id"], file_path)
            self.display_success(
                f"File transfer request for '{os.path.basename(file_path)}' (ID: {tid}) "
                f"sent successfully to {target_peer['username']}."
            )
            print("    Waiting for the recipient to accept the file transfer...")
        except Exception as e:
            self.display_error(f"Error while sending file: {e}")

    def show_transfer_status(self) -> None:
        print("\n--- FILE TRANSFER PROGRESS & STATUS ---")
        with self.file_manager.lock:
            active = list(self.file_manager.active_transfers)
            completed = list(self.file_manager.completed_transfers)

        if not active and not completed:
            print("No file transfer sessions found.")
            return

        if active:
            print("\n[Active / Awaiting Confirmation]:")
            for t in active:
                direction = "Outgoing" if t.get("direction") == "send" else "Incoming"
                status = t.get("status", "unknown")
                progress = t.get("progress", 0.0)
                print(
                    f" - ID: {t.get('transfer_id')} | File: {t.get('filename')} | "
                    f"Direction: {direction} | Status: {status} | Progress: {progress:.1f}%"
                )

        if completed:
            print("\n[Completed]:")
            for t in completed:
                direction = "Outgoing" if t.get("direction") == "send" else "Incoming"
                status = t.get("status", "unknown")
                progress = t.get("progress", 100.0)
                print(f" - ID: {t.get('transfer_id')} | File: {t.get('filename')} | Chiều: {direction} | Trạng thái: {status} | Tiến độ: {progress:.1f}%")

    def cancel_active_transfer(self) -> None:
        print("\n--- CANCEL FILE TRANSFER SESSION ---")
        with self.file_manager.lock:
            active = list(self.file_manager.active_transfers)

        if not active:
            print("No active file transfer sessions available to cancel.")
            return

        for idx, t in enumerate(active, start=1):
            print(
                f"{idx}. ID: {t.get('transfer_id')} | "
                f"File: {t.get('filename')} | Status: {t.get('status')}"
            )

        choice = input("Enter the session number or Transfer ID to cancel: ").strip()
        target_id = None
        for idx, t in enumerate(active, start=1):
            if choice == str(idx) or choice == t.get("transfer_id"):
                target_id = t.get("transfer_id")
                break

        if target_id and self.file_manager.cancel_transfer(target_id):
            self.display_success(f"Đã hủy thành công phiên truyền {target_id}.")
        else:
            self.display_error("Không tìm thấy phiên truyền hợp lệ để hủy.")

    def list_docs_files(self) -> None:
        print(f"\n--- FILES IN docs/ ({self.docs_dir}) ---")
        files = [
            f
            for f in os.listdir(self.docs_dir)
            if os.path.isfile(os.path.join(self.docs_dir, f))
        ]
        if not files:
            print(("The docs/ directory is empty. You can add files here for quick file sharing."))
            return
        for idx, f in enumerate(files, start=1):
            size = os.path.getsize(os.path.join(self.docs_dir, f))
            print(f"{idx}. {f} ({size} bytes)")

    def display_transfer_progress(self, transfer: dict):
        """Hiển thị tiến độ truyền file trên cùng một dòng."""

        if not self.file_manager:
            self.display_error("Not file manager")
            return

        if transfer.get("status") != "transferring":
            return

        filename = transfer.get("file_name", "Unknown")
        peer_id = transfer.get("peer_id", "Unknown")
        progress = float(transfer.get("progress", 0))

        file_size = transfer.get("file_size", 0)
        transferred = int(file_size * progress / 100)

        print(
            f"\r[File Transfer] {filename} | "
            f"Peer: {peer_id} | "
            f"{progress:.1f}% "
            f"({transferred}/{file_size} bytes)",
            end="",
            flush=True
        )

        if progress >= 100:
            print()

    def is_filename_in_message(self, user_input) -> str | None:
        """Kiểm tra user_input có chứa tên file hợp lệ không."""

        if not user_input:
            return None

        parts = str(user_input).strip().split(None, 1)

        if len(parts) > 1 and parts[0].lower() == "/send":
            candidate = parts[1].strip()

            # Xử lý tên file có dấu ngoặc kép
            if candidate.startswith('"'):
                end_quote = candidate.find('"', 1)
                if end_quote != -1:
                    return candidate[1:end_quote]

            if candidate.startswith("'"):
                end_quote = candidate.find("'", 1)
                if end_quote != -1:
                    return candidate[1:end_quote]

            # Chỉ lấy đối số filename, bỏ qua receiver
            filename = candidate.split()[0]
            return filename

        available_files = self.get_available_files()

        for file in available_files:
            if file.lower() in str(user_input).lower():
                return file

        return None


    def get_available_files(self) -> list:
        """Lấy danh sách file trong thư mục docs."""
        
        if not os.path.isdir(self.docs_dir):
            return []

        return [
            filename
            for filename in os.listdir(self.docs_dir)
            if os.path.isfile(os.path.join(self.docs_dir, filename))
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

    def validate_send_command(self, user_input: str) -> tuple[bool, str | None, list[str]]:
        """
        Validate /send command.

        Format:
            /send <filename> <receiver1> [receiver2] ...

        Returns:
            (is_valid, filename, receivers)
        """
        parts = user_input.strip().split()

        if len(parts) < 3:
            return False, None, []

        if parts[0] != "/send":
            return False, None, []

        filename = parts[1]
        receivers = parts[2:]

        return True, filename, receivers

    def start(self) -> None:
        self.display_help_menu()
        while True:
            choice = input()
            if choice == "/requests":
                self.process_pending_requests()

            elif choice == "/list":
                peers = self.peer_manager.get_online_peers()

                if not peers:
                    print("No peers online.")
                    continue

                for idx, peer in enumerate(peers, start = 1):
                     print(f"{idx}. {peer.get('username', 'Unknown')}")

            elif choice.startswith("/send"):
                is_valid, filename, receivers = self.validate_send_command(choice)

                if not is_valid:
                    self.display_error(
                        "Invalid command! Usage: /send <filename> <receiver1> [receiver2] ..."
                    )
                    continue

                for receiver in receivers:
                    self.send_file_to_peer(filename, receiver)

            elif choice == "/sessions":
                self.show_transfer_status()

            elif choice == "/cancel":
                self.cancel_active_transfer()

            elif choice == "/files":
                self.list_docs_files()

            elif choice == "/help":
                self.display_help_menu()

            elif choice == "/quit":
                break

            else:
                print("Invalid option")
