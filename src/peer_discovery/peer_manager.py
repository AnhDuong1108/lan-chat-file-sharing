
class PeerManager:
    def __init__(self, self_peer_id):
        self.self_peer_id = self_peer_id
        self.peers = {}
        
    def update_peer(self, message, source_ip):
        pass
    def get_online_peers(self):
        pass
    def select_chat_peer(self, peer_id):
        pass
    def get_messages(self, peer_id):
        pass
    def send_message(self, peer_id, message):
        pass
    def remove_peer(self, peer_id):
        pass
    def get_all_peers(self):
        pass