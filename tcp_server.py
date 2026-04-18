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

        # Inside tcp_server.py -> handle_client method

        # Inside tcp_server.py -> handle_client method
    def handle_client(self, conn):
        try:
            data = conn.recv(1024).decode()
            if not data: return

            request = json.loads(data)
            req_type = request.get("type")
            file_id = request.get("file_id")  # <--- CHANGED: Ask by ID

            # Validate the file exists
            if file_id not in self.file_manager.my_files:
                return

            filename = self.file_manager.my_files[file_id]["filename"]

            if req_type == "METADATA":
                file_data = self.file_manager.my_files[file_id]  # <--- CHANGED
                response = json.dumps(file_data).encode()
                conn.sendall(f"{len(response):<10}".encode())
                conn.sendall(response)
                return

            chunk_index = request.get("chunk_index")
            if chunk_index is not None:
                chunk_data = self.read_chunk(filename, chunk_index)  # Still read physical file by name
                if chunk_data:
                    conn.sendall(chunk_data)

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