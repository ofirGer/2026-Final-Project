import os
import shutil
import hashlib


class SharedFilesManager:
    CHUNK_SIZE = 65536

    def __init__(self, shared_folder="shared"):
        self.shared_folder = shared_folder
        self.my_files = {}  # Key: file_id (hash), Value: metadata dictionary
        self.load_shared_files()

    def load_shared_files(self):
        self.my_files.clear()

        if not os.path.isdir(self.shared_folder):
            print("Shared folder does not exist, creating it...")
            os.makedirs(self.shared_folder)

        for filename in os.listdir(self.shared_folder):
            path = os.path.join(self.shared_folder, filename)
            if os.path.isfile(path):
                file_id, metadata = self.analyze_file(path)
                if file_id:
                    self.my_files[file_id] = metadata

        print("Loaded shared files IDs:")
        print(list(self.my_files.keys()))

    def analyze_file(self, path):
        file_size = os.path.getsize(path)
        hashes = []
        filename = os.path.basename(path)

        try:
            with open(path, 'rb') as f:
                while True:
                    chunk = f.read(self.CHUNK_SIZE)
                    if not chunk:
                        break

                    sha256 = hashlib.sha256()
                    sha256.update(chunk)
                    hashes.append(sha256.hexdigest())

            # --- NEW: Calculate the Master "Info Hash" (file_id) ---
            # We hash all the smaller hashes together to create one unique ID
            master_hash = hashlib.sha256("".join(hashes).encode()).hexdigest()

            metadata = {
                "filename": filename,  # Keep the name for humans to read
                "size": file_size,
                "chunk_size": self.CHUNK_SIZE,
                "total_chunks": len(hashes),
                "checksums": hashes
            }
            return master_hash, metadata

        except Exception as e:
            print(f"Error analyzing file {path}: {e}")
            return None, None

    def add_file(self, source_path):
        if not os.path.isfile(source_path):
            print("Invalid file path")
            return
        filename = os.path.basename(source_path)
        destination = os.path.join(self.shared_folder, filename)
        shutil.copy(source_path, destination)
        self.load_shared_files()

    def remove_file(self, file_id):
        # We now delete by file_id instead of filename
        if file_id not in self.my_files:
            print("File not shared")
            return

        filename = self.my_files[file_id]["filename"]
        path = os.path.join(self.shared_folder, filename)

        try:
            os.remove(path)
            del self.my_files[file_id]
            print(f"Removed file: {filename}")
        except OSError as e:
            print(f"Error deleting file: {e}")

    def get_files_summary(self):
        summary = {}
        for file_id, data in self.my_files.items():
            summary[file_id] = {
                "filename": data["filename"],  # UI needs to know the name
                "size": data["size"],
                "chunk_size": data["chunk_size"],
                "total_chunks": data["total_chunks"]
            }
        return summary