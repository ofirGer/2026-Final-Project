import socket
import os
from protocol import Protocol


class TCPClient:
    def __init__(self, file_manager):
        self.file_manager = file_manager

    def download_file(self, target_ip, filename):
        print(f"Attempting to download {filename} from {target_ip}...")

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)  # Good practice: don't hang forever
            sock.connect((target_ip, Protocol.TCP_PORT))

            # 1. Send Request
            sock.send(Protocol.prepare_request(filename))

            # 2. Receive Header
            header_data = sock.recv(1024)
            cmd, content = Protocol.parse_message(header_data)

            if cmd == Protocol.CMD_EXISTS:
                filesize = int(content)
                print(f"File found ({filesize} bytes). Downloading...")

                sock.send(Protocol.CMD_OK.encode())  # ACK

                # 3. Receive Data
                save_path = self.file_manager.get_download_path(filename)
                received = 0

                with open(save_path, "wb") as f:
                    while received < filesize:
                        chunk = sock.recv(Protocol.BUFFER_SIZE)
                        if not chunk: break
                        f.write(chunk)
                        received += len(chunk)

                print(f"Download complete: {filename}")
                self.file_manager.load_shared_files()  # Refresh to share it back

            elif cmd == Protocol.CMD_ERROR:
                print(f"Server Error: {content}")
            else:
                print(f"Unknown response: {cmd}")

            sock.close()
        except Exception as e:
            print(f"Download error: {e}")