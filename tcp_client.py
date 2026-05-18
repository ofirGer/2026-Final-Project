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
        self.download_folder = self.file_manager.shared_folder
        self.active_downloads = {}

        self.download_sessions = {}
        self.cancel_flags = {}  # <--- Fast Abort Switch

        self.MAX_WORKERS = 5

        if not os.path.exists(self.download_folder):
            os.makedirs(self.download_folder)

    def fetch_metadata(self, ip, port, file_id):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((ip, port))

            secure_conn = SecureConnection(sock, is_client=True)
            secure_conn.handshake()

            req = json.dumps({"type": "METADATA", "file_id": file_id})
            secure_conn.send_encrypted(req.encode())

            received_data = secure_conn.recv_encrypted()
            sock.close()
            return json.loads(received_data.decode())
        except Exception as e:
            print(f"Error fetching metadata: {e}")
            return None

    def download_file(self, peers_list, file_id, filename, file_metadata, port=50001):
        session_id = str(uuid.uuid4())
        self.download_sessions[file_id] = session_id

        # Reset the abort switch for this file
        self.cancel_flags[file_id] = False

        print(f"Starting SWARM download: {filename} from {len(peers_list)} peers")
        # Initialize speed to 0 when starting
        self.active_downloads[file_id] = {"filename": filename, "progress": 0, "speed": 0}

        if "checksums" not in file_metadata:
            full_metadata = None
            for ip in peers_list:
                full_metadata = self.fetch_metadata(ip, port, file_id)
                if full_metadata: break

            if not full_metadata:
                del self.active_downloads[file_id]
                return
            checksums = full_metadata["checksums"]
        else:
            checksums = file_metadata["checksums"]

        total_chunks = file_metadata['total_chunks']
        chunk_size = file_metadata['chunk_size']

        final_path = os.path.join(self.download_folder, filename)
        part_path = final_path + ".part"

        if not os.path.exists(part_path):
            with open(part_path, 'wb') as f:
                f.truncate(file_metadata['size'])

        chunks_to_download = list(range(total_chunks))
        progress_lock = threading.Lock()
        completed_chunks = 0

        # --- SPEED TRACKING VARIABLES ---
        last_speed_calc_time = time.time()
        bytes_downloaded_since_last = 0

        def download_worker(chunk_index):
            nonlocal completed_chunks, last_speed_calc_time, bytes_downloaded_since_last

            # FAST ABORT: If network failed on another thread, don't even try.
            if self.cancel_flags.get(file_id, False) or self.download_sessions.get(file_id) != session_id:
                return

            peer_ip = peers_list[chunk_index % len(peers_list)]
            success = self.get_chunk(peer_ip, port, file_id, chunk_index, chunk_size, checksums[chunk_index], part_path,
                                     session_id)

            if success:
                # Use the lock to prevent thread race conditions when updating progress and speed
                with progress_lock:
                    if self.download_sessions.get(file_id) == session_id:
                        # Update Progress
                        completed_chunks += 1
                        progress_percent = int((completed_chunks / total_chunks) * 100)
                        self.active_downloads[file_id]["progress"] = progress_percent

                        # --- CALCULATE SPEED ---
                        bytes_downloaded_since_last += chunk_size
                        now = time.time()
                        time_diff = now - last_speed_calc_time

                        # Update the speed stat every 1 second
                        if time_diff >= 1.0:
                            speed = bytes_downloaded_since_last / time_diff
                            self.active_downloads[file_id]['speed'] = speed

                            # Reset the trackers for the next second
                            bytes_downloaded_since_last = 0
                            last_speed_calc_time = now

        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
            executor.map(download_worker, chunks_to_download)

        # POST-DOWNLOAD CHECK
        if self.download_sessions.get(file_id) == session_id:
            if completed_chunks == total_chunks:
                if os.path.exists(part_path):
                    os.rename(part_path, final_path)
                self.active_downloads[file_id]["progress"] = 100
                self.active_downloads[file_id]["speed"] = 0  # Reset speed on completion
                self.file_manager.load_shared_files()
            else:
                print(f"Download FAILED for {filename}. Peer likely disconnected.")
                self.active_downloads[file_id]["progress"] = "Failed"
                self.active_downloads[file_id]["speed"] = 0

            time.sleep(5)
            if self.download_sessions.get(file_id) == session_id:
                if file_id in self.active_downloads:
                    del self.active_downloads[file_id]
                del self.download_sessions[file_id]

    def get_chunk(self, ip, port, file_id, chunk_index, chunk_size, expected_hash, save_path, session_id):
        # Check Abort Switches
        if self.cancel_flags.get(file_id, False) or self.download_sessions.get(file_id) != session_id:
            return False

        # 1. RESUME FEATURE
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

        # 2. NETWORK DOWNLOAD
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)  # Reduced to 3 seconds so we fail faster
            sock.connect((ip, port))

            secure_conn = SecureConnection(sock, is_client=True)
            secure_conn.handshake()

            request = json.dumps({"type": "CHUNK", "file_id": file_id, "chunk_index": chunk_index})
            secure_conn.send_encrypted(request.encode())

            received_data = secure_conn.recv_encrypted()
            sock.close()

            # 3. VERIFY
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
                return False

        except Exception as e:
            # --- THE MAGIC FIX ---
            # If the network connection fails, flip the abort switch instantly!
            self.cancel_flags[file_id] = True
            return False