import json
import sys
from tkinter import Tk
from tkinter.filedialog import askopenfilename


class CommandHandler:
    def __init__(self, peer, file_manager):
        self.peer = peer
        self.file_manager = file_manager
        self.running = True

    def open_file_dialog(self):
        root = Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        file_path = askopenfilename(
            title="Select a file to share"
        )

        root.destroy()
        return file_path

    def start(self):
        while self.running:
            cmd = input(
                "Command (t=peers, f=files, add, remove, exit): "
            ).strip()

            if cmd == "t":
                print(json.dumps(self.peer.peer_table, indent=4))

            elif cmd == "f":
                print(json.dumps(self.file_manager.my_files, indent=4))

            elif cmd == "add":
                file_path = self.open_file_dialog()
                if file_path:
                    self.file_manager.add_file(file_path)
                else:
                    print("No file selected")

            elif cmd == "remove":
                files = list(self.file_manager.my_files.keys())

                if not files:
                    print("No shared files to remove")
                    continue

                print("Shared files:")
                for i, name in enumerate(files):
                    print(f"{i}: {name}")

                try:
                    index = int(input("Select file number to remove: "))
                    filename = files[index]
                    self.file_manager.remove_file(filename)
                except (ValueError, IndexError):
                    print("Invalid selection")

            elif cmd == "exit":
                print("Exiting...")
                self.running = False
                sys.exit(0)

            else:
                print("Unknown command")
