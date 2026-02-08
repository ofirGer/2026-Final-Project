import socket
import os
import json
import hashlib


class TCPClient:
    def __init__(self, download_folder="downloads"):
        self.download_folder = download_folder
        if not os.path.exists(self.download_folder):
            os.makedirs(self.download_folder)

    def download_file(self, target_ip, filename, file_metadata, port=50001):
        print(f"Starting download: {filename} from {target_ip}")

        total_chunks = file_metadata['total_chunks']
        chunk_size = file_metadata['chunk_size']
        checksums = file_metadata['checksums']

        save_path = os.path.join(self.download_folder, filename)

        # Create/Open the file in binary write mode
        # 'wb' overwrites the file. In the future, we will use 'r+b' to resume.
        with open(save_path, 'wb') as f:
            # We just create an empty file of the right size first (optional but good practice)
            f.truncate(file_metadata['size'])

        for i in range(total_chunks):
            self.get_chunk(target_ip, port, filename, i, chunk_size, checksums[i], save_path)

        print(f"Download complete: {filename}")

    def get_chunk(self, ip, port, filename, chunk_index, chunk_size, expected_hash, save_path):
        try:
            # 1. Connect to the peer
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((ip, port))

            # 2. Send Request
            request = json.dumps({"filename": filename, "chunk_index": chunk_index})
            sock.sendall(request.encode())

            # 3. Receive Data (might come in small packets, so we loop)
            received_data = b""
            while len(received_data) < chunk_size:
                packet = sock.recv(4096)
                if not packet:
                    break
                received_data += packet

            sock.close()

            # 4. Verify Hash (Security Check)
            # Handle edge case: last chunk might be smaller than chunk_size
            sha256 = hashlib.sha256()
            sha256.update(received_data)
            calculated_hash = sha256.hexdigest()

            if calculated_hash == expected_hash:
                # 5. Write to disk at the correct location
                with open(save_path, 'r+b') as f:
                    f.seek(chunk_index * chunk_size)
                    f.write(received_data)
                print(f"Chunk {chunk_index} verified and written.")
            else:
                print(f"HASH MISMATCH for chunk {chunk_index}! Retrying... (Logic to be added)")

        except Exception as e:
            print(f"Error downloading chunk {chunk_index}: {e}")