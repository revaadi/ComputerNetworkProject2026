import sys
import socket
import math
import threading
import time
import logging
import struct
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


def handle_connection(connection, my_id, tracker, logger, connected_peer_id=None, handshake_done=False):
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

            elif msg_type == ProtocolMessage.TYPE_REQUEST:
                piece = int.from_bytes(payload, byteorder="big")

        except Exception:
            break

    connection.close()


def start_server(my_id, host, port, tracker, logger):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen()
    logger.info(f"Peer {my_id} started listening on {port}...")

    while True:
        conn, addr = server.accept()
        thread = threading.Thread(target=handle_connection, args=(conn, my_id, tracker, logger, None, False))
        thread.start()

def connect_to_previous_peers(my_id, peer_data, tracker, logger):
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
                
                thread = threading.Thread(target=handle_connection, args=(sock, my_id, tracker, logger, pid, True))
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
        args=(my_peer_id, my_info["host"], my_info["port"], tracker, logger),
        daemon=True
    )
    server_thread.start()

    time.sleep(0.5)
    connect_to_previous_peers(my_peer_id, peers, tracker, logger)

    server_thread.join()