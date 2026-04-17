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

    def pick_from_neighbor(self, neighbor_bitfield):
        with self.lock:
            possible_choices = [
                i for i in range(self.total_pieces)
                if neighbor_bitfield[i] == 1
                and self.bitfield[i] == 0
                and i not in self.requested_pieces
            ]
            if not possible_choices:
                return None
            return random.choice(possible_choices)

    def bitfieldPayload(self):
        with self.lock:
            result = bytearray()
            for i in range(0, self.total_pieces, 8):
                byte = 0
                for bit_index in range(8):
                    piece_index = i + bit_index
                    if piece_index < self.total_pieces and self.bitfield[piece_index] == 1:
                        byte |= (1 << (7 - bit_index))
                result.append(byte)
            return bytes(result)

    def decode_bitfield(self, payload):
        new_bitfield = [0] * self.total_pieces
        piece_index = 0
        for byte in payload:
            for bit in range(8):
                if piece_index >= self.total_pieces:
                    break
                if byte & (1 << (7 - bit)):
                    new_bitfield[piece_index] = 1
                piece_index += 1
        return new_bitfield

    def interested_in(self, neighbor_bitfield):
        with self.lock:
            for i in range(self.total_pieces):
                if neighbor_bitfield[i] == 1 and self.bitfield[i] == 0:
                    return True
            return False

    def clear_requested(self, piece_index):
        with self.lock:
            self.requested_pieces.discard(piece_index)

    def reset_requested_pieces(self):
        with self.lock:
            self.requested_pieces.clear()

    def missing_pieces(self):
        with self.lock:
            return [i for i in range(self.total_pieces) if self.bitfield[i] == 0]

    def has_any_pieces(self):
        with self.lock:
            return any(self.bitfield)