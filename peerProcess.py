import sys
import socket
import math
import threading
import time
from message import ProtocolMessage
from BitFieldTracker import BitFieldTracker

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


def handle_connection(connection, my_id, tracker):
    handshake = connection.recv(32)
    parsed = ProtocolMessage.decode_handshake(handshake)

    if parsed is None:
        connection.close()
        return

    header, peer_id = parsed
    print(f"Peer {my_id} received handshake from Peer {peer_id}")
    reply = ProtocolMessage.make_handshake(my_id)
    connection.sendall(reply)

    connection.sendall(
        ProtocolMessage.bitfield(tracker.bitfieldPayload())
    )

    neighbor_bitfield = None

    while True:
        try:
            data = connection.recv(4096)
            if not data:
                break

            msg_type, payload = ProtocolMessage.parse_packet(data)

            if msg_type == ProtocolMessage.TYPE_CHOKE:
                print(f"Peer {peer_id} choked connection")

            elif msg_type == ProtocolMessage.TYPE_UNCHOKE:
                print(f"Peer {peer_id} unchoked connection")

                if neighbor_bitfield is not None:
                    piece = tracker.pick_from_neighbor(neighbor_bitfield)

                    if piece is not None:
                        tracker.add_requested(piece)
                        connection.sendall(
                            ProtocolMessage.request(piece)
                        )

            elif msg_type == ProtocolMessage.TYPE_INTERESTED:
                print(f"Peer {peer_id} is interested")

            elif msg_type == ProtocolMessage.TYPE_NOT_INTERESTED:
                print(f"Peer {peer_id} not interested")

            elif msg_type == ProtocolMessage.TYPE_BITFIELD:
                neighbor_bitfield = list(payload)

                piece = tracker.pick_from_neighbor(neighbor_bitfield)

                if piece is not None:
                    print(f"Peer {my_id} is interested in Peer {peer_id}")
                    connection.sendall(ProtocolMessage.interested())
                else:
                    connection.sendall(ProtocolMessage.not_interested())


            elif msg_type == ProtocolMessage.TYPE_HAVE:
                piece = int.from_bytes(payload, byteorder="big")
                print(f"Peer {peer_id} has piece {piece}")

            elif msg_type == ProtocolMessage.TYPE_REQUEST:
                piece = int.from_bytes(payload, byteorder="big")
                print(f"Peer {peer_id} requested piece {piece}")

        except:
            break

    connection.close()


def start_server(my_id, host, port, tracker):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen()
    print(f"Peer {my_id} listening on {port}")

    while True:
        conn, addr = server.accept()
        thread = threading.Thread(target=handle_connection, args=(conn, my_id, tracker))
        thread.start()


def connect_to_previous_peers(my_id, peer_data, tracker):
    for pid in peer_data:
        if pid < my_id:
            try:
                peer = peer_data[pid]
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((peer["host"], peer["port"]))

                handshake = ProtocolMessage.make_handshake(my_id)
                sock.sendall(handshake)

                response = sock.recv(32)
                parsed = ProtocolMessage.decode_handshake(response)
                if parsed:
                    header, peer_id = parsed
                    print(f"Peer {my_id} received handshake reply from Peer {peer_id}")

                thread = threading.Thread(target=handle_connection, args=(sock, my_id, tracker))
                thread.start()

                print(f"Connected to peer {pid}")

            except:
                print(f"Failed connection to peer {pid}")


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

    tracker = BitFieldTracker(
        total_pieces=common["TotalPieces"],
        has_complete_file=my_info["file"]
)

    server_thread = threading.Thread(
        target=start_server,
        args=(my_peer_id, my_info["host"], my_info["port"], tracker),
        daemon=True
    )
    server_thread.start()

    time.sleep(0.5)
    connect_to_previous_peers(my_peer_id, peers, tracker)

    server_thread.join()