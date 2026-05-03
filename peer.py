import socket
import threading
import time
import json
import uuid
import os
from protocol import Protocol


class Peer:
    def __init__(self, file_manager, broadcast_ip="172.16.255.255", port=50000):
        self.peer_id = str(uuid.uuid4())
        self.broadcast_ip = broadcast_ip
        self.port = port
        self.broadcast_interval = 5
        self.peer_timeout = 15

        self.file_manager = file_manager
        self.peer_table = {}
        self.running = True

    def start(self):
        threading.Thread(target=self.broadcast_presence, daemon=True).start()
        threading.Thread(target=self.listen_for_peers, daemon=True).start()
        threading.Thread(target=self.cleanup_peers, daemon=True).start()

        # --- NEW: Start TCP Server ---


    def broadcast_presence(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        while self.running:
            message = json.dumps({
                "type": "PEER",
                "peer_id": self.peer_id,
                # --- NEW: Advertise TCP Port ---
                "tcp_port": Protocol.TCP_PORT,
                "files": self.file_manager.get_files_summary()
            })
            sock.sendto(message.encode(), (self.broadcast_ip, self.port))
            time.sleep(self.broadcast_interval)

    def listen_for_peers(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("0.0.0.0", self.port))

        while self.running:
            try:
                data, addr = sock.recvfrom(4096)
                obj = json.loads(data.decode())

                if obj.get("type") != "PEER" or obj["peer_id"] == self.peer_id:
                    continue

                self.peer_table[obj["peer_id"]] = {
                    "ip": addr[0],
                    "files": obj["files"],
                    "last_seen": time.time()
                }
                # (Optional: You can keep your print here if you want)
            except Exception as e:
                print("Error processing message:", e)

    def cleanup_peers(self):
        while self.running:
            now = time.time()
            for peer_id, info in list(self.peer_table.items()):
                if now - info["last_seen"] > self.peer_timeout:
                    del self.peer_table[peer_id]
                    # print(f"Removed inactive peer: {peer_id}") # Uncomment if needed
            time.sleep(5)
