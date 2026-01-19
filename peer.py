import socket
import threading
import time
import json
import uuid
import os
from protocol import Protocol


class Peer:
    def __init__(self, file_manager, broadcast_ip="192.168.1.255", port=50000):
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
        threading.Thread(target=self.start_tcp_server, daemon=True).start()

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
                "files": self.file_manager.my_files
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

    # --- NEW: TCP Server Logic ---
    def start_tcp_server(self):
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.bind(("0.0.0.0", Protocol.TCP_PORT))
        server_sock.listen(5)

        while self.running:
            try:
                client_sock, _ = server_sock.accept()
                threading.Thread(target=self.handle_client, args=(client_sock,), daemon=True).start()
            except Exception as e:
                print(f"TCP Server error: {e}")

    def handle_client(self, conn):
        try:
            data = conn.recv(1024)
            cmd, filename = Protocol.parse_message(data)

            if cmd == Protocol.CMD_DOWNLOAD:
                file_path = self.file_manager.get_file_path(filename)

                if file_path and os.path.exists(file_path):
                    filesize = os.path.getsize(file_path)
                    conn.send(Protocol.prepare_response_exists(filesize))

                    conn.recv(1024)  # Wait for Ack

                    with open(file_path, "rb") as f:
                        while True:
                            bytes_read = f.read(Protocol.BUFFER_SIZE)
                            if not bytes_read: break
                            conn.sendall(bytes_read)
                else:
                    conn.send(Protocol.prepare_response_error("File Not Found"))
        except Exception as e:
            print(f"Transfer error: {e}")
        finally:
            conn.close()