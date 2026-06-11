import socket
import threading
import time
import json
import uuid
import hashlib
import base64
from cryptography.fernet import Fernet, InvalidToken
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

        # --- Credentials are NOT set yet ---
        # The username and the Fernet key are supplied later via start(),
        # after the user enters them in the lobby. Until then,
        # UDP discovery stays dormant (no broadcasting, no listening).
        self.username = None
        self.fernet = None

        # Background threads launch only on the first call to start().
        self.running = False
        self._threads_started = False

    def start(self, username, network_password):
        """Activate (or refresh) UDP discovery with the given credentials.

        First call: derives the Fernet key from the password, stores the
        username, and launches the three background threads
        (broadcast_presence, listen_for_peers, cleanup_peers).

        Subsequent calls (e.g., after the user logs out and joins another
        swarm): updates the username and key, and clears the peer table.
        The background threads keep running with the new credentials.
        """
        # --- 1. KEY DERIVATION LOGIC ---
        # We take the human-readable password and hash it using SHA-256.
        # This guarantees we get exactly 32 bytes of seemingly random data.
        key_hash = hashlib.sha256(network_password.encode()).digest()

        # Fernet requires the 32-byte key to be url-safe base64 encoded.
        fernet_key = base64.urlsafe_b64encode(key_hash)

        # Store the user identity and create our Symmetric Encryption tool.
        self.username = username
        self.fernet = Fernet(fernet_key)

        # Old peers may belong to a different swarm — clear them out.
        self.peer_table.clear()
        print(f"[*] Joined swarm. User: {username}, Swarm Password: {network_password}")

        # Launch background threads only the first time start() is called.
        if not self._threads_started:
            self._threads_started = True
            self.running = True
            threading.Thread(target=self.broadcast_presence, daemon=True).start()
            threading.Thread(target=self.listen_for_peers, daemon=True).start()
            threading.Thread(target=self.cleanup_peers, daemon=True).start()

    def stop(self):
        """Pause UDP discovery (called on Logout).

        The background threads stay alive, but every iteration of the
        broadcast/listen loops sees `fernet is None` and skips its work.
        The peer_table is cleared so the dashboard shows nothing while
        logged out. A future start() call seamlessly resumes activity.
        """
        self.username = None
        self.fernet = None
        self.peer_table.clear()
        print("[*] Logged out — UDP discovery paused.")

    def broadcast_presence(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        while self.running:
            # --- PAUSE GATE ---
            # If the user is logged out (or hasn't logged in yet), there's
            # no Fernet key and no username — skip this iteration.
            # We poll every 0.5s so the moment start() is called again,
            # broadcasting resumes almost immediately.
            if self.fernet is None or self.username is None:
                time.sleep(0.5)
                continue

            # Create our payload, adding a timestamp for Anti-Replay protection.
            # The username is now part of the payload so other peers know
            # who's behind each peer_id.
            payload = {
                "type": "PEER",
                "peer_id": self.peer_id,
                "username": self.username,
                "tcp_port": Protocol.TCP_PORT,
                "timestamp": time.time(),
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

                # --- PAUSE GATE ---
                # If logged out, we still drain incoming packets (so the OS
                # socket buffer doesn't fill up), but we don't process them.
                if self.fernet is None:
                    continue

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
                    "username": obj.get("username", "Unknown"),
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