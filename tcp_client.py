import socket
import os
import json
import hashlib


class TCPClient:
    def __init__(self, file_manager):
        # We now link the client to the file manager
        self.file_manager = file_manager

    def download_file(self, target_ip, filename, file_metadata, port=50001):
        print(f"Starting download: {filename} from {target_ip}")

        total_chunks = file_metadata['total_chunks']
        chunk_size = file_metadata['chunk_size']
        checksums = file_metadata['checksums']

        # <--- CHANGE: Save directly to the shared folder
        save_path = os.path.join(self.file_manager.shared_folder, filename)

        # Create/Open the file
        with open(save_path, 'wb') as f:
            f.truncate(file_metadata['size'])

        for i in range(total_chunks):
            self.get_chunk(target_ip, port, filename, i, chunk_size, checksums[i], save_path)

        print(f"Download complete: {filename}")

        # <--- NEW: Tell the manager to scan the folder again so the new file appears immediately
        self.file_manager.load_shared_files()

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

            sha256 = hashlib.sha256()
            sha256.update(received_data)
            calculated_hash = sha256.hexdigest()

            if calculated_hash == expected_hash:
                with open(save_path, 'r+b') as f:
                    f.seek(chunk_index * chunk_size)
                    f.write(received_data)
                print(f"Chunk {chunk_index} verified.")
            else:
                print(f"HASH MISMATCH for chunk {chunk_index}!")

        except Exception as e:
            print(f"Error downloading chunk {chunk_index}: {e}")