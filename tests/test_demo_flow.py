"""
Kiểm tra kịch bản Demo hoàn chỉnh giữa 2 Peer A (Alice) và Peer B (Bob):
1. Khởi tạo Discovery, ChatServer, FileServer, FileManager, ChatManager cho cả 2 Peer.
2. Peer A gửi tin nhắn Chat qua TCP tới Peer B.
3. Peer A gửi yêu cầu truyền file 'docs/demo.txt' tới Peer B.
4. Peer B chấp nhận nhận file (Accept).
5. FileSender của Peer A mở kết nối TCP tới FileServer của Peer B và truyền file.
6. FileReceiver của Peer B nhận file, kiểm tra SHA-256, và lưu vào downloads/.
7. Xác nhận nội dung và mã hash của file nhận được tại Peer B hoàn toàn trùng khớp với file gốc!
"""

import hashlib
import os
import shutil
import socket
import sys
import tempfile
import threading
import time

SRC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from chat.chat_client import ChatClient
from chat.chat_manager import ChatManager
from chat.chat_message import create_chat_message
from chat.chat_server import ChatServer
from file_transfer.file_manager import FileManager
from file_transfer.file_server import FileServer
from file_transfer.file_utils import calculate_file_hash
from peer_discovery.peer_manager import PeerManager


def test_full_demo_flow():
    print("\n" + "=" * 70)
    print(" BẮT ĐẦU KIỂM THỬ KỊCH BẢN DEMO THỰC TẾ (PEER A -> PEER B)")
    print("=" * 70)

    # Thư mục tạm cho kịch bản
    from config import DOWNLOAD_DIR
    temp_dir = tempfile.mkdtemp(prefix="demo_test_")
    src_file = os.path.join(temp_dir, f"demo_send_{int(time.time())}.txt")
    downloaded_file = os.path.join(DOWNLOAD_DIR, os.path.basename(src_file))
    if os.path.exists(downloaded_file):
        os.remove(downloaded_file)
    test_data = b"Hello from Peer A! LAN P2P File Sharing and Chat Demonstration." * 100
    with open(src_file, "wb") as f:
        f.write(test_data)
    original_hash = hashlib.sha256(test_data).hexdigest()

    # Cấu hình cổng cho 2 Peer (chạy cùng localhost)
    port_chat_a, port_file_a = 59101, 59102
    port_chat_b, port_file_b = 59103, 59104

    # 1. Khởi tạo Peer A
    pm_a = PeerManager("peer_A", username="Alice", tcp_port=port_chat_a)
    cm_a = ChatManager("peer_A", pm_a)
    fm_a = FileManager(pm_a, cm_a, file_port=port_file_a)
    cm_a.set_file_manager(fm_a)

    cs_a = ChatServer(port=port_chat_a, on_message=cm_a.handle_incoming_message)
    cs_a_worker = cs_a.start(background=True)

    fs_a = FileServer(port=port_file_a)
    fs_a.set_file_manager(fm_a)
    fs_a_worker = threading.Thread(target=fs_a.start_file_server, daemon=True)
    fs_a_worker.start()

    # 2. Khởi tạo Peer B
    pm_b = PeerManager("peer_B", username="Bob", tcp_port=port_chat_b)
    cm_b = ChatManager("peer_B", pm_b)
    fm_b = FileManager(pm_b, cm_b, file_port=port_file_b)
    cm_b.set_file_manager(fm_b)

    cs_b = ChatServer(port=port_chat_b, on_message=cm_b.handle_incoming_message)
    cs_b_worker = cs_b.start(background=True)

    fs_b = FileServer(port=port_file_b)
    fs_b.set_file_manager(fm_b)
    fs_b_worker = threading.Thread(target=fs_b.start_file_server, daemon=True)
    fs_b_worker.start()

    # Cập nhật thông tin nhận biết nhau (thay cho broadcast)
    pm_a.update_peer({"peer_id": "peer_B", "username": "Bob", "tcp_port": port_chat_b, "file_port": port_file_b, "status": "online"}, "127.0.0.1")
    pm_b.update_peer({"peer_id": "peer_A", "username": "Alice", "tcp_port": port_chat_a, "file_port": port_file_a, "status": "online"}, "127.0.0.1")

    time.sleep(0.5)

    try:
        # BƯỚC 1: Chat thử nghiệm
        print("\n[*] BƯỚC 1: Peer A gửi tin nhắn TCP tới Peer B...")
        client_a = ChatClient("peer_B", "127.0.0.1", port_chat_b)
        conn_a = client_a.connect()
        cm_a.add_connection("peer_B", conn_a)

        chat_msg = create_chat_message("peer_A", "peer_B", "Chào Bob, mình chuẩn bị gửi file nhé!")
        client_a.send_message(conn_a, chat_msg)

        time.sleep(0.5)
        b_msgs = cm_b.get_messages("peer_A")
        assert len(b_msgs) >= 1, "Peer B không nhận được tin nhắn chat!"
        print(f"[+] Thành công! Peer B đã nhận tin nhắn: '{b_msgs[0]['content']}'")

        # BƯỚC 2: Gửi file
        print("\n[*] BƯỚC 2: Peer A gửi yêu cầu truyền file tới Peer B...")
        transfer_id = fm_a.send_file("peer_B", src_file)
        assert transfer_id is not None, "Không tạo được transfer_id!"
        print(f"[+] Đã tạo transfer_id: {transfer_id}")

        time.sleep(0.5)
        assert not fm_b.file_request_queue.empty(), "Hàng đợi nhận file của Peer B trống!"
        req_b = fm_b.file_request_queue.get_nowait()
        assert req_b["transfer_id"] == transfer_id
        print(f"[+] Thành công! Peer B nhận được yêu cầu truyền file '{req_b['filename']}' ({req_b['filesize']} bytes).")

        # BƯỚC 3: Peer B chấp nhận (Accept)
        print("\n[*] BƯỚC 3: Peer B chấp nhận nhận file (Accept)...")
        # Kết nối Chat TCP từ B tới A để gửi phản hồi
        client_b = ChatClient("peer_A", "127.0.0.1", port_chat_a)
        conn_b = client_b.connect()
        cm_b.add_connection("peer_A", conn_b)

        accept_ok = fm_b.accept_file(transfer_id)
        assert accept_ok, "Peer B chấp nhận file thất bại!"

        # Chờ quá trình FileSender -> FileReceiver hoàn tất qua File TCP
        print("\n[*] BƯỚC 4: Đang truyền dữ liệu file qua File TCP...")
        timeout = 10
        start = time.time()
        while time.time() - start < timeout:
            status_a = fm_a.get_transfer_status(transfer_id)
            status_b = fm_b.get_transfer_status(transfer_id)
            if status_a == "completed" and status_b == "completed":
                break
            time.sleep(0.3)

        status_a = fm_a.get_transfer_status(transfer_id)
        status_b = fm_b.get_transfer_status(transfer_id)
        print(f"    Trạng thái Peer A: {status_a}")
        print(f"    Trạng thái Peer B: {status_b}")
        assert status_a == "completed", f"Peer A chưa hoàn thành (status={status_a})"
        assert status_b == "completed", f"Peer B chưa hoàn thành (status={status_b})"

        # Kiểm tra file đã lưu tại downloads/
        from config import DOWNLOAD_DIR
        downloaded_file = os.path.join(DOWNLOAD_DIR, os.path.basename(src_file))
        assert os.path.isfile(downloaded_file), f"File không tồn tại ở {downloaded_file}!"

        received_hash = calculate_file_hash(downloaded_file)
        assert received_hash == original_hash, "Hash file nhận không khớp với file gốc!"
        print(f"[+] Tuyệt vời! File đã được lưu tại '{downloaded_file}' với mã SHA-256 chính xác 100%!")

        print("\n" + "=" * 70)
        print(" TOÀN BỘ KỊCH BẢN DEMO ĐÃ THÀNH CÔNG 100%! HỆ THỐNG SẴN SÀNG DEMO!")
        print("=" * 70)

    finally:
        cs_a.stop()
        cs_b.stop()
        fs_a.stop_file_server()
        fs_b.stop_file_server()
        shutil.rmtree(temp_dir, ignore_errors=True)
        if os.path.exists(downloaded_file):
            try:
                os.remove(downloaded_file)
            except OSError:
                pass


if __name__ == "__main__":
    test_full_demo_flow()
