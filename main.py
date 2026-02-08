from shared_files_manager import SharedFilesManager
from peer import Peer
from tcp_server import TCPServer  # <--- NEW
from tcp_client import TCPClient  # <--- NEW
from web_ui import WebUI  # Assuming you have the web_ui file from previous steps

if __name__ == "__main__":
    file_manager = SharedFilesManager()

    # 1. Start the Peer Discovery (UDP)
    peer = Peer(file_manager)
    peer.start()

    # 2. Start the TCP Server (To let others download from me)
    tcp_server = TCPServer(file_manager)
    tcp_server.start()

    # 3. Initialize the Client (To download from others)
    tcp_client = TCPClient(file_manager)

    # 4. Start the Web UI
    # Note: We pass tcp_client so the UI can trigger downloads
    web_ui = WebUI(peer, file_manager, tcp_client)
    web_ui.run()