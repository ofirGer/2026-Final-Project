import socket
import os
import json
import hashlib
import time
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from security import SecureConnection

PACKET_SIZE = 4096
class TCPClient:
    def __init__(self, file_manager, download_folder="downloads"):
        self.file_manager = file_manager
        # We save directly to the shared folder to become a seeder immediately
        self.download_folder = self.file_manager.shared_folder

        # Dictionary to track progress for the UI
        # Format: { "movie.mp4": 45 } (percent)
        self.active_downloads = {}

        # Tracks which downloads should be killed
        self.cancel_flags = {}

        # Max number of threads downloading together
        self.MAX_WORKERS = 5
        self.download_sessions = {}
        if not os.path.exists(self.download_folder):
            os.makedirs(self.download_folder)

    def fetch_metadata(self, ip, port, file_id):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((ip, port))

            # --- 1. HANDSHAKE ---
            secure_conn = SecureConnection(sock, is_client=True)
            secure_conn.handshake()

            # --- 2. ENCRYPT & SEND REQUEST ---
            req = json.dumps({"type": "METADATA", "file_id": file_id})
            secure_conn.send_encrypted(req.encode())

            # --- 3. RECEIVE & DECRYPT METADATA ---
            # No more reading weird 10-byte headers! SecureConnection handles sizes automatically.
            received_data = secure_conn.recv_encrypted()

            sock.close()
            return json.loads(received_data.decode())
        except Exception as e:
            print(f"Error fetching metadata: {e}")
            return None

    def download_file(self, peers_list, file_id, filename, file_metadata, port=50001):
        # --- 1. SESSION MANAGEMENT (KILL GHOST THREADS) ---
        # Generate a unique ID for THIS specific download click.
        # Any old threads will realize their ID is outdated and die.
        session_id = str(uuid.uuid4())
        self.download_sessions[file_id] = session_id
        # --------------------------------------------------

        print(f"Starting SWARM download: {filename} from {len(peers_list)} peers")
        self.active_downloads[file_id] = {"filename": filename, "progress": 0}

        # 2. משיכת מטא-דאטה חסר
        if "checksums" not in file_metadata:
            full_metadata = None
            for ip in peers_list:
                full_metadata = self.fetch_metadata(ip, port, file_id)
                if full_metadata: break

            if not full_metadata:
                print("CRITICAL: Could not fetch metadata. Aborting.")
                del self.active_downloads[file_id]
                return
            checksums = full_metadata["checksums"]
        else:
            checksums = file_metadata["checksums"]

        total_chunks = file_metadata['total_chunks']
        chunk_size = file_metadata['chunk_size']

        # 3. יצירת קובץ ה-.part
        final_path = os.path.join(self.download_folder, filename)
        part_path = final_path + ".part"

        if not os.path.exists(part_path):
            with open(part_path, 'wb') as f:
                f.truncate(file_metadata['size'])

        chunks_to_download = list(range(total_chunks))
        progress_lock = threading.Lock()
        completed_chunks = 0

        def download_worker(chunk_index):
            nonlocal completed_chunks

            # SESSION CHECK: Before starting the network request
            if self.download_sessions.get(file_id) != session_id:
                return

            peer_ip = peers_list[chunk_index % len(peers_list)]

            # <-- Pass session_id to get_chunk
            success = self.get_chunk(peer_ip, port, file_id, chunk_index, chunk_size, checksums[chunk_index], part_path,
                                     session_id)

            if success:
                with progress_lock:
                    # SESSION CHECK: Before updating the UI
                    if self.download_sessions.get(file_id) == session_id:
                        completed_chunks += 1
                        progress_percent = int((completed_chunks / total_chunks) * 100)
                        self.active_downloads[file_id]["progress"] = progress_percent

        # 4. הפעלת מנגנון המקביליות
        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
            executor.map(download_worker, chunks_to_download)

        # --- 5. POST-DOWNLOAD CHECKS (SUCCESS OR FAILURE) ---
        # Make sure the user didn't restart the download while we were analyzing
        if self.download_sessions.get(file_id) == session_id:

            if completed_chunks == total_chunks:
                # SUCCESS!
                if os.path.exists(part_path):
                    os.rename(part_path, final_path)
                print(f"Swarm download complete! Now seeding {filename}")
                self.active_downloads[file_id]["progress"] = 100
                self.file_manager.load_shared_files()
            else:
                # FAILED / DISCONNECTED!
                print(f"Download FAILED or INCOMPLETE for {filename}. Missing chunks.")
                self.active_downloads[file_id]["progress"] = "Failed"

            # Show the 100% or Failed state for 5 seconds, then clear it
            time.sleep(5)
            if self.download_sessions.get(file_id) == session_id:
                if file_id in self.active_downloads:
                    del self.active_downloads[file_id]
                del self.download_sessions[file_id]

    def get_chunk(self, ip, port, file_id, chunk_index, chunk_size, expected_hash, save_path, session_id):
        # --- 0. SESSION CHECK (Kill Switch) ---
        if self.download_sessions.get(file_id) != session_id:
            return False

            # --- 1. RESUME FEATURE: Check local disk first ---
        try:
            if os.path.exists(save_path):
                with open(save_path, 'rb') as f:
                    f.seek(chunk_index * chunk_size)
                    local_data = f.read(chunk_size)

                    if local_data:
                        sha256 = hashlib.sha256()
                        sha256.update(local_data)
                        if sha256.hexdigest() == expected_hash:
                            return True
        except Exception as e:
            pass

            # --- 2. NETWORK DOWNLOAD ---
        try:
            # Check session again right before blocking on network
            if self.download_sessions.get(file_id) != session_id:
                return False

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((ip, port))

            secure_conn = SecureConnection(sock, is_client=True)
            secure_conn.handshake()

            request = json.dumps({"type": "CHUNK", "file_id": file_id, "chunk_index": chunk_index})
            secure_conn.send_encrypted(request.encode())

            received_data = secure_conn.recv_encrypted()
            sock.close()

            # --- 3. VERIFY AND SAVE NEW DOWNLOAD ---
            sha256 = hashlib.sha256()
            sha256.update(received_data)

            if sha256.hexdigest() == expected_hash:
                if not os.path.exists(save_path):
                    open(save_path, 'wb').close()

                with open(save_path, 'r+b') as f:
                    f.seek(chunk_index * chunk_size)
                    f.write(received_data)
                return True
            else:
                print(f"HASH MISMATCH for chunk {chunk_index} from {ip}")
                return False

        except Exception as e:
            # User disconnected, timeout, etc. We just fail quietly.
            return False