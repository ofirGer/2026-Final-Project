import socket
import threading
import time
import json
import uuid

# Unique ID for this peer
PEER_ID = str(uuid.uuid4())

# Example files this peer owns
my_files = {
    "file1.txt": 1024,
    "file2.mp3": 5000
}

# Discovery table
peer_table = {}

BROADCAST_PORT = 50000
BROADCAST_INTERVAL = 5  # seconds


def broadcast_presence():
    """Broadcast this peer's info to the local network."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    while True:
        message = json.dumps({
            "type": "PEER",
            "peer_id": PEER_ID,
            "files": my_files
        })
        sock.sendto(message.encode(), ('<broadcast>', BROADCAST_PORT))
        time.sleep(BROADCAST_INTERVAL)


def listen_for_peers():
    """Listen for broadcast messages from other peers."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('', BROADCAST_PORT))

    while True:
        data, addr = sock.recvfrom(4096)


        try:
            msg = data.decode()
            data_obj = json.loads(msg)

            if data_obj.get("type") == "PEER":
                peer_id = data_obj["peer_id"]

                # Ignore our own broadcasts
                if peer_id == PEER_ID:
                    continue
                print("Received broadcast from:", addr)

                peer_table[peer_id] = {
                    "ip": addr[0],
                    "files": data_obj["files"],
                    "last_seen": time.time()
                }

                print("Updated peer table:")
                print(peer_table)

        except Exception as e:
            print("Failed to process message:", e)


if __name__ == "__main__":
    threading.Thread(target=broadcast_presence, daemon=True).start()
    threading.Thread(target=listen_for_peers, daemon=True).start()

    while True:
        cmd = input("Enter 'table' to see known peers: ")
        if cmd == "table":
            print(peer_table)
