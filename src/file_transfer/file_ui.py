import os
import queue
from typing import Any, Optional


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
        file_manager: Any,
        chat_manager: Any,
        peer_manager: Any,
        chat_ui: Optional[Any] = None,
    ):
        self.file_manager = file_manager
        self.chat_manager = chat_manager
        self.peer_manager = peer_manager
        self.chat_ui = chat_ui
        self.docs_dir = os.path.abspath("docs")
        self.downloads_dir = os.path.abspath("downloads")
        os.makedirs(self.docs_dir, exist_ok=True)
        os.makedirs(self.downloads_dir, exist_ok=True)

    def display_menu(self) -> str:
        print("\n================= FILE MANAGER =================")
        print("1. Xem và xử lý yêu cầu nhận file đang chờ")
        print("2. Gửi file tới một máy trong mạng LAN")
        print("3. Xem danh sách và tiến độ các phiên truyền file")
        print("4. Hủy một phiên truyền file đang hoạt động")
        print("5. Xem danh sách file có sẵn trong thư mục docs/")
        print("6. Quay lại menu chính")
        print("================================================")
        return input("Chọn chức năng (1-6): ").strip()

    def process_pending_requests(self) -> None:
        print("\n--- CÁC YÊU CẦU NHẬN FILE ĐANG CHỜ ---")
        if self.file_manager.file_request_queue.empty():
            print("Không có yêu cầu nhận file nào đang chờ.")
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

            print(f"\n[*] Yêu cầu gửi file từ: {sender_name} (Peer ID: {sender_id})")
            print(f"    Tên file: {filename} ({filesize} bytes)")
            choice = input("    Bạn có chấp nhận nhận file này không? (Y/N): ").strip().lower()

            if choice in ("y", "yes"):
                self.file_manager.accept_file(transfer_id)
                print(f"[+] Đã chấp nhận file '{filename}'. Dữ liệu sẽ được lưu vào '{self.downloads_dir}'.")
            else:
                self.file_manager.reject_file(transfer_id)
                print(f"[-] Đã từ chối nhận file '{filename}'.")

            self.file_manager.file_request_queue.task_done()

    def send_file_to_peer(self) -> None:
        print("\n--- GỬI FILE TỚI PEER ---")
        peers = (
            self.peer_manager.get_online_peers()
            if self.peer_manager
            else []
        )
        if not peers:
            print("Không có máy (peer) nào đang online trong mạng LAN.")
            return

        print("Danh sách máy online:")
        for idx, p in enumerate(peers, start=1):
            print(f"{idx}. {p['username']} (ID: {p['peer_id']}, IP: {p['ip']})")

        choice = input("Chọn số thứ tự peer hoặc Peer ID (Enter để quay lại): ").strip()
        if not choice:
            return

        target_peer = None
        for idx, p in enumerate(peers, start=1):
            if (
                choice == str(idx)
                or choice.lower() == p["peer_id"].lower()
                or choice.lower() == p["username"].lower()
            ):
                target_peer = p
                break

        if not target_peer:
            print("[!] Không tìm thấy peer đã chọn.")
            return

        file_input = input("Nhập tên file trong docs/ hoặc đường dẫn file: ").strip().strip('"').strip("'")
        if not file_input:
            return

        file_path = file_input
        if not os.path.isfile(file_path):
            in_docs = os.path.join(self.docs_dir, file_input)
            if os.path.isfile(in_docs):
                file_path = in_docs
            else:
                print(f"[!] File '{file_input}' không tồn tại.")
                return

        try:
            tid = self.file_manager.send_file(target_peer["peer_id"], file_path)
            print(f"[+] Đã gửi yêu cầu truyền file '{os.path.basename(file_path)}' (ID: {tid}) tới {target_peer['username']}.")
            print("    Đang chờ đối phương chấp nhận nhận file...")
        except Exception as e:
            print(f"[!] Lỗi khi gửi file: {e}")

    def show_transfer_status(self) -> None:
        print("\n--- TIẾN ĐỘ & TRẠNG THÁI TRUYỀN FILE ---")
        with self.file_manager.lock:
            active = list(self.file_manager.active_transfers)
            completed = list(self.file_manager.completed_transfers)

        if not active and not completed:
            print("Chưa có phiên truyền file nào.")
            return

        if active:
            print("\n[Đang hoạt động / Chờ xác nhận]:")
            for t in active:
                direction = "Gửi đi" if t.get("direction") == "send" else "Nhận về"
                status = t.get("status", "unknown")
                progress = t.get("progress", 0.0)
                print(f" - ID: {t.get('transfer_id')} | File: {t.get('filename')} | Chiều: {direction} | Trạng thái: {status} | Tiến độ: {progress:.1f}%")

        if completed:
            print("\n[Đã kết thúc]:")
            for t in completed:
                direction = "Gửi đi" if t.get("direction") == "send" else "Nhận về"
                status = t.get("status", "unknown")
                progress = t.get("progress", 100.0)
                print(f" - ID: {t.get('transfer_id')} | File: {t.get('filename')} | Chiều: {direction} | Trạng thái: {status} | Tiến độ: {progress:.1f}%")

    def cancel_active_transfer(self) -> None:
        print("\n--- HỦY PHIÊN TRUYỀN FILE ---")
        with self.file_manager.lock:
            active = list(self.file_manager.active_transfers)

        if not active:
            print("Không có phiên truyền file nào đang hoạt động để hủy.")
            return

        for idx, t in enumerate(active, start=1):
            print(f"{idx}. ID: {t.get('transfer_id')} | File: {t.get('filename')} | Trạng thái: {t.get('status')}")

        choice = input("Nhập số thứ tự hoặc Transfer ID cần hủy: ").strip()
        target_id = None
        for idx, t in enumerate(active, start=1):
            if choice == str(idx) or choice == t.get("transfer_id"):
                target_id = t.get("transfer_id")
                break

        if target_id and self.file_manager.cancel_transfer(target_id):
            print(f"[+] Đã hủy thành công phiên truyền {target_id}.")
        else:
            print("[!] Không tìm thấy phiên truyền hợp lệ để hủy.")

    def list_docs_files(self) -> None:
        print(f"\n--- DANH SÁCH FILE TRONG THƯ MỤC docs/ ({self.docs_dir}) ---")
        files = [
            f
            for f in os.listdir(self.docs_dir)
            if os.path.isfile(os.path.join(self.docs_dir, f))
        ]
        if not files:
            print("Thư mục docs/ đang trống. Bạn có thể thêm file vào đây để gửi nhanh.")
            return
        for idx, f in enumerate(files, start=1):
            size = os.path.getsize(os.path.join(self.docs_dir, f))
            print(f"{idx}. {f} ({size} bytes)")

    def start(self) -> None:
        while True:
            choice = self.display_menu()
            if choice == "1":
                self.process_pending_requests()
            elif choice == "2":
                self.send_file_to_peer()
            elif choice == "3":
                self.show_transfer_status()
            elif choice == "4":
                self.cancel_active_transfer()
            elif choice == "5":
                self.list_docs_files()
            elif choice == "6":
                break
            else:
                print("Lựa chọn không hợp lệ. Vui lòng chọn từ 1 đến 6.")
