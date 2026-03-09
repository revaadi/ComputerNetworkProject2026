import sys
import math
import socket
def parse_common_config(filepath):
    config = {}
    try:
        with open(filepath, 'r') as file:
            for line in file:
                parts = line.strip().split()
                if len(parts) == 2:
                    key = parts[0]
                    value = parts[1]
                    
                    if value.isdigit():
                        config[key] = int(value)
                    else:
                        config[key] = value
                        
        if 'FileSize' in config and 'PieceSize' in config:
            config['num_pieces'] = math.ceil(config['FileSize'] / config['PieceSize'])
            
        return config
    except FileNotFoundError:
        print(f"Error: File not found")
        return None

def parse_peer_info(filepath):
    peers = {}
    try:
        with open(filepath, 'r') as file:
            for line in file:
                parts = line.strip().split()
                if len(parts) == 4:
                    peer_id = int(parts[0])
                    peers[peer_id] = {
                        'host': parts[1],
                        'port': int(parts[2]),
                        'has_file': int(parts[3]) == 1 
                    }
        return peers
    except FileNotFoundError:
        print(f"Error: File not found")
        return None

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Incorrect arguments")
        sys.exit(1)

    my_peer_id = int(sys.argv[1])
    print(f"Starting Peer {my_peer_id}...")

    common_cfg = parse_common_config('Common.cfg')
    peer_info = parse_peer_info('PeerInfo.cfg')

    if my_peer_id not in peer_info:
        print(f"Error: Peer {my_peer_id} not found in PeerInfo.cfg")
        sys.exit(1)

    my_info = peer_info[my_peer_id]
    
    print("\nInitialization Complete")
    print(f"My Info: {my_info}")
    
    #making the socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((my_info['host'], my_info['port']))
    server_socket.listen()
    print(f"Peer {my_peer_id} is running on port {my_info['port']}...")

    # connect to earlier peers
    for peer_id, info in peer_info.items():
        if peer_id < my_peer_id:
            try:
                client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                client_socket.connect((info['host'], info['port']))
                print(f"Peer {my_peer_id} connected to peer {peer_id}")
            except Exception as e:
                print(f"the connection has failed to peer {peer_id}: {e}")

    while True:
        conn, addr = server_socket.accept()
        print(f"Peer {my_peer_id} connected from {addr}")