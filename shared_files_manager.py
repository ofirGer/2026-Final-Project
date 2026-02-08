import os
import shutil
import hashlib  # <--- NEW: Needed for calculating the "fingerprints"
import math


class SharedFilesManager:
    # 64KB is a standard chunk size for small-medium files
    CHUNK_SIZE = 65536

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
                # <--- CHANGED: We now call a smart function instead of just getting size
                self.my_files[filename] = self.analyze_file(path)

        print("Loaded shared files with chunks:")
        # We print just the keys to avoid spamming the console with huge hash lists


    def analyze_file(self, path):
        """
        Reads the file in chunks and calculates SHA-256 hashes.
        Returns a dictionary with all file metadata.
        """
        file_size = os.path.getsize(path)
        hashes = []

        try:
            with open(path, 'rb') as f:
                while True:
                    # Read exactly one chunk
                    chunk = f.read(self.CHUNK_SIZE)
                    if not chunk:
                        break  # End of file

                    # Calculate hash for this specific chunk
                    sha256 = hashlib.sha256()
                    sha256.update(chunk)
                    hashes.append(sha256.hexdigest())

            return {
                "size": file_size,
                "chunk_size": self.CHUNK_SIZE,
                "total_chunks": len(hashes),
                "checksums": hashes  # The list of fingerprints
            }
        except Exception as e:
            print(f"Error analyzing file {path}: {e}")
            return {}

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
            print("File not shared")
            return

        try:
            os.remove(path)
            del self.my_files[filename]
            print(f"Removed file: {filename}")
        except OSError as e:
            print(f"Error deleting file: {e}")

    def get_files_summary(self):
        """
        Returns a lightweight version of my_files without the huge 'checksums' list.
        Used for UDP broadcasting.
        """
        summary = {}
        for filename, data in self.my_files.items():
            summary[filename] = {
                "size": data["size"],
                "chunk_size": data["chunk_size"],
                "total_chunks": data["total_chunks"]
                # NOTE: We intentionally EXCLUDE "checksums" here
            }
        return summary