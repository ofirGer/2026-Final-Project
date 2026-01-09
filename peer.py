import socket
import threading
import time
import json
import uuid
import os


class Peer:
    def __init__(self, shared_folder="shared"):
        self.peer_id = str(uuid.uuid4())
        self.broadcast_ip = "192.168.1.255"  # At home broadcast_ip=192.168.1.255, at school 172.16.255.255
        self.port = 50000
        self.broadcast_interval = 5
        self.peer_timeout = 15

        self.my_files = {}
        self.shared_folder = shared_folder
        # peer_id -> peer info
        self.peer_table = {}
        self.load_shared_files()

    def load_shared_files(self):
        """
        Scan the shared folder and build the my_files dictionary.
        """
        self.my_files.clear()

        if not os.path.isdir(self.shared_folder):
            print("Shared folder does not exist, creating it...")
            os.makedirs(self.shared_folder)

        for filename in os.listdir(self.shared_folder):
            path = os.path.join(self.shared_folder, filename)

            if os.path.isfile(path):
                size = os.path.getsize(path)
                self.my_files[filename] = {
                    "size": size
                }

        print("Loaded shared files:")
        print(self.my_files)
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
