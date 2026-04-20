from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes


class SecureConnection:
    def __init__(self, sock, is_client=False):
        self.sock = sock
        self.is_client = is_client
        self.fernet = None

    def _recv_exact(self, length):
        """Helper function to read EXACTLY 'length' bytes from the socket."""
        data = b""
        while len(data) < length:
            packet = self.sock.recv(length - len(data))
            if not packet: break
            data += packet
        return data

    def _send_raw(self, data: bytes):
        """Sends data with a 4-byte length prefix so the receiver knows how much to read."""
        length_prefix = len(data).to_bytes(4, 'big')
        self.sock.sendall(length_prefix + data)

    def _recv_raw(self) -> bytes:
        """Reads the length prefix, then reads the exact amount of data."""
        length_bytes = self._recv_exact(4)
        if not length_bytes: return b""
        length = int.from_bytes(length_bytes, 'big')
        return self._recv_exact(length)

    def handshake(self):
        """Performs the RSA + Symmetric Key Exchange"""
        if self.is_client:
            # 1. Receive Server's Public Key
            pub_bytes = self._recv_raw()
            public_key = serialization.load_pem_public_key(pub_bytes)

            # 2. Generate our fast Symmetric Key (Fernet)
            sym_key = Fernet.generate_key()
            self.fernet = Fernet(sym_key)

            # 3. Encrypt the Symmetric key with the Server's Public Key and send it
            encrypted_sym = public_key.encrypt(
                sym_key,
                padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None)
            )
            self._send_raw(encrypted_sym)
        else:
            # 1. Generate RSA Keys & Send Public Key to Client
            private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            public_key = private_key.public_key()

            pub_bytes = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            self._send_raw(pub_bytes)

            # 2. Receive the encrypted Symmetric Key from Client and decrypt it
            encrypted_sym = self._recv_raw()
            sym_key = private_key.decrypt(
                encrypted_sym,
                padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None)
            )
            self.fernet = Fernet(sym_key)

    def send_encrypted(self, data: bytes):
        """Encrypts data with Fernet and sends it."""
        encrypted_data = self.fernet.encrypt(data)
        self._send_raw(encrypted_data)

    def recv_encrypted(self) -> bytes:
        """Receives encrypted data and decrypts it back to original."""
        encrypted_data = self._recv_raw()
        if not encrypted_data: return b""
        return self.fernet.decrypt(encrypted_data)