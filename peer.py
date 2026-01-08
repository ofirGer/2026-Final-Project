import socket
import threading
import time
import json
import uuid


class Peer:
    def __init__(self, broadcast_ip="172.16.255.255", port=50000):
        self.peer_id = str(uuid.uuid4())
        self.broadcast_ip = broadcast_ip
        self.port = port

        self.broadcast_interval = 5
        self.peer_timeout = 15

        self.my_files = {
            "file1.txt": 1024,
            "file2.mp3": 5000
        }

        # peer_id -> peer info
        self.peer_table = {}

    def start(self):
        threading.Thread(target=self.broadcast_presence, daemon=True).start()
        threading.Thread(target=self.listen_for_peers, daemon=True).start()
        threading.Thread(target=self.cleanup_peers, daemon=True).start()

        self.cli_loop()

    def broadcast_presence(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        while True:
            message = json.dumps({
                "type": "PEER",
                "peer_id": self.peer_id,
                "files": self.my_files
            })

            sock.sendto(message.encode(), (self.broadcast_ip, self.port))
            print("Broadcast sent")
            time.sleep(self.broadcast_interval)

    def listen_for_peers(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("0.0.0.0", self.port))

        while True:
            data, addr = sock.recvfrom(4096)

            try:
                obj = json.loads(data.decode())

                if obj.get("type") != "PEER":
                    continue

                peer_id = obj.get("peer_id")

                if peer_id == self.peer_id:
                    continue

                self.peer_table[peer_id] = {
                    "ip": addr[0],
                    "files": obj["files"],
                    "last_seen": time.time()
                }

                print(f"Discovered peer {peer_id} at {addr[0]}")

            except Exception as e:
                print("Error processing message:", e)

    def cleanup_peers(self):
        while True:
            now = time.time()
            removed = []

            for peer_id, info in list(self.peer_table.items()):
                if now - info["last_seen"] > self.peer_timeout:
                    removed.append(peer_id)
                    del self.peer_table[peer_id]

            if removed:
                print("Removed inactive peers:", removed)

            time.sleep(5)

    def cli_loop(self):
        while True:
            cmd = input("Enter 't' to show peer table: ").strip()
            if cmd == "t":
                print(json.dumps(self.peer_table, indent=4))


if __name__ == "__main__":
    peer = Peer()
    peer.start()
