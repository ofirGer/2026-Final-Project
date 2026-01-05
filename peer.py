import socket
import threading
import time
import json
import uuid

PEER_ID = str(uuid.uuid4())

my_files = {
    "file1.txt": 1024,
    "file2.mp3": 5000
}

peer_table = {}

BROADCAST_PORT = 50000
BROADCAST_INTERVAL = 5


def broadcast_presence():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    while True:
        message = json.dumps({
            "type": "PEER",
            "peer_id": PEER_ID,
            "files": my_files
        })

        sock.sendto(message.encode(), ('172.16.255.255', BROADCAST_PORT))
        print("Broadcast sent")
        time.sleep(BROADCAST_INTERVAL)


def listen_for_peers():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('0.0.0.0', BROADCAST_PORT))

    while True:
        data, addr = sock.recvfrom(4096)


        try:
            obj = json.loads(data.decode())

            if obj.get("type") == "PEER":
                peer_id = obj["peer_id"]

                if peer_id == PEER_ID:
                    continue
                print("Received raw data from", addr)
                peer_table[peer_id] = {
                    "ip": addr[0],
                    "files": obj["files"],
                    "last_seen": time.time()
                }

                print("Updated peer table:")
                print(peer_table)

        except Exception as e:
            print("Error:", e)


if __name__ == "__main__":
    threading.Thread(target=broadcast_presence, daemon=True).start()
    threading.Thread(target=listen_for_peers, daemon=True).start()

    while True:
        if input("Enter 't': ") == "t":
            print(peer_table)
