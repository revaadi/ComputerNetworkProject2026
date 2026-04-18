import random
import threading

class BitFieldTracker:

    def __init__(self, total_pieces, has_complete_file):
        self.lock = threading.Lock()
        self.total_pieces = total_pieces

        if has_complete_file:
            self.bitfield = [1] * total_pieces
        else:
            self.bitfield = [0] * total_pieces

        self.requested_pieces = set()
        self.peer_bitfields = {}

    def piece_owned(self, piece_index):
        with self.lock:
            return self.bitfield[piece_index] == 1

    def add_requested(self, piece_index):
        with self.lock:
            self.requested_pieces.add(piece_index)

    def add_received(self, piece_index):
        with self.lock:
            self.bitfield[piece_index] = 1
            self.requested_pieces.discard(piece_index)

    def totalAmount(self):
        with self.lock:
            return sum(self.bitfield)

    def file_complete(self):
        with self.lock:
            return all(self.bitfield)

    def mark_peer_has(self, peer_id, piece_index):
        with self.lock:
            if peer_id not in self.peer_bitfields:
                self.peer_bitfields[peer_id] = set()
            self.peer_bitfields[peer_id].add(piece_index)

    def update_peer_bitfield(self, peer_id, bitfield):
        with self.lock:
            self.peer_bitfields[peer_id] = {
                i for i in range(len(bitfield)) if bitfield[i] == 1
            }

    def peer_has_piece(self, peer_id, piece_index):
        with self.lock:
            return (
                peer_id in self.peer_bitfields and
                piece_index in self.peer_bitfields[peer_id]
            )

    def pick_from_neighbor(self, neighbor_bitfield):
        with self.lock:
            choices = [
                i for i in range(self.total_pieces)
                if neighbor_bitfield[i] == 1
                and self.bitfield[i] == 0
                and i not in self.requested_pieces
            ]
            return random.choice(choices) if choices else None

    def bitfieldPayload(self):
        with self.lock:
            result = bytearray()
            for i in range(0, self.total_pieces, 8):
                byte = 0
                for bit in range(8):
                    idx = i + bit
                    if idx < self.total_pieces and self.bitfield[idx]:
                        byte |= (1 << (7 - bit))
                result.append(byte)
            return bytes(result)

    def decode_bitfield(self, payload):
        bitfield = [0] * self.total_pieces
        idx = 0
        for byte in payload:
            for bit in range(8):
                if idx >= self.total_pieces:
                    break
                if byte & (1 << (7 - bit)):
                    bitfield[idx] = 1
                idx += 1
        return bitfield

    def interested_in(self, neighbor_bitfield):
        with self.lock:
            return any(
                neighbor_bitfield[i] == 1 and self.bitfield[i] == 0
                for i in range(self.total_pieces)
            )

    def has_all_pieces(self):
        with self.lock:
            return all(self.bitfield)

    def has_piece(self, piece_index):
        with self.lock:
            return self.bitfield[piece_index] == 1

    def missing_pieces(self):
        with self.lock:
            return [i for i in range(self.total_pieces) if self.bitfield[i] == 0]