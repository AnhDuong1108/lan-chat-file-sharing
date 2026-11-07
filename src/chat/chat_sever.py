import socket
import threading
from common.message import *
from src.config import CHAT_PORT


class ChatServer:

    def __init__(self, host="0.0.0.0", port=CHAT_PORT):

        self.host = host
        self.port = port

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

        server_socket.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_REUSEADDR,
            1
        )

        server_socket.bind((self.host, self.port))

        server_socket.listen()

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

                data = conn.recv(4096)

                if not data:
                    break

                buffer += data

                while b"\n" in buffer:

                    raw_message, buffer = buffer.split(b"\n", 1)

                    if not raw_message:
                        continue

                    try:

                        message = decode_message(raw_message)

                        print("Received:", message)

                    except (ValueError, UnicodeDecodeError) as exc:

                        print(
                            f"Invalid message from {addr}: {exc}"
                        )

        except (ConnectionResetError, OSError) as exc:

            print(f"Connection lost: {addr} - {exc}")

        finally:
            self.remove_client(conn)
            conn.close()

            print(f"Disconnected: {addr}")


    # ==========================================
    # START CHAT SERVER
    # ==========================================

    def start(self):

        self.create_server_socket()

        self.running = True

        print("TCP Chat Server is running...")

        try:

            while self.running:

                conn, addr = self.server_socket.accept()

                self.add_client(conn, addr)

                client_thread = threading.Thread(
                    target=self.handle_client,
                    args=(conn, addr),
                    daemon=True
                )

                self.client_threads.append(client_thread)

                client_thread.start()

        except OSError as e:

            if self.running:
                print(f"Server error: {e}")

        finally:

            self.stop()

    # ==========================================
    # STOP CHAT SERVER
    # ==========================================

    def stop(self):

        self.running = False
        print("Stopping TCP Chat Server...")

        if self.server_socket:
            self.server_socket.close()
            self.server_socket = None

        with self.lock:

            for conn in list(self.clients.keys()):
                try:
                    conn.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

                conn.close()

            self.clients.clear()
