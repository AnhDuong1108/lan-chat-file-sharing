import logging
import socket
import threading

from common.message import decode_message
from config import UDP_PORT
from peer_discovery.presense_message import validate_presence_message

logger = logging.getLogger(__name__)


def create_listener_socket():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", UDP_PORT))
        sock.settimeout(0.2)
        return sock
    except BaseException:
        sock.close()
        raise


def process_received_message(data, source_ip, peer_manager):
    try:
        message = decode_message(data)
        if not validate_presence_message(message):
            return False
    except (TypeError, ValueError, RecursionError):
        # Includes malformed JSON, invalid UTF-8 and excessively nested JSON.
        return False
    peer_manager.update_peer(message, source_ip)
    return True


class PresenceListener:

    def __init__(self, peer_manager):
        self._peer_manager = peer_manager
        self._stopping = threading.Event()
        self._socket = create_listener_socket()
        self._thread = threading.Thread(
            target=self._run, name="presence-listener", daemon=True
        )

    @property
    def is_running(self):
        return self._thread.is_alive()

    def stop(self):
        self._stopping.set()
        if threading.current_thread() is not self._thread:
            self._thread.join()

    def _run(self):
        try:
            while not self._stopping.is_set():
                try:
                    data, address = self._socket.recvfrom(65535)
                except socket.timeout:
                    continue
                except OSError:
                    if not self._stopping.is_set():
                        logger.warning("UDP listener socket failed", exc_info=True)
                    break
                if self._stopping.is_set():
                    break
                try:
                    process_received_message(data, address[0], self._peer_manager)
                except Exception:
                    logger.exception("Could not update peer from %s", address[0])
        finally:
            self._socket.close()


def start_listener(peer_manager):
    listener = PresenceListener(peer_manager)
    try:
        listener._thread.start()
    except BaseException:
        listener._socket.close()
        raise
    return listener
