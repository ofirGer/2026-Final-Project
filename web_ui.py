# Change this line:
from flask import Flask, render_template, request, redirect, jsonify, send_from_directory
import threading
import os
import tkinter as tk
from tkinter import filedialog


class WebUI:
    def __init__(self, peer, file_manager, tcp_client):
        self.peer = peer
        self.file_manager = file_manager
        self.tcp_client = tcp_client
        self.app = Flask(__name__)
        self.app.secret_key = 'super_secret_key'

        # --- ROUTES ---

        @self.app.route('/')
        def index():
            # We still pass data for the first load, but JS takes over after
            return render_template('index.html',
                                   peer_table=self.peer.peer_table,
                                   my_files=self.file_manager.my_files)

        # --- NEW: API Route for JavaScript to talk to ---
        @self.app.route('/api/data')
        def get_data():
            """Returns the current state of peers, files, AND active downloads"""
            return jsonify({
                "peers": self.peer.peer_table,
                "my_files": self.file_manager.my_files,
                "downloads": self.tcp_client.active_downloads  # <--- NEW
            })

        @self.app.route('/select_file', methods=['POST'])
        def select_file():
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)

            file_path = filedialog.askopenfilename(title="Select a file to share")
            root.destroy()

            if file_path:
                self.file_manager.add_file(file_path)

            return redirect('/')

        @self.app.route('/download', methods=['POST'])
        def download():
            file_id = request.form.get('file_id')  # אנחנו מקבלים מזהה ייחודי במקום שם

            peers_with_file = []
            file_metadata = None
            filename = None

            # חיפוש בכל טבלת העמיתים: מי מחזיק ב-ID הזה?
            for peer_id, data in self.peer.peer_table.items():
                if file_id in data['files']:
                    peers_with_file.append(data['ip'])
                    if file_metadata is None:
                        file_metadata = data['files'][file_id]
                        filename = file_metadata['filename']

            # אם מצאנו את הקובץ אצל משתמשים ברשת, מתחילים להוריד מכולם במקביל!
            if peers_with_file and file_metadata:
                threading.Thread(target=self.tcp_client.download_file,
                                 args=(peers_with_file, file_id, filename, file_metadata)).start()
            else:
                print("Error: Could not find any peers with this file ID")

            return redirect('/')

        @self.app.route('/remove', methods=['POST'])
        def remove_file():
            file_id = request.form.get('file_id')  # Remove by ID
            if (file_id):
                self.file_manager.remove_file(file_id)
            return redirect('/')

        @self.app.route('/open/<file_id>')
        def open_file(file_id):
            # Check if the file is actually in our shared files
            if file_id in self.file_manager.my_files:
                filename = self.file_manager.my_files[file_id]['filename']

                # Send the physical file from the shared folder to the browser
                return send_from_directory(
                    os.path.abspath(self.file_manager.shared_folder),
                    filename
                )
            return "File not found", 404

    def run(self):
        self.app.run(host="0.0.0.0", port=8000, debug=False, use_reloader=False)
