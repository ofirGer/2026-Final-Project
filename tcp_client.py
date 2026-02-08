import socket
import os
import json
import hashlib
import time


class TCPClient:
    def __init__(self, file_manager, download_folder="downloads"):
        self.file_manager = file_manager
        self.download_folder = download_folder

        # New: Dictionary to track progress for the UI
        # Format: { "movie.mp4": 45 (percent) }
        self.active_downloads = {}

        if not os.path.exists(self.download_folder):
            os.makedirs(self.download_folder)

    def download_file(self, target_ip, filename, file_metadata, port=50001):
        print(f"Starting download: {filename}")

        total_chunks = file_metadata['total_chunks']
        chunk_size = file_metadata['chunk_size']
        checksums = file_metadata['checksums']

        # 1. Initialize progress
        self.active_downloads[filename] = 0

        save_path = os.path.join(self.file_manager.shared_folder, filename)

        with open(save_path, 'wb') as f:
            f.truncate(file_metadata['size'])

        for i in range(total_chunks):
            self.get_chunk(target_ip, port, filename, i, chunk_size, checksums[i], save_path)

            # 2. Update progress
            progress_percent = int(((i + 1) / total_chunks) * 100)
            self.active_downloads[filename] = progress_percent

        print(f"Download complete: {filename}")

        # 3. Mark as complete (100%) and refresh shared files
        self.active_downloads[filename] = 100
        self.file_manager.load_shared_files()

        # Optional: Remove from list after 5 seconds so the user sees "100%" for a bit
        time.sleep(5)
        if filename in self.active_downloads:
            del self.active_downloads[filename]

    def get_chunk(self, ip, port, filename, chunk_index, chunk_size, expected_hash, save_path):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((ip, port))

            request = json.dumps({"filename": filename, "chunk_index": chunk_index})
            sock.sendall(request.encode())

            received_data = b""
            while len(received_data) < chunk_size:
                packet = sock.recv(4096)
                if not packet:
                    break
                received_data += packet

            sock.close()

            # Verify Hash
            sha256 = hashlib.sha256()
            sha256.update(received_data)
            if sha256.hexdigest() == expected_hash:
                with open(save_path, 'r+b') as f:
                    f.seek(chunk_index * chunk_size)
                    f.write(received_data)
            else:
                print(f"HASH MISMATCH for chunk {chunk_index}")

        except Exception as e:
            print(f"Error downloading chunk {chunk_index}: {e}")