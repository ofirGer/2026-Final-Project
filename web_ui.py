from flask import Flask, render_template, request, redirect, jsonify
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
            target_ip = request.form.get('ip')
            filename = request.form.get('filename')

            # Find the peer who has this file to get the metadata
            # (In a real app, we'd look up the peer_id, but here we search by IP)
            file_metadata = None
            for peer_id, data in self.peer.peer_table.items():
                if data['ip'] == target_ip and filename in data['files']:
                    file_metadata = data['files'][filename]
                    break

            if file_metadata:
                threading.Thread(target=self.tcp_client.download_file,
                                 args=(target_ip, filename, file_metadata)).start()
            else:
                print("Error: Could not find file metadata")

            return redirect('/')
        @self.app.route('/remove', methods=['POST'])
        def remove_file():
            file_name = request.form.get('filename')

            if(file_name):
                self.file_manager.remove_file(file_name)

            return redirect('/')


    def run(self):
        self.app.run(host="0.0.0.0", port=8000, debug=False, use_reloader=False)