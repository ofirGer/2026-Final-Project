import socket
import threading
import time
import json
import uuid
import os
import hashlib
import base64
from cryptography.fernet import Fernet, InvalidToken
from protocol import Protocol


class Peer:
    def __init__(self, file_manager, broadcast_ip="172.16.255.255", port=50000,):
        self.peer_id = str(uuid.uuid4())
        self.broadcast_ip = broadcast_ip
        self.port = port
        self.broadcast_interval = 5
        self.peer_timeout = 15

        self.file_manager = file_manager
        self.peer_table = {}
        self.running = True

        self.fernet = None
        self.username = ""

    def start(self):
        # Start the UDP discovery only if three is a swarm key
        if self.fernet is not None:
            threading.Thread(target=self.broadcast_presence, daemon=True).start()
            threading.Thread(target=self.listen_for_peers, daemon=True).start()
            threading.Thread(target=self.cleanup_peers, daemon=True).start()

    def broadcast_presence(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        while self.running:
            # Create our payload, adding a timestamp for Anti-Replay protection
            payload = {
                "type": "PEER",
                "peer_id": self.peer_id,
                "peer_username": self.username,
                "tcp_port": Protocol.TCP_PORT,
                "timestamp": time.time(),  # <--- NEW: Current time
                "files": self.file_manager.get_files_summary()
            }

            # Convert dictionary to JSON string, then to bytes
            json_data = json.dumps(payload).encode()

            # --- 2. ENCRYPT THE BROADCAST ---
            encrypted_data = self.fernet.encrypt(json_data)

            # Send the scrambled bytes over the network
            sock.sendto(encrypted_data, (self.broadcast_ip, self.port))
            time.sleep(self.broadcast_interval)

    def listen_for_peers(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("0.0.0.0", self.port))

        while self.running:
            try:
                encrypted_data, addr = sock.recvfrom(Protocol.BUFFER_SIZE)

                # --- 3. THE BOUNCER (DECRYPTION) ---
                try:
                    # Attempt to decrypt. If the password is wrong or data is corrupted,
                    # this will instantly raise an InvalidToken error.
                    decrypted_data = self.fernet.decrypt(encrypted_data)
                except InvalidToken:
                    # The packet didn't have our password. Silently ignore it.
                    continue

                # If we get here, the decryption succeeded!
                obj = json.loads(decrypted_data.decode())

                # --- 4. ANTI-REPLAY CHECK ---
                packet_time = obj.get("timestamp", 0)
                current_time = time.time()

                # If the packet is older than 10 seconds, it's a replay attack or extreme lag. Drop it.
                if current_time - packet_time > 10:
                    continue

                if obj.get("type") != "PEER" or obj["peer_id"] == self.peer_id:
                    continue

                self.peer_table[obj["peer_id"]] = {
                    "ip": addr[0],
                    "files": obj["files"],
                    "last_seen": current_time  # Use current_time, not packet_time, for accurate timeouts
                }

            except json.JSONDecodeError:
                # Occurs if someone encrypts non-JSON text with our password
                continue
            except Exception as e:
                print("Error processing message:", e)

    def cleanup_peers(self):
        while self.running:
            now = time.time()
            for peer_id, info in list(self.peer_table.items()):
                if now - info["last_seen"] > self.peer_timeout:
                    del self.peer_table[peer_id]
            time.sleep(5)

    def set_network_password(self, new_password, username):
        self.username = username
        """Updates the encryption key and clears old peers from the table."""
        # 1. Generate the new key
        key_hash = hashlib.sha256(new_password.encode()).digest()
        fernet_key = base64.urlsafe_b64encode(key_hash)
        self.fernet = Fernet(fernet_key)

        # 2. CLEAR the peer table immediately
        self.peer_table.clear()
        print(f"[*] Network key updated. Swarm: {new_password}")