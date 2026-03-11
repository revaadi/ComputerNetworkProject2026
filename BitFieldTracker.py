import random

class BitFieldTracker:

    def __init__(self, total_pieces, has_complete_file):
        self.total_pieces = total_pieces

        if has_complete_file:
            self.bitfield = [1] * total_pieces
        else:
            self.bitfield = [0] * total_pieces

        self.requested_pieces = set()

    def piece_owned(self, piece_index):
        return self.bitfield[piece_index] == 1

    def add_requested(self, piece_index):
        self.requested_pieces.add(piece_index)

    def add_received(self, piece_index):
        self.bitfield[piece_index] = 1
        if piece_index in self.requested_pieces:
            self.requested_pieces.remove(piece_index)


    def totalAmount(self):
        return sum(self.bitfield)

    def file_complete(self):
        return all(self.bitfield)

    def pick_from_neighbor(self, neighbor_bitfield):

        possible_choices = []

        for i in range(self.total_pieces):
            if (
                neighbor_bitfield[i] == 1 and
                self.bitfield[i] == 0 and
                i not in self.requested_pieces
            ):
                possible_choices.append(i)

        if not possible_choices:
            return None

        return random.choice(possible_choices)

    def bitfieldPayload(self):
        return bytes(self.bitfield)
    
    def missing_pieces(self):
        missing = []
        for i in range(self.total_pieces):
            if self.bitfield[i] == 0:
                missing.append(i)
        return missing

    def owned_pieces(self):
        owned = []
        for i in range(self.total_pieces):
            if self.bitfield[i] == 1:
                owned.append(i)
        return owned

    def has_any_pieces(self):
        return self.totalAmount() > 0

    def clear_requested(self, piece_index):
        if piece_index in self.requested_pieces:
            self.requested_pieces.remove(piece_index)

    def interested_in(self, neighbor_bitfield):
        for i in range(self.total_pieces):
            if neighbor_bitfield[i] == 1 and self.bitfield[i] == 0:
                return True
        return False
    
    def count_owned(self):
        return sum(self.bitfield)

    def count_missing(self):
        return self.total_pieces - sum(self.bitfield)

    def is_piece_requested(self, piece_index):
        return piece_index in self.requested_pieces

    def mark_piece_missing(self, piece_index):
        self.bitfield[piece_index] = 0
        if piece_index in self.requested_pieces:
            self.requested_pieces.remove(piece_index)

    def reset_requested_pieces(self):
        self.requested_pieces.clear()