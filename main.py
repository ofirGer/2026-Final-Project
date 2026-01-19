from shared_files_manager import SharedFilesManager
from peer import Peer
from command_handler import CommandHandler
from tcp_client import TCPClient

if __name__ == "__main__":
    file_manager = SharedFilesManager()
    peer = Peer(file_manager)
    tcp_client = TCPClient(file_manager)

    # Pass tcp_client to the command handler
    cli = CommandHandler(peer, file_manager, tcp_client)

    peer.start()
    cli.start()