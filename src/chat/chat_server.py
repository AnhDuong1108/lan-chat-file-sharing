import socket
import threading
from common.message import decode_message
from config import BUFFER_SIZE, CHAT_PORT


class ChatServer:

    def __init__(self, host="0.0.0.0", port=CHAT_PORT, on_message=None):

        self.host = host
        self.port = port
        self.on_message = on_message

        self.server_socket = None

        self.running = False

        self.clients = {}
        self.client_threads = []

        self.lock = threading.Lock()

    # ==========================================
    # CREATE SERVER SOCKET
    # ==========================================

    def create_server_socket(self):

        server_socket = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM
        )

        try:
            reuse_option = getattr(socket, "SO_EXCLUSIVEADDRUSE", socket.SO_REUSEADDR)
            server_socket.setsockopt(socket.SOL_SOCKET, reuse_option, 1)
            server_socket.bind((self.host, self.port))
            server_socket.listen()
            server_socket.settimeout(0.2)
        except OSError:
            server_socket.close()
            raise

        self.server_socket = server_socket

        return server_socket


    # ==========================================
    #  CLIENT MANAGEMENT
    # ==========================================

    def add_client(self, conn, addr):

        with self.lock:
            self.clients[conn] = addr

        print(f"Client added: {addr}")

    def remove_client(self, conn):

        with self.lock:
            self.clients.pop(conn, None)

    def get_client(self, peer_id):

        with self.lock:
            return self.clients.get(peer_id)

    # ==========================================
    # HANDLE CLIENT
    # ==========================================

    def handle_client(self, conn, addr):

        print(f"Connected by {addr}")

        buffer = b""

        try:

            while self.running:

                data = conn.recv(BUFFER_SIZE)

                if not data:
                    break

                buffer += data

                while b"\n" in buffer:

                    raw_message, buffer = buffer.split(b"\n", 1)

                    if not raw_message:
                        continue

                    try:

                        message = decode_message(raw_message)

                    except (ValueError, RecursionError) as exc:

                        print(
                            f"Invalid message from {addr}: {exc}"
                        )
                        continue

                    if self.on_message is None:
                        print("Received:", message)
                    else:
                        self.on_message(message)

        except (ConnectionResetError, OSError) as exc:

            print(f"Connection lost: {addr} - {exc}")

        finally:
            self.remove_client(conn)
            conn.close()
            with self.lock:
                worker = threading.current_thread()
                if worker in self.client_threads:
                    self.client_threads.remove(worker)

            print(f"Disconnected: {addr}")


    # ==========================================
    # START CHAT SERVER
    # ==========================================

    def start(self, background=False):
        with self.lock:
            if self.running:
                raise RuntimeError("Chat server is already running")
            server_socket = self.create_server_socket()
            self.running = True

        print("TCP Chat Server is running...")
        if background:
            worker = threading.Thread(
                target=self._accept_clients, args=(server_socket,), daemon=True
            )
            try:
                worker.start()
            except RuntimeError:
                self.stop()
                raise
            return worker

        self._accept_clients(server_socket)

    def _accept_clients(self, server_socket):
        try:
            while self.server_socket is server_socket and self.running:
                try:
                    conn, addr = server_socket.accept()
                except socket.timeout:
                    continue
                with self.lock:
                    if self.server_socket is not server_socket or not self.running:
                        conn.close()
                        return
                    worker = threading.Thread(
                        target=self.handle_client, args=(conn, addr), daemon=True
                    )
                    self.clients[conn] = addr
                    self.client_threads.append(worker)
                    try:
                        worker.start()
                    except RuntimeError:
                        self.client_threads.remove(worker)
                        raise

        except OSError as e:

            if self.server_socket is server_socket and self.running:
                print(f"Server error: {e}")

        finally:

            with self.lock:
                if self.server_socket is server_socket:
                    self._stop()

    # ==========================================
    # STOP CHAT SERVER
    # ==========================================

    def stop(self):
        with self.lock:
            self._stop()

    def _stop(self):
        self.running = False

        if self.server_socket:
            self.server_socket.close()
            self.server_socket = None

        for conn in self.clients:
            try:
                conn.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            conn.close()

        self.clients.clear()
