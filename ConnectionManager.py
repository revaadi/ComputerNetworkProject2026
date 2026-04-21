import threading
from enum import Enum

class PeerState(Enum):
    CONNECTING = "CONNECTING"
    HANDSHAKING = "HANDSHAKING"
    CONNECTED = "CONNECTED"
    CHOKED = "CHOKED"
    UNCHOKED = "UNCHOKED"
    COMPLETED = "COMPLETED"
    DISCONNECTED = "DISCONNECTED"

class ConnectionManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.peers = {}

    def add_connection(self, peer_id, connection):
        with self.lock:
            self.peers[peer_id] = {
                "connection": connection,
                "send_lock": threading.Lock(),
                "state": PeerState.CONNECTED,
                "choked_by_me": True,
                "choking_me": True,
                "interested_in_me": False,
                "download_bytes": 0,
                "neighbor_complete": False,
                "pending_request": None,
                "bitfield": None
            }

    def send_message(self, peer_id, message_bytes):
        with self.lock:
            if peer_id not in self.peers:
                return
            peer_data = self.peers[peer_id]
        
        with peer_data["send_lock"]:
            try:
                peer_data["connection"].sendall(message_bytes)
            except Exception:
                pass

    def broadcast(self, message_bytes):
        with self.lock:
            peer_ids = list(self.peers.keys())
        for pid in peer_ids:
            self.send_message(pid, message_bytes)

    def remove_connection(self, peer_id):
        with self.lock:
            if peer_id in self.peers:
                del self.peers[peer_id]

    def record_download(self, peer_id, num_bytes):
        with self.lock:
            if peer_id in self.peers:
                self.peers[peer_id]["download_bytes"] += num_bytes

    def set_interested_in_me(self, peer_id, is_interested):
        with self.lock:
            if peer_id in self.peers:
                self.peers[peer_id]["interested_in_me"] = is_interested

    def set_choking_me(self, peer_id, is_choking):
        with self.lock:
            if peer_id in self.peers:
                self.peers[peer_id]["choking_me"] = is_choking

    def get_interested_peers(self):
        with self.lock:
            return [pid for pid, state in self.peers.items() if state["interested_in_me"]]

    def get_and_reset_download_rates(self):
        rates = {}
        with self.lock:
            for peer_id, state in self.peers.items():
                rates[peer_id] = state["download_bytes"]
                state["download_bytes"] = 0
        return rates
    
    def set_state(self, peer_id, new_state):
        with self.lock:
            if peer_id in self.peers:
                self.peers[peer_id]["state"] = new_state

    def get_state(self, peer_id):
        with self.lock:
            if peer_id in self.peers:
                return self.peers[peer_id]["state"]
            return None

    def mark_completed(self, peer_id):
        with self.lock:
            if peer_id in self.peers:
                self.peers[peer_id]["neighbor_complete"] = True
                self.peers[peer_id]["state"] = PeerState.COMPLETED

    def mark_disconnected(self, peer_id):
        with self.lock:
            if peer_id in self.peers:
                self.peers[peer_id]["state"] = PeerState.DISCONNECTED

    def get_pending_request(self, peer_id):
        with self.lock:
            if peer_id in self.peers:
                return self.peers[peer_id]["pending_request"]
        return None
        
    def set_pending_request(self, peer_id, piece_index):
        with self.lock:
            if peer_id in self.peers:
                self.peers[peer_id]["pending_request"] = piece_index

    def get_bitfield(self, peer_id):
        with self.lock:
            if peer_id in self.peers:
                return self.peers[peer_id]["bitfield"]
        return None
        
    def set_bitfield(self, peer_id, bitfield):
        with self.lock:
            if peer_id in self.peers:
                self.peers[peer_id]["bitfield"] = bitfield