from shared_files_manager import SharedFilesManager
from peer import Peer
from tcp_server import TCPServer  # <--- NEW
from tcp_client import TCPClient  # <--- NEW
from web_ui import WebUI  # Assuming you have the web_ui file from previous steps

def main():
    file_manager = SharedFilesManager()

    # 1. Create the Peer object (UDP Discovery).
    # NOTE: We do NOT call peer.start() here. UDP broadcasting and listening
    # stay dormant until the user enters their username and swarm key in the
    # lobby — that's when WebUI calls peer.start(username, swarm_key).
    peer = Peer(file_manager, broadcast_ip="192.168.1.255")

    # 2. Start the TCP Server (To let others download from me)
    tcp_server = TCPServer(file_manager)
    tcp_server.start()

    # 3. Initialize the Client (To download from others)
    tcp_client = TCPClient(file_manager)

    # 4. Start the Web UI
    # The WebUI will activate peer.start(...) once the user fills the lobby.
    web_ui = WebUI(peer, file_manager, tcp_client, tcp_server)
    web_ui.run()

if __name__ == "__main__":
    main()