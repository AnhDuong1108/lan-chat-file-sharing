import threading

import socket
import threading
import logging
from file_manager import FileManager
from config import FILE_BUFFER_SIZE

logger = logging.getLogger(__name__)


import socket
import threading
import logging

from config import FILE_HOST, FILE_PORT, BACKLOG

logger = logging.getLogger(__name__)


class FileServer:

    def __init__(self, host=FILE_HOST, port=FILE_PORT):
        self.host = host
        self.port = port

        self.server_socket = None
        self.running = False

        # Quản lý các kết nối client
        self.clients = {}
        self.client_threads = []

        self.file_manager = None

        # Đồng bộ dữ liệu giữa các thread
        self.lock = threading.Lock()

        # Thread chạy server
        self.server_thread = None

    def create_server_socket(self):
        """
        Tạo TCP socket cho FileServer.
        """

        try:
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
            server_socket.listen(BACKLOG)

            logger.info(
                "FileServer listening on %s:%s",
                self.host,
                self.port
            )

            return server_socket

        except OSError:
            logger.exception("Failed to create FileServer socket")

            if "server_socket" in locals():
                server_socket.close()

            return None

    def handle_client(self, conn, addr):
        """
        Tiếp nhận kết nối TCP và chuyển socket cho FileManager.
        """

        client_id = f"{addr[0]}:{addr[1]}"

        try:
            logger.info("New file connection from %s", client_id)

            with self.lock:
                self.clients[client_id] = conn

            if self.file_manager is None:
                logger.error("FileManager has not been initialized")
                return

            # Chuyển socket cho FileManager xử lý
            self.file_manager.handle_incoming_connection(
                conn,
                addr
            )

        except Exception:
            logger.exception(
                "Error handling file connection from %s",
                client_id
            )

        finally:
            with self.lock:
                self.clients.pop(client_id, None)

            try:
                conn.close()
            except OSError:
                pass

            logger.info("File connection closed: %s", client_id)

    def start_file_server(self):
        """
        Khởi chạy FileServer trong thread riêng.
        """

        if self.running:
            logger.warning("FileServer is already running")
            return False

        self.server_socket = self.create_server_socket()

        if self.server_socket is None:
            return False

        self.running = True

        logger.info("FileServer started")

        try:
            while self.running:

                try:
                    conn, addr = self.server_socket.accept()

                except OSError:
                    if self.running:
                        logger.exception("FileServer accept failed")
                    break

                if not self.running:
                    conn.close()
                    break

                thread = threading.Thread(
                    target=self.handle_client,
                    args=(conn, addr),
                    daemon=True
                )

                with self.lock:
                    self.client_threads.append(thread)

                thread.start()

        finally:
            self.running = False

            if self.server_socket:
                try:
                    self.server_socket.close()
                except OSError:
                    pass

                self.server_socket = None

            logger.info("FileServer stopped")

        return True

    def stop_file_server(self):
        """
        Dừng FileServer và đóng các kết nối đang hoạt động.
        """

        if not self.running:
            return

        logger.info("Stopping FileServer")

        self.running = False

        # Đóng listening socket để thoát accept()
        if self.server_socket:
            try:
                self.server_socket.close()
            except OSError:
                pass

        # Đóng các kết nối client
        with self.lock:
            clients = list(self.clients.values())

        for conn in clients:
            try:
                conn.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

            try:
                conn.close()
            except OSError:
                pass

        # Chờ các worker thread kết thúc
        current_thread = threading.current_thread()

        with self.lock:
            threads = list(self.client_threads)

        for thread in threads:
            if thread is not current_thread and thread.is_alive():
                thread.join(timeout=2)

        logger.info("FileServer shutdown completed")

    def set_file_manager(self, file_manager):
        """
        Inject FileManager dependency.
        """

        self.file_manager = file_manager