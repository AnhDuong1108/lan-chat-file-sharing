import logging
import queue
import threading
import uuid
from typing import Any, Dict, List, Optional, Union

from config import DOWNLOAD_DIR, FILE_PORT
from file_transfer.file_message import create_file_request, create_file_response, validate_file_message
from file_transfer.file_receiver import FileReceiver, receive_file_data_start
from file_transfer.file_sender import FileSender
from file_transfer.file_utils import get_file_info, validate_file
from common.message import send_framed_message

logger = logging.getLogger(__name__)


class FileManager:
    """
    Quản lý toàn bộ vòng đời truyền file trong hệ thống P2P:
    - Quản lý các phiên truyền active / completed.
    - Tạo file_request kèm transfer_id duy nhất.
    - Phối hợp với ChatManager để gửi/nhận handshake bắt tay qua Chat TCP.
    - Điều phối FileSender và FileReceiver truyền nhận nhị phân qua File TCP.
    """

    def __init__(self, peer_manager: Any, chat_manager: Optional[Any] = None, file_port: int = FILE_PORT):
        self.peer_manager = peer_manager
        self.chat_manager = chat_manager
        self.file_port = file_port

        #Gọi callback ở UI
        self.on_progress = None

        # Quản lý các phiên truyền file
        self.active_transfers: List[Dict[str, Any]] = []
        self.completed_transfers: List[Dict[str, Any]] = []

        # Lưu thông tin và trạng thái tất cả transfer
        self.transfers: List[Dict[str, Any]] = []

        # Đồng bộ dữ liệu giữa các thread
        self.lock = threading.RLock()

        # Quản lý các worker thread
        self.transfer_threads: List[threading.Thread] = []

        # Hàng đợi yêu cầu nhận file (chỉ chứa request chiều receive để UI lấy ra xử lý)
        self.file_request_queue: queue.Queue = queue.Queue()

    def set_chat_manager(self, chat_manager: Any) -> None:
        """Inject hoặc cập nhật ChatManager dependency."""
        with self.lock:
            self.chat_manager = chat_manager

    # ==========================================
    # TẠO VÀ ĐĂNG KÝ PHIÊN TRUYỀN FILE
    # ==========================================

    def create_file_request(self, peer_id: str, file_path: str) -> dict:
        """
        Nhiệm vụ:
            1. Sinh transfer_id duy nhất.
            2. Lấy metadata file và tạo file_request chuẩn từ file_message.
            3. Đăng ký transfer vào active_transfers với trạng thái pending (chiều send).
            4. Trả về request dict để ChatManager gửi thông báo qua Chat TCP.
        """
        if not validate_file(file_path, mode="source"):
            raise ValueError(f"Invalid source file: {file_path}")

        file_info = get_file_info(file_path)
        transfer_id = f"transfer_{uuid.uuid4().hex[:10]}"

        sender_id = getattr(self.peer_manager, "self_peer_id", "local")
        request = create_file_request(
            transfer_id=transfer_id,
            sender_id=str(sender_id),
            receiver_id=str(peer_id),
            filename=file_info["filename"],
            filesize=file_info["filesize"],
            file_hash=file_info["file_hash"],
        )

        request["file_name"] = file_info["filename"]
        request["file_size"] = file_info["filesize"]

        transfer_data = {
            "transfer_id": transfer_id,
            "peer_id": str(peer_id),
            "sender_id": str(sender_id),
            "receiver_id": str(peer_id),
            "filename": file_info["filename"],
            "file_name": file_info["filename"],
            "filesize": file_info["filesize"],
            "file_size": file_info["filesize"],
            "file_hash": file_info["file_hash"],
            "file_path": str(file_path),
            "direction": "send",
            "status": "pending",
            "progress": 0.0,
            "socket": None,
            "thread": None,
            "cancel_event": threading.Event(),
        }

        with self.lock:
            self.active_transfers.append(transfer_data)
            self.transfers.append(transfer_data)

        return request

    def register_transfer(self, request: dict, direction: str) -> bool:
        """
        Đăng ký một phiên truyền file mới từ request có sẵn.
        Chỉ direction = 'receive' mới được đưa vào file_request_queue.
        """
        if not isinstance(request, dict):
            return False

        transfer_id = request.get("transfer_id")
        filename = request.get("filename")
        filesize = request.get("filesize")
        file_hash = request.get("file_hash") or request.get("filehash", "")

        if not transfer_id or not filename or filesize is None:
            return False

        with self.lock:
            # Không cho phép đăng ký trùng transfer_id
            for t in self.active_transfers:
                if t.get("transfer_id") == transfer_id:
                    return False

            peer_id = (
                request.get("sender_id")
                if direction == "receive"
                else request.get("receiver_id")
            ) or request.get("peer_id", "unknown")

            filename = request.get("filename") or request.get("file_name", "")
            filesize = request.get("filesize") if request.get("filesize") is not None else request.get("file_size", 0)

            transfer_data = {
                "transfer_id": str(transfer_id),
                "peer_id": str(peer_id),
                "sender_id": str(request.get("sender_id", "")),
                "receiver_id": str(request.get("receiver_id", "")),
                "filename": str(filename),
                "file_name": str(filename),
                "filesize": int(filesize),
                "file_size": int(filesize),
                "file_hash": str(file_hash),
                "file_path": request.get("file_path"),
                "direction": direction,
                "status": "pending",
                "progress": 0.0,
                "socket": None,
                "thread": None,
                "cancel_event": threading.Event(),
            }

            self.active_transfers.append(transfer_data)
            self.transfers.append(transfer_data)

            if direction == "receive":
                self.file_request_queue.put(request.copy())

        return True

    # ==========================================
    # GỬI VÀ NHẬN FILE
    # ==========================================

    def send_file(self, peer_id_or_notification: Union[str, dict], file_path: Optional[str] = None) -> Any:
        """
        Điều phối quá trình gửi file từ phía gửi:
        - Hỗ trợ gọi send_file(peer_id, file_path): tạo request và thông báo cho ChatManager gửi.
        - Hỗ trợ gọi send_file(file_notification): đăng ký transfer với direction='send'.
        """
        if isinstance(peer_id_or_notification, str) and file_path is not None:
            peer_id = peer_id_or_notification
            request = self.create_file_request(peer_id, file_path)

            if self.chat_manager is not None:
                self.chat_manager.send_file_request(peer_id, request)

            return request.get("transfer_id")

        elif isinstance(peer_id_or_notification, dict):
            notification = peer_id_or_notification
            success = self.register_transfer(notification, direction="send")
            peer_id = notification.get("receiver_id") or notification.get("peer_id")
            if success and self.chat_manager is not None and peer_id:
                self.chat_manager.send_file_request(peer_id, notification)
            return success

        return False

    def receive_file(self, file_notification: dict) -> bool:
        """
        Đăng ký và khởi tạo một yêu cầu nhận file đến từ Chat TCP:
        - Nhận thông điệp file_request notification từ ChatManager.
        - Đăng ký transfer với direction = 'receive', status = 'pending'.
        - Đưa request vào file_request_queue để UI hiển thị.
        """
        return self.register_transfer(file_notification, direction="receive")

    def handle_notification(self, file_notification: dict) -> None:
        """
        Nhận phản hồi notification handshake từ ChatManager:
        1. Accept -> Nếu là bên gửi (direction='send'), khởi chạy thread FileSender.
        2. Reject/expired -> Hủy hoặc kết thúc transfer.
        """
        if not isinstance(file_notification, dict):
            return

        transfer_id = file_notification.get("transfer_id")
        status = file_notification.get("status")

        if not transfer_id or not status:
            return

        transfer = self.get_transfer(transfer_id)
        if not transfer:
            return

        if status in ("accept", "accepted"):
            with self.lock:
                for t in self.active_transfers:
                    if t.get("transfer_id") == transfer_id:
                        t["status"] = "accepted"
                        if file_notification.get("file_port"):
                            t["file_port"] = file_notification.get("file_port")
                        if t.get("direction") == "send":
                            self._start_sender_worker(t)
                        break

        elif status in ("reject", "rejected", "expired"):
            new_status = "rejected" if "reject" in status else "failed"
            self.update_transfer_status(transfer_id, new_status)

    def _start_sender_worker(self, transfer: dict) -> None:
        """Khởi chạy worker thread gửi file TCP sau khi người nhận đồng ý."""
        def worker():
            transfer_id = transfer["transfer_id"]
            peer_id = transfer.get("receiver_id") or transfer.get("peer_id")
            peer = self.peer_manager.get_peer(peer_id) if self.peer_manager else None
            ip = peer.get("ip") if peer else "127.0.0.1"
            port = int(transfer.get("file_port") or (peer.get("file_port") if peer else None) or self.file_port)

            sender = FileSender(
                peer_id=peer_id,
                ip=ip,
                port=port,
                cancel_event=transfer["cancel_event"],
                on_progress=lambda sent, total, prog: self._on_progress(transfer_id, prog),
            )

            if not sender.connect():
                logger.error("Could not connect to peer file server %s:%s - %s", ip, port, sender.last_error)
                self.update_transfer_status(transfer_id, "failed")
                return

            with self.lock:
                transfer["socket"] = sender.conn
                transfer["status"] = "transferring"

            try:
                if sender.send_file_data_start(transfer):
                    file_path = transfer.get("file_path")
                    if file_path and sender.send_file_data(file_path):
                        self.update_transfer_status(transfer_id, "completed")
                    else:
                        status = "cancelled" if transfer["cancel_event"].is_set() else "failed"
                        logger.error("send_file_data failed: %s", sender.last_error)
                        self.update_transfer_status(transfer_id, status)
                else:
                    logger.error("send_file_data_start failed: %s", sender.last_error)
                    self.update_transfer_status(transfer_id, "failed")
            finally:
                sender.close()

        thread = threading.Thread(
            target=worker,
            name=f"file-sender-{transfer['transfer_id']}",
            daemon=True,
        )
        transfer["thread"] = thread
        with self.lock:
            self.transfer_threads.append(thread)
        thread.start()

    def _on_progress(self, transfer_id: str, progress: float) -> None:
        """Cập nhật phần trăm tiến độ truyền file."""
        transfer = None 
        with self.lock:
            for t in self.active_transfers:
                if t.get("transfer_id") == transfer_id:
                    t["progress"] = progress
                    transfer = t.copy()
                    break   

        if transfer and self.on_progress:
            self.on_progress(transfer)

    # ==========================================
    # PHẢN HỒI ACCEPT / REJECT
    # ==========================================

    def accept_file(self, transfer_id: str) -> bool:
        """
        Người nhận chấp nhận yêu cầu truyền file:
        1. Tìm transfer trong active_transfers.
        2. Chuyển trạng thái sang 'accepted'.
        3. Yêu cầu ChatManager gửi phản hồi 'accept' tới bên gửi.
        """
        with self.lock:
            transfer = None
            for t in self.active_transfers:
                if t.get("transfer_id") == transfer_id:
                    transfer = t
                    break

            if not transfer or transfer.get("status") != "pending":
                return False

            transfer["status"] = "accepted"
            peer_id = transfer.get("sender_id") or transfer.get("peer_id")

        if self.chat_manager is not None and peer_id:
            response = create_file_response(transfer_id=transfer_id, status="accept")
            response["filename"] = transfer.get("filename", "")
            response["file_name"] = transfer.get("filename", "")
            response["filesize"] = transfer.get("filesize", 0)
            response["file_size"] = transfer.get("filesize", 0)
            response["file_port"] = self.file_port
            self.chat_manager.send_file_response(peer_id, response)

        return True

    def reject_file(self, transfer_id: str) -> bool:
        """
        Người nhận từ chối yêu cầu truyền file:
        1. Tìm transfer trong active_transfers.
        2. Chuyển trạng thái sang 'rejected'.
        3. Chuyển phiên sang completed_transfers.
        4. Yêu cầu ChatManager gửi phản hồi 'reject' tới bên gửi.
        """
        with self.lock:
            transfer = None
            for t in self.active_transfers:
                if t.get("transfer_id") == transfer_id:
                    transfer = t
                    break

            if not transfer or transfer.get("status") != "pending":
                return False

            transfer["status"] = "rejected"
            self.active_transfers.remove(transfer)
            self.completed_transfers.append(transfer)
            peer_id = transfer.get("sender_id") or transfer.get("peer_id")

        if self.chat_manager is not None and peer_id:
            response = create_file_response(transfer_id=transfer_id, status="reject")
            response["filename"] = transfer.get("filename", "")
            response["filesize"] = transfer.get("filesize", 0)
            self.chat_manager.send_file_response(peer_id, response)

        return True

    # ==========================================
    # TIẾP NHẬN KẾT NỐI FILE TCP TỪ FILESERVER
    # ==========================================

    def handle_incoming_connection(self, conn: Any, addr: Any) -> None:
        """
        Tiếp nhận kết nối TCP từ FileServer:
        1. Đọc frame file_data_start để trích xuất transfer_id.
        2. Đối chiếu transfer đã đăng ký với direction=='receive' và status in ('accepted', 'transferring').
        3. Nếu hợp lệ: gửi file_data_ready (status='accept') và trao socket cho FileReceiver.
        4. Nếu không hợp lệ: gửi file_data_ready (status='reject') và đóng socket.
        """
        start_msg = receive_file_data_start(conn)
        if start_msg is None:
            try:
                conn.close()
            except OSError:
                pass
            return

        transfer_id = start_msg.get("transfer_id")
        transfer = None

        with self.lock:
            for t in self.active_transfers:
                if t.get("transfer_id") == transfer_id:
                    transfer = t
                    break

        # Kiểm tra tính hợp lệ của transfer
        is_valid = (
            transfer is not None
            and transfer.get("direction") == "receive"
            and transfer.get("status") in ("accepted", "transferring")
        )

        if not is_valid:
            try:
                send_framed_message(
                    conn,
                    {"type": "file_data_ready", "transfer_id": transfer_id or "", "status": "reject"},
                )
            except Exception:
                pass
            try:
                conn.close()
            except OSError:
                pass
            return

        # Bắt tay thành công phía nhận
        if not send_framed_message(
            conn,
            {"type": "file_data_ready", "transfer_id": transfer_id, "status": "accept"},
        ):
            try:
                conn.close()
            except OSError:
                pass
            return

        with self.lock:
            transfer["status"] = "transferring"
            transfer["socket"] = conn

        receiver = FileReceiver(
            download_dir=DOWNLOAD_DIR,
            on_progress=lambda sent, total, prog: self._on_progress(transfer_id, prog),
            cancel_event=transfer["cancel_event"],
        )

        success = receiver.receive_file_data(conn, transfer)
        if success:
            self.update_transfer_status(transfer_id, "completed")
        else:
            final_status = "cancelled" if transfer["cancel_event"].is_set() else "failed"
            self.update_transfer_status(transfer_id, final_status)

    # ==========================================
    # TRẠNG THÁI VÀ QUẢN LÝ VÒNG ĐỜI TRANSFER
    # ==========================================

    def get_transfer_status(self, transfer_id: str) -> Optional[str]:
        """Lấy trạng thái hiện tại của phiên truyền file."""
        with self.lock:
            for t in self.active_transfers:
                if t.get("transfer_id") == transfer_id:
                    return t.get("status")
            for t in self.completed_transfers:
                if t.get("transfer_id") == transfer_id:
                    return t.get("status")
        return None

    def get_transfer(self, transfer_id: str) -> Optional[Dict[str, Any]]:
        """Lấy thông tin chi tiết một phiên truyền file."""
        with self.lock:
            for t in self.active_transfers:
                if t.get("transfer_id") == transfer_id:
                    return t.copy()
            for t in self.completed_transfers:
                if t.get("transfer_id") == transfer_id:
                    return t.copy()
        return None

    def update_transfer_status(self, transfer_id: str, status: str) -> bool:
        """
        Cập nhật trạng thái của phiên truyền file.
        Khi chuyển sang trạng thái kết thúc (completed/failed/cancelled/rejected),
        tự động chuyển từ active_transfers sang completed_transfers.
        """
        with self.lock:
            for idx, t in enumerate(self.active_transfers):
                if t.get("transfer_id") == transfer_id:
                    t["status"] = status
                    if status == "completed":
                        t["progress"] = 100.0
                    if status in ("completed", "failed", "cancelled", "rejected"):
                        self.active_transfers.pop(idx)
                        self.completed_transfers.append(t)
                    return True

            for t in self.completed_transfers:
                if t.get("transfer_id") == transfer_id:
                    t["status"] = status
                    return True

        return False

    def cancel_transfer(self, transfer_id: str) -> bool:
        """Hủy một phiên truyền file đang hoạt động bằng Event và đóng socket an toàn."""
        with self.lock:
            transfer = None
            for idx, t in enumerate(self.active_transfers):
                if t.get("transfer_id") == transfer_id:
                    transfer = t
                    self.active_transfers.pop(idx)
                    break

            if not transfer:
                return False

            transfer["cancel_event"].set()
            transfer["status"] = "cancelled"

            sock = transfer.get("socket")
            if sock:
                try:
                    sock.close()
                except OSError:
                    pass

            self.completed_transfers.append(transfer)
            return True
