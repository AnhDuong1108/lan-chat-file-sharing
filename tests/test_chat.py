import socket
import sys
import threading
import time
import unittest
from pathlib import Path
from queue import Queue
from unittest.mock import patch

SRC_DIR = str(Path(__file__).resolve().parents[1] / "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from chat.chat_client import ChatClient
from chat.chat_manager import ChatManager
from chat.chat_message import create_chat_message
from chat.chat_server import ChatServer
from chat.chat_ui import ChatUI
from common.message import encode_message
from config import CONNECT_TIMEOUT
from peer_discovery.peer_manager import PeerManager


LOOPBACK = "127.0.0.1"
WAIT = 3


class TestChat(unittest.TestCase):
    def start_server(self, on_message, port=0):
        server = ChatServer(LOOPBACK, port, on_message=on_message)
        worker = server.start(background=True)

        def stop_server():
            server.stop()
            worker.join(WAIT)
            self.assertFalse(worker.is_alive())

        self.addCleanup(stop_server)
        return server

    def connect(self, server, peer_id="B"):
        port = server.server_socket.getsockname()[1]
        client = ChatClient(peer_id, LOOPBACK, port)
        conn = client.connect()
        self.addCleanup(client.close, conn)
        return client, conn

    def wait_for(self, condition):
        deadline = time.monotonic() + WAIT
        while not condition():
            if time.monotonic() >= deadline:
                self.fail("Timed out waiting for the chat state to change")
            time.sleep(0.01)

    def make_ui(self, peer_id):
        peers = PeerManager(peer_id)
        manager = ChatManager(peer_id, peers)
        return ChatUI(peers, manager)

    def test_tc01_connection_refused(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reserved:
            reserved.bind((LOOPBACK, 0))
            client = ChatClient("B", LOOPBACK, reserved.getsockname()[1])
            with self.assertRaises(ConnectionRefusedError):
                client.connect()
        self.assertFalse(client.is_connected(None))

    def test_tc02_connection_timeout(self):
        client = ChatClient("B", LOOPBACK, 5000)
        # Mô phỏng peer không phản hồi mà không phụ thuộc định tuyến LAN.
        with patch("chat.chat_client.socket.create_connection", side_effect=TimeoutError) as dial:
            with self.assertRaises(TimeoutError):
                client.connect()
        dial.assert_called_once_with((LOOPBACK, 5000), CONNECT_TIMEOUT)

    def test_tc03_port_in_use(self):
        server = self.start_server(None)
        occupied_port = server.server_socket.getsockname()[1]
        duplicate = ChatServer(LOOPBACK, occupied_port)
        with self.assertRaises(OSError):
            duplicate.start(background=True)
        self.assertFalse(duplicate.running)
        self.assertIsNone(duplicate.server_socket)

    def test_tc04_send_one_message(self):
        received = Queue()
        client, conn = self.connect(self.start_server(received.put))
        message = create_chat_message("A", "B", "Chào bạn!\nDòng thứ hai.")
        self.assertTrue(client.is_connected(conn))
        self.assertTrue(client.send_message(conn, message))
        self.assertEqual(received.get(timeout=WAIT), message)
        client.close(conn)
        self.assertFalse(client.is_connected(conn))

    def test_tc05_receive_two_messages_in_order(self):
        received = Queue()
        client, conn = self.connect(self.start_server(received.put))
        messages = [create_chat_message("A", "B", str(i)) for i in range(2)]
        for message in messages:
            self.assertTrue(client.send_message(conn, message))
        self.assertEqual([received.get(timeout=WAIT) for _ in messages], messages)

        # Hai dòng có thể nằm chung một lần recv, hoặc một dòng bị chia nhỏ.
        sender, receiver = socket.socketpair()
        with sender, receiver:
            receiver.settimeout(WAIT)
            wire = b"".join(encode_message(message) + b"\n" for message in messages)
            sender.sendall(wire[:8])
            sender.sendall(wire[8:])
            sender.shutdown(socket.SHUT_WR)
            decoded = []
            self.assertTrue(client.receive_messages(receiver, decoded.append))
            self.assertEqual(decoded, messages[:1])
            self.assertTrue(client.receive_messages(receiver, decoded.append))
            self.assertEqual(decoded, messages)
            self.assertFalse(client.receive_messages(receiver, decoded.append))

    def test_tc06_malformed_json_does_not_stop_server(self):
        received = Queue()
        server = self.start_server(received.put)
        client, conn = self.connect(server)
        conn.sendall(b'{"broken":\n\xff\n[]\n')
        valid = create_chat_message("A", "B", "Still connected")
        self.assertTrue(client.send_message(conn, valid))
        self.assertEqual(received.get(timeout=WAIT), valid)
        self.assertTrue(server.running)

    def test_tc07_disconnected_client_is_removed(self):
        server = self.start_server(None)
        _, conn = self.connect(server)

        def client_count():
            with server.lock:
                return len(server.clients)

        self.wait_for(lambda: client_count() == 1)
        conn.close()
        self.wait_for(lambda: client_count() == 0)

    def test_tc08_only_addressed_peer_keeps_message(self):
        ui_b = self.make_ui("B")
        ui_c = self.make_ui("C")
        server_b = self.start_server(ui_b.handle_incoming_message)
        checked = threading.Event()

        def receive_at_c(message):
            ui_c.handle_incoming_message(message)
            checked.set()

        server_c = self.start_server(receive_at_c)
        client_b, conn_b = self.connect(server_b)
        client_c, conn_c = self.connect(server_c, "C")
        message = create_chat_message("A", "B", "For B")
        self.assertTrue(client_b.send_message(conn_b, message))
        self.wait_for(lambda: ui_b.chat_manager.get_messages("A") == [message])
        self.assertEqual(ui_c.chat_manager.conversations, {})

        self.assertTrue(client_c.send_message(conn_c, message))
        self.assertTrue(checked.wait(WAIT))
        self.assertEqual(ui_c.chat_manager.conversations, {})
        self.assertEqual(ui_c.chat_manager.get_unread_count("A"), 0)

    def test_tc09_histories_are_separate_and_complete(self):
        manager = ChatManager("A")
        to_b = create_chat_message("A", "B", "First")
        from_b = create_chat_message("B", "A", "Second")
        from_c = create_chat_message("C", "A", "Other peer")

        manager.add_message("B", to_b)
        manager.handle_incoming_message(from_b)
        manager.handle_incoming_message(from_c)

        self.assertEqual(manager.conversations, {"B": [to_b, from_b], "C": [from_c]})

    def test_tc10_unread_counts_when_opening_a_conversation(self):
        ui = self.make_ui("B")
        manager = ui.chat_manager
        incoming = create_chat_message("A", "B", "Unread")
        ui.handle_incoming_message(incoming)
        ui.handle_incoming_message(create_chat_message("C", "B", "Also unread"))
        self.assertEqual(manager.get_unread_count(), {"A": 1, "C": 1})

        ui.peer_manager.update_peer(
            {"peer_id": "A", "username": "Alice", "tcp_port": 5000}, LOOPBACK
        )
        with (
            patch("builtins.input", side_effect=["1", "/exit"]),
            patch.object(ChatClient, "connect", side_effect=ConnectionRefusedError),
        ):
            ui.start_chat()

        self.assertEqual(manager.get_unread_count(), {"A": 0, "C": 1})
        self.assertEqual(manager.get_messages("A"), [incoming])
        self.assertIsNone(manager.current_chat_peer)

    def test_tc11_send_and_receive_once_per_history(self):
        ui_a = self.make_ui("A")
        ui_b = self.make_ui("B")
        server_b = self.start_server(ui_b.handle_incoming_message)
        _, conn = self.connect(server_b)
        peer = {"peer_id": "B", "ip": LOOPBACK, "tcp_port": conn.getpeername()[1]}
        with patch.object(ui_a, "get_user_input", side_effect=["Hello", "/back"]):
            ui_a.chat_loop(peer, conn)

        sent = ui_a.chat_manager.get_messages("B")
        self.assertEqual(len(sent), 1)
        self.wait_for(lambda: bool(ui_b.chat_manager.get_messages("A")))
        conn.close()
        self.wait_for(lambda: not server_b.client_threads)
        self.assertEqual(ui_b.chat_manager.get_messages("A"), sent)
        self.assertEqual(ui_b.chat_manager.get_unread_count("A"), 1)

    def test_tc12_concurrent_access_is_consistent(self):
        manager = ChatManager("B")
        worker_count = 8
        messages_per_worker = 30
        start = threading.Barrier(worker_count)

        def exchange(worker_id):
            start.wait(timeout=WAIT)
            for sequence in range(messages_per_worker):
                content = f"{worker_id}/{sequence}"
                manager.handle_incoming_message(create_chat_message("A", "B", content))
                manager.add_message("C", create_chat_message("B", "C", content))
                manager.get_messages("A")
                manager.get_unread_count()

        workers = [
            threading.Thread(target=exchange, args=(i,), daemon=True)
            for i in range(worker_count)
        ]
        for worker in workers:
            worker.start()
        deadline = time.monotonic() + WAIT
        for worker in workers:
            worker.join(max(0, deadline - time.monotonic()))
        self.assertFalse(any(worker.is_alive() for worker in workers))

        expected = {
            f"{i}/{sequence}"
            for i in range(worker_count)
            for sequence in range(messages_per_worker)
        }
        for peer_id in ("A", "C"):
            history = manager.get_messages(peer_id)
            self.assertEqual(len(history), len(expected))
            self.assertEqual({message["content"] for message in history}, expected)
        self.assertEqual(manager.get_unread_count(), {"A": len(expected)})


if __name__ == "__main__":
    unittest.main()
