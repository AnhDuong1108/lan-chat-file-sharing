
class ChatClient:
    # ChatClient: chỉ nhận và giải mã dữ liệu, sau đó gọi callback.
    #Nhat Nghi tự design class này
    def __init__(self, peer_id, ip, tcp_port):
        pass

    def connect(self) -> bool:
        pass

    def send_message(self, conn, message: dict) -> bool:
        pass

    def receive_messages(self, conn, callback):
        pass

    def close(self):
        pass

    def is_connected(self) -> bool:
        pass