import socket
import threading
import os
import json
import time  # <--- NEW
from security import SecureConnection


class TCPServer:
    def __init__(self, file_manager, port=50001):
        self.file_manager = file_manager
        self.port = port
        self.server_socket = None
        self.running = False

        # --- NEW: Upload Tracking ---
        self.active_uploads = {}

    def start(self):
        self.running = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind(('0.0.0.0', self.port))
        self.server_socket.listen(5)
        print(f"TCP Server listening on port {self.port}...")

        threading.Thread(target=self.accept_connections, daemon=True).start()
        # Start the cleanup thread for old uploads
        threading.Thread(target=self.cleanup_uploads, daemon=True).start()

    def accept_connections(self):
        while self.running:
            try:
                client_sock, addr = self.server_socket.accept()
                threading.Thread(target=self.handle_client, args=(client_sock, addr), daemon=True).start()
            except Exception as e:
                if self.running:
                    print(f"Error accepting connection: {e}")

    # Notice we added 'addr' here to get the client IP
    def handle_client(self, conn, addr):
        client_ip = addr[0]
        try:
            secure_conn = SecureConnection(conn, is_client=False)
            secure_conn.handshake()

            request_data = secure_conn.recv_encrypted()
            if not request_data:
                return

            request = json.loads(request_data.decode())
            req_type = request.get("type")
            file_id = request.get("file_id")

            if file_id not in self.file_manager.my_files:
                return

            filename = self.file_manager.my_files[file_id]["filename"]

            if req_type == "METADATA":
                file_data = self.file_manager.my_files[file_id]
                response = json.dumps(file_data).encode()
                secure_conn.send_encrypted(response)
                return

            chunk_index = request.get("chunk_index")
            if chunk_index is not None:
                chunk_data = self.read_chunk(filename, chunk_index)
                if chunk_data:
                    # --- NEW: Speed Calculation ---
                    now = time.time()
                    if client_ip not in self.active_uploads:
                        self.active_uploads[client_ip] = {
                            "filename": filename,
                            "bytes_since_last": 0,
                            "speed": 0,
                            "last_calc_time": now,
                            "last_activity": now
                        }

                    # Update activity and calculate speed if 1 second has passed
                    upload_info = self.active_uploads[client_ip]
                    upload_info["last_activity"] = now
                    upload_info["bytes_since_last"] += len(chunk_data)

                    time_diff = now - upload_info["last_calc_time"]
                    if time_diff >= 1.0:
                        upload_info["speed"] = upload_info["bytes_since_last"] / time_diff
                        upload_info["bytes_since_last"] = 0
                        upload_info["last_calc_time"] = now

                    secure_conn.send_encrypted(chunk_data)

        except Exception as e:
            pass  # Keep terminal clean from random disconnect errors
        finally:
            conn.close()

    def read_chunk(self, filename, chunk_index):
        real_path = os.path.join(self.file_manager.shared_folder, filename)
        chunk_size = self.file_manager.CHUNK_SIZE
        try:
            with open(real_path, 'rb') as f:
                f.seek(chunk_index * chunk_size)
                return f.read(chunk_size)
        except Exception:
            return None

    # --- NEW: Cleanup inactive uploads ---
    def cleanup_uploads(self):
        while self.running:
            now = time.time()
            for ip in list(self.active_uploads.keys()):
                # If they haven't requested a chunk in 3 seconds, they are done
                if now - self.active_uploads[ip]['last_activity'] > 3.0:
                    del self.active_uploads[ip]
            time.sleep(2)