import socket
import os
import json
import hashlib
import time
import threading
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
        """
        peers_list: רשימה של כתובות IP של כל מי שיש לו את הקובץ (למשל ['192.168.1.5', '192.168.1.9'])
        """
        # --- 1. KILL GHOST THREADS ---
        # If the user clicks download again, kill the old threads before starting new ones
        if file_id in self.active_downloads:
            print(f"Killing old download threads for {filename} before restarting...")
            self.cancel_flags[file_id] = True
            time.sleep(1)  # Give the old threads 1 second to see the flag and die

        self.cancel_flags[file_id] = False  # Reset flag for the new threads
        # -----------------------------

        print(f"Starting SWARM download: {filename} from {len(peers_list)} peers")
        self.active_downloads[file_id] = {"filename": filename, "progress": 0}

        # 2. משיכת מטא-דאטה חסר (Hashes) מאחד העמיתים
        if "checksums" not in file_metadata:
            full_metadata = None
            for ip in peers_list:
                full_metadata = self.fetch_metadata(ip, port, file_id)  # <-- Pass file_id
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

        # --- 3. THE .PART PATH LOGIC ---
        final_path = os.path.join(self.download_folder, filename)
        part_path = final_path + ".part"

        # We create the empty file using the .part extension
        with open(part_path, 'wb') as f:
            f.truncate(file_metadata['size'])
        # -------------------------------

        chunks_to_download = list(range(total_chunks))
        progress_lock = threading.Lock()
        completed_chunks = 0

        # A function inside download_file, enables it to use the download_file variables
        # Has a single use inside download_file
        def download_worker(chunk_index):
            # Do not create a new local variable called completed_chunks. Use the one from the parent function outside.
            nonlocal completed_chunks
            peer_ip = peers_list[chunk_index % len(peers_list)]

            # <-- Pass file_id and part_path to get_chunk
            success = self.get_chunk(peer_ip, port, file_id, chunk_index, chunk_size, checksums[chunk_index], part_path)

            if success:
                with progress_lock:
                    completed_chunks += 1
                    progress_percent = int((completed_chunks / total_chunks) * 100)
                    self.active_downloads[file_id]["progress"] = progress_percent

        # 4. הפעלת מנגנון המקביליות
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
            executor.map(download_worker, chunks_to_download)

        # --- 5. ONCE DOWNLOAD IS 100% FINISHED ---
        # Rename .part to the real filename
        if os.path.exists(part_path):
            os.rename(part_path, final_path)

        print(f"Swarm download complete! Now seeding {filename}")
        self.active_downloads[file_id]["progress"] = 100

        # Tell the file manager to scan the folder so it sees the new, finished file
        self.file_manager.load_shared_files()

        time.sleep(5)
        if file_id in self.active_downloads:
            del self.active_downloads[file_id]
    def get_chunk(self, ip, port, file_id, chunk_index, chunk_size, expected_hash, save_path):
        if self.cancel_flags.get(file_id, False):
            return False  # Abort thread immediately!
        # --- 1. RESUME FEATURE: Check local disk first ---
        try:
            if os.path.exists(save_path):
                with open(save_path, 'rb') as f:
                    # Jump to the correct byte offset for this chunk
                    f.seek(chunk_index * chunk_size)
                    local_data = f.read(chunk_size)

                    # If we actually read data, check if it's the completed chunk
                    if local_data:
                        sha256 = hashlib.sha256()
                        sha256.update(local_data)
                        if sha256.hexdigest() == expected_hash:
                            # We already have this chunk! Skip the download.
                            return True
        except Exception as e:
            # If there's an error reading (e.g., file doesn't exist yet), just proceed to download
            pass
            # -------------------------------------------------

        # --- 2. NETWORK DOWNLOAD (If chunk is missing or incomplete) ---
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((ip, port))

            # Initialize Hybrid Encryption Handshake
            secure_conn = SecureConnection(sock, is_client=True)
            secure_conn.handshake()

            # Encrypt & Send Request
            request = json.dumps({"type": "CHUNK", "file_id": file_id, "chunk_index": chunk_index})
            secure_conn.send_encrypted(request.encode())

            # Receive & Decrypt Chunk
            received_data = secure_conn.recv_encrypted()
            sock.close()

            # --- 3. VERIFY AND SAVE NEW DOWNLOAD ---
            sha256 = hashlib.sha256()
            sha256.update(received_data)

            if sha256.hexdigest() == expected_hash:
                # Safety check: ensure file exists before we try to open in r+b (read/write binary) mode
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
            # Silently fail, the ThreadPool will retry if needed
            return False