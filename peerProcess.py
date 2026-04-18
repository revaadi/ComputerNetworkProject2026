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
from ConnectionManager import ConnectionManager


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
    data = b''
    while len(data) < num_bytes:
        packet = sock.recv(num_bytes - len(data))
        if not packet:
            return None
        data += packet
    return data


def split_file_into_pieces(file_path, piece_size):
    with open(file_path, "rb") as f:
        data = f.read()
    return [data[i:i + piece_size] for i in range(0, len(data), piece_size)]


def handle_connection(conn, my_id, tracker, logger, common, conn_manager,
                      peer_id=None, handshake_done=False):

    if not handshake_done:
        handshake = recv_exact(conn, 32)
        parsed = ProtocolMessage.decode_handshake(handshake)
        _, peer_id = parsed
        logger.info(f"Peer {my_id} connected from Peer {peer_id}")
        conn.sendall(ProtocolMessage.make_handshake(my_id))
    else:
        peer_id = peer_id

    conn_manager.add_connection(peer_id, conn)

    if tracker.totalAmount() > 0:
        conn.sendall(ProtocolMessage.bitfield(tracker.bitfieldPayload()))

    neighbor_bitfield = None

    while True:
        try:
            length_bytes = recv_exact(conn, 4)
            if not length_bytes:
                break

            msg_len = struct.unpack(">I", length_bytes)[0]
            msg_body = recv_exact(conn, msg_len)

            msg_type = msg_body[0]
            payload = msg_body[1:]

            if msg_type == ProtocolMessage.TYPE_BITFIELD:
                neighbor_bitfield = tracker.decode_bitfield(payload)

                if tracker.interested_in(neighbor_bitfield):
                    conn.sendall(ProtocolMessage.interested())
                else:
                    conn.sendall(ProtocolMessage.not_interested())

            elif msg_type == ProtocolMessage.TYPE_INTERESTED:
                conn_manager.set_interested_in_me(peer_id, True)

            elif msg_type == ProtocolMessage.TYPE_NOT_INTERESTED:
                conn_manager.set_interested_in_me(peer_id, False)

            elif msg_type == ProtocolMessage.TYPE_REQUEST:
                piece_id = struct.unpack(">I", payload)[0]
                piece_data = pieces[piece_id]
                conn.sendall(ProtocolMessage.piece(piece_id, piece_data))

            elif msg_type == ProtocolMessage.TYPE_PIECE:
                piece_id = struct.unpack(">I", payload[:4])[0]
                piece_data = payload[4:]

                tracker.add_received(piece_id)
                logger.info(f"Received piece {piece_id} from Peer {peer_id}")

        except Exception:
            break

    conn_manager.remove_connection(peer_id)
    conn.close()


def request_loop(my_id, tracker, conn_manager):
    while True:
        time.sleep(2)

        with conn_manager.lock:
            for peer_id, state in conn_manager.peers.items():
                if state["state"].name != "CHOKED":
                    bitfield = state["connection"]
                    piece = tracker.pick_from_neighbor([1]*tracker.total_pieces)

                    if piece is not None:
                        state["connection"].sendall(ProtocolMessage.request(piece))


def start_server(my_id, host, port, tracker, logger, common, conn_manager):
    server = socket.socket()
    server.bind((host, port))
    server.listen()

    logger.info(f"Peer {my_id} listening on {port}")

    while True:
        conn, _ = server.accept()
        threading.Thread(
            target=handle_connection,
            args=(conn, my_id, tracker, logger, common, conn_manager),
            daemon=True
        ).start()


def connect_to_peers(my_id, peers, tracker, logger, common, conn_manager):
    for pid in peers:
        if pid < my_id:
            peer = peers[pid]

            sock = socket.socket()
            sock.connect((peer["host"], peer["port"]))

            sock.sendall(ProtocolMessage.make_handshake(my_id))
            sock.recv(32)

            threading.Thread(
                target=handle_connection,
                args=(sock, my_id, tracker, logger, common, conn_manager, pid, True),
                daemon=True
            ).start()


if __name__ == "__main__":

    my_id = int(sys.argv[1])

    common = load_common_config("Common.cfg")
    peers = load_peer_info("PeerInfo.cfg")

    my_info = peers[my_id]

    logger = setup_logger(my_id)

    tracker = BitFieldTracker(common["TotalPieces"], my_info["file"])
    conn_manager = ConnectionManager()

    global pieces
    file_path = f"peer_{my_id}/thefile"
    pieces = split_file_into_pieces(file_path, common["PieceSize"])


    threading.Thread(
        target=start_server,
        args=(my_id, my_info["host"], my_info["port"], tracker, logger, common, conn_manager),
        daemon=True
    ).start()

    time.sleep(2)

    connect_to_peers(my_id, peers, tracker, logger, common, conn_manager)

    threading.Thread(
        target=request_loop,
        args=(my_id, tracker, conn_manager),
        daemon=True
    ).start()

    while True:
        time.sleep(5)