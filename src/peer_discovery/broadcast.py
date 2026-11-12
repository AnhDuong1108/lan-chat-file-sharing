import logging
import socket
import threading

from common.message import encode_message
from config import BROADCAST_ADDRESS, BROADCAST_INTERVAL, UDP_PORT
from peer_discovery.presense_message import (
    create_presence_message,
    validate_presence_message,
)

logger = logging.getLogger(__name__)
_broadcasters = {}
_broadcasters_lock = threading.Lock()


def create_broadcast_socket():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(0.5)
        return sock
    except BaseException:
        sock.close()
        raise


def broadcast_presence(sock, peer_id, username, tcp_port, status):
    message = create_presence_message(peer_id, username, tcp_port, status)
    message["status"] = status
    if not validate_presence_message(message):
        raise ValueError("Invalid presence message")
    sock.sendto(encode_message(message), (BROADCAST_ADDRESS, UDP_PORT))


class PresenceBroadcaster:

    def __init__(self, peer_id, username, tcp_port):
        self._status = "online"
        message = create_presence_message(peer_id, username, tcp_port, self._status)
        if not validate_presence_message(message):
            raise ValueError("Invalid peer identity")
        self.peer_id = peer_id
        self.username = username
        self.tcp_port = tcp_port
        self._condition = threading.Condition()
        self._stopping = False
        self._socket = create_broadcast_socket()
        self._thread = threading.Thread(
            target=self._run, name=f"presence-broadcast-{peer_id}", daemon=True
        )

    @property
    def is_running(self):
        return self._thread.is_alive()

    def set_status(self, status):
        if status not in ("online", "away"):
            raise ValueError("Status must be online or away; use stop() to exit")
        with self._condition:
            if self._stopping:
                raise RuntimeError("Broadcaster has stopped")
            if status != self._status:
                self._status = status
                self._condition.notify_all()

    def stop(self):
        with self._condition:
            self._stopping = True
            self._condition.notify_all()
        if threading.current_thread() is not self._thread:
            self._thread.join()

    def _send(self, status):
        try:
            broadcast_presence(
                self._socket, self.peer_id, self.username, self.tcp_port, status
            )
        except OSError:
            logger.warning("Could not broadcast presence", exc_info=True)

    def _run(self):
        try:
            with self._condition:
                while not self._stopping:
                    sent_status = self._status
                    self._send(sent_status)
                    self._condition.wait_for(
                        lambda: self._stopping or self._status != sent_status,
                        timeout=BROADCAST_INTERVAL,
                    )
            self._send("offline")
        finally:
            self._socket.close()
            with _broadcasters_lock:
                if _broadcasters.get(self.peer_id) is self:
                    del _broadcasters[self.peer_id]


def start_broadcast(peer_id, username, tcp_port):
    
    with _broadcasters_lock:
        existing = _broadcasters.get(peer_id)
        if existing is not None:
            if (existing.username, existing.tcp_port) != (username, tcp_port):
                raise ValueError("Peer already broadcasting with another identity")
            return existing
        broadcaster = PresenceBroadcaster(peer_id, username, tcp_port)
        _broadcasters[peer_id] = broadcaster
        try:
            broadcaster._thread.start()
        except BaseException:
            del _broadcasters[peer_id]
            broadcaster._socket.close()
            raise
        return broadcaster
