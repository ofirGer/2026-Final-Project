from flask import Flask, render_template, request, redirect, jsonify, send_from_directory, session, url_for
import threading
import os
import tempfile



class WebUI:
    def __init__(self, peer, file_manager, tcp_client):
        self.peer = peer
        self.file_manager = file_manager
        self.tcp_client = tcp_client
        self.app = Flask(__name__)
        self.app.secret_key = 'og_p2p_secure_session_key'  # Required for sessions

        @self.app.route('/')
        def index():
            # If not logged in, redirect to lobby
            if 'username' not in session:
                return redirect(url_for('lobby'))
            return render_template('index.html',
                                   username=session['username'],
                                   network_key=session['network_key'],
                                   my_files=self.file_manager.my_files)

        @self.app.route('/lobby')
        def lobby():
            return render_template('lobby.html')

        @self.app.route('/join', methods=['POST'])
        def join():
            username = request.form.get('username')
            network_key = request.form.get('network_key')

            if username and network_key:
                session['username'] = username
                session['network_key'] = network_key

                # UPDATE PEER SECURITY ON THE FLY
                self.peer.set_network_password(network_key)
                print(f"[*] {username} joined swarm with key: {network_key}")

                return redirect(url_for('index'))
            return redirect(url_for('lobby'))

        @self.app.route('/logout')
        def logout():
            session.clear()
            return redirect(url_for('lobby'))

        # --- Existing API and File Routes ---
        @self.app.route('/api/data')
        def get_data():
            return jsonify({
                "peers": self.peer.peer_table,
                "my_files": self.file_manager.my_files,
                "downloads": self.tcp_client.active_downloads
            })

        @self.app.route('/select_file', methods=['POST'])
        def select_file():
            # Check if a file was actually uploaded in the request
            if 'file' not in request.files:
                return redirect('/')

            file = request.files['file']

            if file and file.filename != '':
                # 1. Save the uploaded file to a temporary location
                temp_dir = tempfile.gettempdir()
                temp_path = os.path.join(temp_dir, file.filename)
                file.save(temp_path)

                # 2. Use your existing file manager to add it to the shared folder
                self.file_manager.add_file(temp_path)

                # 3. Clean up the temporary file
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

            return redirect('/')

        @self.app.route('/download', methods=['POST'])
        def download_file():
            file_id = request.form.get('file_id')
            peers_with_file = []
            file_metadata = None
            filename = ""

            for peer_id, data in self.peer.peer_table.items():
                if file_id in data['files']:
                    peers_with_file.append(data['ip'])
                    if not file_metadata:
                        file_metadata = data['files'][file_id]
                        filename = file_metadata['filename']

            if peers_with_file and file_metadata:
                threading.Thread(target=self.tcp_client.download_file,
                                 args=(peers_with_file, file_id, filename, file_metadata)).start()
            return redirect('/')

        @self.app.route('/remove', methods=['POST'])
        def remove_file():
            file_id = request.form.get('file_id')
            if file_id:
                self.file_manager.remove_file(file_id)
            return redirect('/')

        @self.app.route('/open/<file_id>')
        def open_file(file_id):
            # 1. Check if the file is in our local shared manager
            if file_id in self.file_manager.my_files:
                filename = self.file_manager.my_files[file_id]['filename']
                shared_dir = os.path.abspath(self.file_manager.shared_folder)

                # 2. Serve the file to the browser
                # as_attachment=False allows the browser to try and view it (PDF, Images, Text)
                return send_from_directory(shared_dir, filename, as_attachment=False)

            return "File not found on this node.", 404

    def run(self):
        self.app.run(debug=False, port=5000, host='0.0.0.0')