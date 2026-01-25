from flask import Flask, render_template, request, redirect, flash
import threading
import os


class WebUI:
    def __init__(self, peer, file_manager, tcp_client):
        self.peer = peer
        self.file_manager = file_manager
        self.tcp_client = tcp_client
        self.app = Flask(__name__)
        self.app.secret_key = 'super_secret_key'  # Needed for flashing messages

        # --- ROUTES ---

        @self.app.route('/')
        def index():
            # Pass the peer table and my files to the HTML
            return render_template('index.html',
                                   peer_table=self.peer.peer_table,
                                   my_files=self.file_manager.my_files)

        @self.app.route('/add_file', methods=['POST'])
        def add_file():
            filepath = request.form.get('filepath')
            if os.path.exists(filepath):
                self.file_manager.add_file(filepath)
            return redirect('/')

        @self.app.route('/download', methods=['POST'])
        def download():
            target_ip = request.form.get('ip')
            filename = request.form.get('filename')

            # Start download in a background thread so the website doesn't freeze
            thread = threading.Thread(target=self.tcp_client.download_file,
                                      args=(target_ip, filename))
            thread.start()

            return redirect('/')

    def run(self):
        # We turn off the reloader because it doesn't play nice with our Peer threads
        self.app.run(host="0.0.0.0", port=8000, debug=False, use_reloader=False)