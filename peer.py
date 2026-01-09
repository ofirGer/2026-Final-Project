import socket
import threading
import time
import json
import uuid


class Peer:
    # At home broadcast_ip=192.168.1.255, at school 172.16.255.255
    def __init__(self, file_manager, broadcast_ip="192.168.1.255", port=50000):
        self.peer_id = str(uuid.uuid4())
        self.broadcast_ip = broadcast_ip
        self.port = port
        self.broadcast_interval = 5
        self.peer_timeout = 15

        self.file_manager = file_manager
        self.peer_table = {}

    def start(self):
        threading.Thread(target=self.broadcast_presence, daemon=True).start()
        threading.Thread(target=self.listen_for_peers, daemon=True).start()
        threading.Thread(target=self.cleanup_peers, daemon=True).start()

    def broadcast_presence(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        while True:
            message = json.dumps({
                "type": "PEER",
                "peer_id": self.peer_id,
                "files": self.file_manager.my_files
            })

            sock.sendto(message.encode(), (self.broadcast_ip, self.port))
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

                peer_id = obj["peer_id"]
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
            for peer_id, info in list(self.peer_table.items()):
                if now - info["last_seen"] > self.peer_timeout:
                    del self.peer_table[peer_id]
                    print("Removed inactive peer:", peer_id)
            time.sleep(5)
