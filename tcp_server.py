import socket
import threading
import os
import json


class TCPServer:
    def __init__(self, file_manager, port=50001):
        self.file_manager = file_manager
        self.port = port
        self.server_socket = None
        self.running = False

    def start(self):
        self.running = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind(('0.0.0.0', self.port))
        self.server_socket.listen(5)
        print(f"TCP Server listening on port {self.port}...")

        threading.Thread(target=self.accept_connections, daemon=True).start()

    def accept_connections(self):
        while self.running:
            try:
                client_sock, addr = self.server_socket.accept()
                threading.Thread(target=self.handle_client, args=(client_sock,), daemon=True).start()
            except Exception as e:
                if self.running:
                    print(f"Error accepting connection: {e}")

    def handle_client(self, conn):
        try:
            # 1. Receive the request (e.g., '{"filename": "test.txt", "chunk_index": 0}')
            data = conn.recv(1024).decode()
            if not data:
                return

            request = json.loads(data)
            filename = request.get("filename")
            chunk_index = request.get("chunk_index")

            # 2. Validate
            if filename not in self.file_manager.my_files:
                print(f"Requested file {filename} not found.")
                conn.close()
                return

            # 3. Read the specific chunk
            chunk_data = self.read_chunk(filename, chunk_index)

            # 4. Send the data back
            if chunk_data:
                conn.sendall(chunk_data)
                print(f"Sent chunk {chunk_index} of {filename} to client")
            else:
                print("Error reading chunk")

        except Exception as e:
            print(f"Error handling client: {e}")
        finally:
            conn.close()

    def read_chunk(self, filename, chunk_index):
        # We need the real path on the disk
        real_path = os.path.join(self.file_manager.shared_folder, filename)
        chunk_size = self.file_manager.CHUNK_SIZE

        try:
            with open(real_path, 'rb') as f:
                # JUMP to the specific part of the file
                f.seek(chunk_index * chunk_size)
                # Read only one chunk
                data = f.read(chunk_size)
                return data
        except Exception as e:
            print(f"File read error: {e}")
            return None