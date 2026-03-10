import struct

class ProtocolMessage:

    TYPE_CHOKE = 0
    TYPE_UNCHOKE = 1
    TYPE_INTERESTED = 2
    TYPE_NOT_INTERESTED = 3
    TYPE_HAVE = 4
    TYPE_BITFIELD = 5
    TYPE_REQUEST = 6
    TYPE_PIECE = 7

    HANDSHAKE_HEADER = b'P2PFILESHARINGPROJ'
    ZERO_PADDING = b'\x00' * 10

    @staticmethod
    def make_handshake(pid):
        peer_bytes = struct.pack(">I", pid)
        return ProtocolMessage.HANDSHAKE_HEADER + ProtocolMessage.ZERO_PADDING + peer_bytes

    @staticmethod
    def decode_handshake(raw_data):
        if len(raw_data) != 32:
            return None

        header = raw_data[:18]
        peer = struct.unpack(">I", raw_data[28:])[0]

        return header, peer

    @staticmethod
    def build_message(msg_id, body=b''):
        msg_length = len(body) + 1
        prefix = struct.pack(">I", msg_length)
        msg_type = struct.pack("B", msg_id)

        return prefix + msg_type + body

    @staticmethod
    def choke():
        return ProtocolMessage.build_message(ProtocolMessage.TYPE_CHOKE)

    @staticmethod
    def unchoke():
        return ProtocolMessage.build_message(ProtocolMessage.TYPE_UNCHOKE)

    @staticmethod
    def interested():
        return ProtocolMessage.build_message(ProtocolMessage.TYPE_INTERESTED)

    @staticmethod
    def not_interested():
        return ProtocolMessage.build_message(ProtocolMessage.TYPE_NOT_INTERESTED)

    @staticmethod
    def have(piece_id):
        payload = struct.pack(">I", piece_id)
        return ProtocolMessage.build_message(ProtocolMessage.TYPE_HAVE, payload)

    @staticmethod
    def bitfield(bitfield):
        return ProtocolMessage.build_message(ProtocolMessage.TYPE_BITFIELD, bitfield)

    @staticmethod
    def request(piece_id):
        payload = struct.pack(">I", piece_id)
        return ProtocolMessage.build_message(ProtocolMessage.TYPE_REQUEST, payload)

    @staticmethod
    def piece(piece_id, data):
        payload = struct.pack(">I", piece_id) + data
        return ProtocolMessage.build_message(ProtocolMessage.TYPE_PIECE, payload)

    @staticmethod
    def parse_packet(data):
        msg_len = struct.unpack(">I", data[:4])[0]
        msg_type = data[4]
        payload = data[5:5 + msg_len - 1]

        return msg_type, payload