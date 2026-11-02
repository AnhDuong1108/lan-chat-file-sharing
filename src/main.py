import argparse
import datetime
import logging
import os
import signal
import socket
import sys
import time
import uuid
from typing import List, Optional, Tuple

# Cấu hình UTF-8 cho Windows console nếu cần
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Đảm bảo thư mục src nằm trong sys.path để các module import dễ dàng
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from config import BROADCAST_INTERVAL, CHAT_PORT, DISCOVERY_PORT
from peer_discovery.broadcast import PresenceBroadcaster, start_broadcast
from peer_discovery.listen import PresenceListener, start_listener
from peer_discovery.peer_manager import PeerManager

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("main")


def generate_default_peer_id() -> str:
    """Tạo peer_id mặc định theo tên máy tính và một mã ngẫu nhiên ngắn."""
    hostname = socket.gethostname() or "node"
    short_uid = uuid.uuid4().hex[:4]
    return f"pc-{hostname}-{short_uid}"


def get_default_username() -> str:
    """Lấy username mặc định từ môi trường hoặc hệ điều hành."""
    return os.getenv("USERNAME") or os.getenv("USER") or "User"


def init_discovery(
    peer_id: str, username: str, tcp_port: int
) -> Tuple[PeerManager, PresenceBroadcaster, PresenceListener]:
    """
    Khởi tạo và phối hợp các thành phần phát hiện máy trong mạng LAN:
    1. Khởi tạo PeerManager để lưu danh sách các peer.
    2. Khởi chạy PresenceListener để lắng nghe UDP presence và chuyển vào PeerManager.
    3. Khởi chạy PresenceBroadcaster để định kỳ gửi presence ra mạng LAN.

    :param peer_id: ID duy nhất của máy hiện tại.
    :param username: Tên hiển thị của máy hiện tại.
    :param tcp_port: Cổng TCP dành cho chat/truyền file.
    :return: (peer_manager, broadcaster, listener)
    """
    logger.info("Initializing PeerManager (peer_id: %s)...", peer_id)
    peer_manager = PeerManager(peer_id)

    logger.info("Starting UDP PresenceListener on port %d...", DISCOVERY_PORT)
    listener = start_listener(peer_manager)

    logger.info(
        "Starting UDP PresenceBroadcaster (username: %s, tcp_port: %d)...",
        username,
        tcp_port,
    )
    broadcaster = start_broadcast(peer_id, username, tcp_port)

    return peer_manager, broadcaster, listener


def stop_discovery(
    broadcaster: Optional[PresenceBroadcaster],
    listener: Optional[PresenceListener],
) -> None:
    """Đóng các tài nguyên discovery an toàn khi thoát chương trình."""
    logger.info("Closing discovery resources...")
    if broadcaster is not None:
        try:
            broadcaster.stop()
            logger.info("Broadcaster stopped.")
        except Exception as e:
            logger.warning("Error stopping broadcaster: %s", e)

    if listener is not None:
        try:
            listener.stop()
            logger.info("Listener stopped.")
        except Exception as e:
            logger.warning("Error stopping listener: %s", e)


def display_peer_list(peer_manager: PeerManager) -> None:
    """Hiển thị danh sách các peer trong terminal dưới dạng bảng dễ đọc."""
    peers = peer_manager.get_all_peers()
    now = time.time()

    print("\n" + "=" * 80)
    print(f" DANH SÁCH PEER ĐÃ PHÁT HIỆN TRONG MẠNG LAN ({len(peers)} peers)")
    print("=" * 80)

    if not peers:
        print(" (Chưa tìm thấy peer nào khác trong mạng LAN...)")
        print("=" * 80)
        return

    header = f"{'STT':<4} {'PEER ID':<22} {'USERNAME':<16} {'IP ADDRESS':<16} {'TCP PORT':<10} {'STATUS':<10} {'LAST SEEN'}"
    print(header)
    print("-" * 80)

    for idx, peer in enumerate(peers, start=1):
        peer_id = peer.get("peer_id", "")
        username = peer.get("username", "")
        ip = peer.get("ip", "")
        tcp_port = str(peer.get("tcp_port", ""))
        status = peer.get("status", "unknown")
        last_seen_ts = peer.get("last_seen", 0)

        diff = max(0.0, now - last_seen_ts)
        seen_str = f"{diff:.1f}s trước"

        print(
            f"{idx:<4} {peer_id:<22} {username:<16} {ip:<16} {tcp_port:<10} {status:<10} {seen_str}"
        )
    print("=" * 80)


def main(args: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="LAN Chat & File Sharing - Peer Discovery & Management"
    )
    parser.add_argument(
        "--peer-id",
        type=str,
        default=generate_default_peer_id(),
        help="ID duy nhất của máy tính (mặc định: tự tạo từ hostname)",
    )
    parser.add_argument(
        "--username",
        type=str,
        default=get_default_username(),
        help="Tên hiển thị của người dùng (mặc định: tên tài khoản máy)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=CHAT_PORT,
        help=f"Cổng TCP dùng cho chat (mặc định: {CHAT_PORT})",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=float(BROADCAST_INTERVAL),
        help=f"Khoảng thời gian cập nhật màn hình (giây, mặc định: {BROADCAST_INTERVAL})",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help="Thời gian chạy thử tính bằng giây rồi tự dừng (None: chạy liên tục)",
    )

    parsed_args = parser.parse_args(args)

    peer_id = parsed_args.peer_id
    username = parsed_args.username
    tcp_port = parsed_args.port
    interval = max(0.5, parsed_args.interval)
    duration = parsed_args.duration

    print("=" * 80)
    print("               LAN CHAT & FILE SHARING - PEER DISCOVERY")
    print("=" * 80)
    print(f"[*] Self Peer ID   : {peer_id}")
    print(f"[*] Username       : {username}")
    print(f"[*] TCP Port       : {tcp_port}")
    print(f"[*] UDP Discovery  : Port {DISCOVERY_PORT}")
    print(f"[*] Nhấn Ctrl+C để dừng chương trình an toàn.")
    print("=" * 80)

    peer_manager = None
    broadcaster = None
    listener = None
    running = True

    def signal_handler(sig, frame):
        nonlocal running
        print("\n[!] Đang nhận tín hiệu thoát...")
        running = False

    try:
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    except Exception:
        pass

    try:
        peer_manager, broadcaster, listener = init_discovery(
            peer_id=peer_id, username=username, tcp_port=tcp_port
        )

        start_time = time.time()
        while running:
            display_peer_list(peer_manager)

            # Kiểm tra thời lượng chạy nếu có truyền --duration
            if duration is not None and (time.time() - start_time) >= duration:
                logger.info("Reached duration limit (%.1f s). Exiting...", duration)
                break

            time.sleep(interval)

    except KeyboardInterrupt:
        pass
    except Exception as exc:
        logger.exception("An error occurred during execution: %s", exc)
        return 1
    finally:
        stop_discovery(broadcaster, listener)
        print("\n[+] Đã đóng tất cả tài nguyên discovery an toàn. Tạm biệt!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
