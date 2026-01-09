from shared_files_manager import SharedFilesManager
from peer import Peer
from command_handler import CommandHandler

if __name__ == "__main__":
    file_manager = SharedFilesManager()
    peer = Peer(file_manager)
    cli = CommandHandler(peer, file_manager)

    peer.start()
    cli.start()
