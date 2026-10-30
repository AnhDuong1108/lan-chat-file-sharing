import socket
import threading
from common.message import *
from src.config import CHAT_PORT

def handle_client(conn, addr):
    print(f"Connected by {addr}")

    buffer = b""

    try:
        while True:
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
                    print(f"Invalid message from {addr}: {exc}")

    except (ConnectionResetError, OSError) as exc:
        print(f"Connection lost: {addr} - {exc}")

    finally:
        conn.close()
        print(f"Disconnected: {addr}")

def create_server_socket():
    server_socket = socket.socket(
        #Sử dụng địa chỉ IPv4
        socket.AF_INET,
        #Sử dụng giao thức TCP
        socket.SOCK_STREAM
    )

    server_socket.setsockopt(
        socket.SOL_SOCKET,
        # SO_REUSEADDR hỗ trợ bind lại địa chỉ khi server ngắt kết nối
        socket.SO_REUSEADDR,
        1
    )

    server_socket.bind(("0.0.0.0", CHAT_PORT))

    server_socket.listen()

    return server_socket


def start_chat_server():
    server_socket = create_server_socket()

    print("TCP Chat Server is running...")

    try:
        while True:
            conn, addr = server_socket.accept()

            print(f"Connected by {addr}")

            client_thread = threading.Thread(
                target = handle_client,
                args=(conn, addr),
                daemon=True
            )

            client_thread.start()

    except OSError as e:
        print(f"Server error: {e}")

    finally:
        server_socket.close()
        print("TCP Server closed.")
