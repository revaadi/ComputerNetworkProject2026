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