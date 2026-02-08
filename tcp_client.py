import socket
import os
import json
import hashlib
import time


class TCPClient:
    def __init__(self, file_manager, download_folder="downloads"):
        self.file_manager = file_manager
        # We save directly to the shared folder to become a seeder immediately
        self.download_folder = self.file_manager.shared_folder

        # Dictionary to track progress for the UI
        # Format: { "movie.mp4": 45 } (percent)
        self.active_downloads = {}

        if not os.path.exists(self.download_folder):
            os.makedirs(self.download_folder)

    def fetch_metadata(self, ip, port, filename):
        """
        Connects to a peer via TCP to get the full file metadata (including hashes).
        This is necessary because the UDP broadcast only sends a summary.
        """
        try:
            print(f"Fetching metadata for {filename} from {ip}...")
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)  # 5 second timeout
            sock.connect((ip, port))

            # Request Metadata
            req = json.dumps({"type": "METADATA", "filename": filename})
            sock.sendall(req.encode())

            # Read the length header (first 10 bytes)
            header = sock.recv(10).decode().strip()
            if not header:
                return None

            data_len = int(header)

            # Read the full JSON body
            received_data = b""
            while len(received_data) < data_len:
                packet = sock.recv(4096)
                if not packet: break
                received_data += packet

            sock.close()
            return json.loads(received_data)
        except Exception as e:
            print(f"Error fetching metadata: {e}")
            return None

    def download_file(self, target_ip, filename, file_metadata, port=50001):
        print(f"Starting download: {filename} from {target_ip}")

        # 1. Initialize progress
        self.active_downloads[filename] = 0

        # 2. Get the full metadata (We need the hashes!)
        if "checksums" not in file_metadata:
            full_metadata = self.fetch_metadata(target_ip, port, filename)
            if not full_metadata:
                print("CRITICAL: Could not fetch metadata. Aborting download.")
                del self.active_downloads[filename]
                return
            checksums = full_metadata["checksums"]
        else:
            checksums = file_metadata["checksums"]

        total_chunks = file_metadata['total_chunks']
        chunk_size = file_metadata['chunk_size']

        save_path = os.path.join(self.download_folder, filename)

        # 3. Create the file structure
        with open(save_path, 'wb') as f:
            f.truncate(file_metadata['size'])

        # 4. Download Loop
        for i in range(total_chunks):
            success = self.get_chunk(target_ip, port, filename, i, chunk_size, checksums[i], save_path)
            if not success:
                print(f"Failed to download chunk {i}. Aborting.")
                break

            # Update progress
            progress_percent = int(((i + 1) / total_chunks) * 100)
            self.active_downloads[filename] = progress_percent

        print(f"Download complete: {filename}")

        # 5. Finalize
        self.active_downloads[filename] = 100
        self.file_manager.load_shared_files()  # Refresh so we start seeding

        # Keep the 100% bar for a few seconds then clear it
        time.sleep(5)
        if filename in self.active_downloads:
            del self.active_downloads[filename]

    def get_chunk(self, ip, port, filename, chunk_index, chunk_size, expected_hash, save_path):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((ip, port))

            # Standard Chunk Request
            request = json.dumps({"type": "CHUNK", "filename": filename, "chunk_index": chunk_index})
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
                return True
            else:
                print(f"HASH MISMATCH for chunk {chunk_index}")
                return False

        except Exception as e:
            print(f"Error downloading chunk {chunk_index}: {e}")
            return False