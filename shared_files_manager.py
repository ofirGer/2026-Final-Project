import os
import shutil


class SharedFilesManager:
    def __init__(self, shared_folder="shared"):
        self.shared_folder = shared_folder
        self.my_files = {}
        self.load_shared_files()

    def load_shared_files(self):
        self.my_files.clear()

        if not os.path.isdir(self.shared_folder):
            print("Shared folder does not exist, creating it...")
            os.makedirs(self.shared_folder)

        for filename in os.listdir(self.shared_folder):
            path = os.path.join(self.shared_folder, filename)
            if os.path.isfile(path):
                self.my_files[filename] = {
                    "size": os.path.getsize(path)
                }

        print("Loaded shared files:")
        print(self.my_files)

    def add_file(self, source_path):
        if not os.path.isfile(source_path):
            print("Invalid file path")
            return

        filename = os.path.basename(source_path)
        destination = os.path.join(self.shared_folder, filename)

        shutil.copy(source_path, destination)
        print(f"Added file: {filename}")

        self.load_shared_files()

    def remove_file(self, filename):
        path = os.path.join(self.shared_folder, filename)

        if filename not in self.my_files:
            print("File not found in shared files")
            return

        try:
            os.remove(path)
            del self.my_files[filename]
            print(f"Removed file: {filename}")
        except Exception as e:
            print("Failed to remove file:", e)
