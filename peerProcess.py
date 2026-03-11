import sys
import socket
import math
import threading
import time
import logging
import struct
import os
from message import ProtocolMessage
from BitFieldTracker import BitFieldTracker

def setup_logger(peer_id):
    log_filename = f"log_peer_{peer_id}.log"
    logger = logging.getLogger(f"Peer{peer_id}")
    logger.setLevel(logging.INFO)
    
    if not logger.handlers:
        file_handler = logging.FileHandler(log_filename)
        formatter = logging.Formatter('%(asctime)s: %(message)s', datefmt='[%Y-%m-%d %H:%M:%S]')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
    return logger

def load_common_config(file_path):
    settings = {}
    with open(file_path, 'r') as cfg:
        for line in cfg:
            parts = line.strip().split()
            if len(parts) == 2:
                key, value = parts
                settings[key] = int(value) if value.isdigit() else value

    if "FileSize" in settings and "PieceSize" in settings:
        settings["TotalPieces"] = math.ceil(settings["FileSize"] / settings["PieceSize"])

    return settings


def load_peer_info(file_path):
    peer_map = {}
    with open(file_path, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) == 4:
                pid = int(parts[0])
                peer_map[pid] = {
                    "host": parts[1],
                    "port": int(parts[2]),
                    "file": int(parts[3]) == 1
                }
    return peer_map


def recv_exact(sock, num_bytes):
    """Reads exactly num_bytes from the socket."""
    data = b''
    while len(data) < num_bytes:
        packet = sock.recv(num_bytes - len(data))
        if not packet:
            return None
        data += packet
    return data

def get_peer_directory(peer_id):
    return os.path.join(os.getcwd(), f"peer_{peer_id}")


def get_peer_file_path(peer_id, filename):
    return os.path.join(get_peer_directory(peer_id), filename)


def get_piece_offset(piece_index, piece_size):
    return piece_index * piece_size


def get_piece_length(piece_index, file_size, piece_size, total_pieces):
    if piece_index < total_pieces - 1:
        return piece_size
    return file_size - (piece_size * (total_pieces - 1))


def read_piece_from_file(peer_id, piece_index, filename, piece_size, file_size, total_pieces):
    file_path = get_peer_file_path(peer_id, filename)
    offset = get_piece_offset(piece_index, piece_size)
    piece_length = get_piece_length(piece_index, file_size, piece_size, total_pieces)

    with open(file_path, "rb") as f:
        f.seek(offset)
        return f.read(piece_length)


def write_piece_to_file(peer_id, piece_index, data, filename, piece_size):
    peer_dir = get_peer_directory(peer_id)
    os.makedirs(peer_dir, exist_ok=True)

    file_path = get_peer_file_path(peer_id, filename)
    offset = get_piece_offset(piece_index, piece_size)

    mode = "r+b" if os.path.exists(file_path) else "wb"
    with open(file_path, mode) as f:
        f.seek(offset)
        f.write(data)

def send_have_to_all(piece_index, peer_connections):
    for conn in peer_connections:
        try:
            conn.sendall(ProtocolMessage.have(piece_index))
        except Exception:
            pass

def handle_connection(connection, my_id, tracker, logger, common, connected_peer_id=None, handshake_done=False):
    if not handshake_done:
        handshake = connection.recv(32)
        parsed = ProtocolMessage.decode_handshake(handshake)

        if parsed is None:
            connection.close()
            return

        header, peer_id = parsed
        logger.info(f"Peer {my_id} is connected from Peer {peer_id}.")
        
        reply = ProtocolMessage.make_handshake(my_id)
        connection.sendall(reply)
    else:
        peer_id = connected_peer_id

    if tracker.totalAmount() > 0:
        connection.sendall(ProtocolMessage.bitfield(tracker.bitfieldPayload()))

    neighbor_bitfield = None

    while True:
        try:
            length_bytes = recv_exact(connection, 4)
            if not length_bytes:
                break

            msg_len = struct.unpack(">I", length_bytes)[0]

            msg_body = recv_exact(connection, msg_len)
            if not msg_body:
                break

            msg_type = msg_body[0]
            payload = msg_body[1:]

            if msg_type == ProtocolMessage.TYPE_CHOKE:
                logger.info(f"Peer {my_id} is choked by {peer_id}.")

            elif msg_type == ProtocolMessage.TYPE_UNCHOKE:
                logger.info(f"Peer {my_id} is unchoked by {peer_id}.")
                if neighbor_bitfield is not None:
                    piece = tracker.pick_from_neighbor(neighbor_bitfield)

                    if piece is not None:
                        tracker.add_requested(piece)
                        connection.sendall(ProtocolMessage.request(piece))

            elif msg_type == ProtocolMessage.TYPE_INTERESTED:
                logger.info(f"Peer {my_id} received the 'interested' message from {peer_id}.")

            elif msg_type == ProtocolMessage.TYPE_NOT_INTERESTED:
                logger.info(f"Peer {my_id} received the 'not interested' message from {peer_id}.")

            elif msg_type == ProtocolMessage.TYPE_BITFIELD:
                neighbor_bitfield = list(payload)

                piece = tracker.pick_from_neighbor(neighbor_bitfield)

                if piece is not None:
                    connection.sendall(ProtocolMessage.interested())
                else:
                    connection.sendall(ProtocolMessage.not_interested())


            elif msg_type == ProtocolMessage.TYPE_HAVE:
                piece = int.from_bytes(payload, byteorder="big")
                logger.info(f"Peer {my_id} received the 'have' message from {peer_id} for the piece {piece}.")
                
                if neighbor_bitfield is None:
                    neighbor_bitfield = [0] * tracker.total_pieces

                if 0 <= piece < len(neighbor_bitfield):
                    neighbor_bitfield[piece] = 1

                if tracker.interested_in(neighbor_bitfield):
                    connection.sendall(ProtocolMessage.interested())
                else:
                    connection.sendall(ProtocolMessage.not_interested())

            elif msg_type == ProtocolMessage.TYPE_REQUEST:
                piece = int.from_bytes(payload, byteorder="big")

                if tracker.piece_owned(piece):
                    piece_data = read_piece_from_file(
                        my_id,
                        piece,
                        common["FileName"],
                        common["PieceSize"],
                        common["FileSize"],
                        common["TotalPieces"]
                    )
                    connection.sendall(ProtocolMessage.piece(piece, piece_data))
            
            elif msg_type == ProtocolMessage.TYPE_PIECE:
                piece = int.from_bytes(payload[:4], byteorder="big")
                piece_data = payload[4:]

                write_piece_to_file(
                    my_id,
                    piece,
                    piece_data,
                    common["FileName"],
                    common["PieceSize"]
                )

                tracker.add_received(piece)

                logger.info(
                    f"Peer {my_id} has downloaded the piece {piece} from {peer_id}. "
                    f"Now the number of pieces it has is {tracker.totalAmount()}."
                )

                if tracker.file_complete():
                    logger.info(f"Peer {my_id} has downloaded the complete file.")

                if neighbor_bitfield is not None:
                    next_piece = tracker.pick_from_neighbor(neighbor_bitfield)

                    if next_piece is not None:
                        tracker.add_requested(next_piece)
                        connection.sendall(ProtocolMessage.request(next_piece))

        except Exception:
            break

    connection.close()


def start_server(my_id, host, port, tracker, logger, common):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen()
    logger.info(f"Peer {my_id} started listening on {port}...")

    while True:
        conn, addr = server.accept()
        thread = threading.Thread(target=handle_connection, args=(conn, my_id, tracker, logger, common, None, False))
        thread.start()

def connect_to_previous_peers(my_id, peer_data, tracker, logger, common):
    for pid in peer_data:
        if pid < my_id:
            try:
                peer = peer_data[pid]
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((peer["host"], peer["port"]))

                logger.info(f"Peer {my_id} makes a connection to Peer {pid}.")

                handshake = ProtocolMessage.make_handshake(my_id)
                sock.sendall(handshake)

                response = sock.recv(32)
                parsed = ProtocolMessage.decode_handshake(response)
                
                thread = threading.Thread(target=handle_connection, args=(sock, my_id, tracker, logger, common, pid, True))
                thread.start()

            except Exception as e:
                print(f"Failed connection to peer {pid}. Error: {e}")

if __name__ == "__main__":

    if len(sys.argv) != 2:
        print("Usage: python peerProcess.py <peerID>")
        sys.exit()

    my_peer_id = int(sys.argv[1])

    common = load_common_config("Common.cfg")
    peers = load_peer_info("PeerInfo.cfg")

    if my_peer_id not in peers:
        print("Peer not defined in config")
        sys.exit()

    my_info = peers[my_peer_id]

    logger = setup_logger(my_peer_id)

    tracker = BitFieldTracker(
        total_pieces=common["TotalPieces"],
        has_complete_file=my_info["file"]
    )

    server_thread = threading.Thread(
        target=start_server,
        args=(my_peer_id, my_info["host"], my_info["port"], tracker, logger, common),
        daemon=True
    )
    server_thread.start()

    time.sleep(0.5)
    connect_to_previous_peers(my_peer_id, peers, tracker, logger, common)

    server_thread.join()