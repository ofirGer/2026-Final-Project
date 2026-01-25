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
            """Returns the current state of peers and files as JSON"""
            return jsonify({
                "peers": self.peer.peer_table,
                "my_files": self.file_manager.my_files
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

            threading.Thread(target=self.tcp_client.download_file,
                             args=(target_ip, filename)).start()

            return redirect('/')

    def run(self):
        self.app.run(host="0.0.0.0", port=8000, debug=False, use_reloader=False)