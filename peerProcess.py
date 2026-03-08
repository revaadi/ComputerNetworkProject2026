import sys
import math

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
    