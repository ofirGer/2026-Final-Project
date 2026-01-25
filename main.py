from shared_files_manager import SharedFilesManager
from peer import Peer
from tcp_client import TCPClient
from web_ui import WebUI  # <-- Add this

if __name__ == "__main__":
    file_manager = SharedFilesManager()
    peer = Peer(file_manager)
    tcp_client = TCPClient(file_manager)

    # Initialize the Website instead of the CLI
    ui = WebUI(peer, file_manager, tcp_client)

    # Start the Peer networking threads
    peer.start()

    # Start the Web Server (This will block the main thread, which is fine)
    print("🚀 Website running at http://localhost:8000")
    ui.run()