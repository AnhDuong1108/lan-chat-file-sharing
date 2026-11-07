
import socket


class ChatManager:
    # Class này của Hải Việt
    def __init__(self, self_peer_id, peer_manager):
        self.self_peer_id = self_peer_id
        self.peer_manager = peer_manager
        self.conversations = {}
        self.current_chat_peer = None
        self.unread_counts = {}
        self.connections = {}

    def select_chat_peer(self, peer_id):
        # Chọn peer muốn trò chuyện
        pass

    def handle_incoming_message(self, message):
        # Xử lý tin nhắn nhận được
        pass

    def get_unread_count(self, peer_id):
        # Lấy số tin nhắn chưa đọc từ peer
        pass

    def mark_messages_as_read(self, peer_id):
        # Đánh dấu tin nhắn đã đọc
        pass

    def get_message(self, peer_id):
        # Lấy lịch sử trò chuyện với peer
        pass

    def get_connection(self, peer_id, conn):
        # Lấy kết nối socket với peer
        pass

    def remove_connection(self, peer_id):
        # Xóa kết nối socket với peer
        pass