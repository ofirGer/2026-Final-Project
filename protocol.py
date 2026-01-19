class Protocol:
    # --- Configuration ---
    TCP_PORT = 50001
    BUFFER_SIZE = 4096

    # --- Message Headers ---
    CMD_DOWNLOAD = "DOWNLOAD"
    CMD_EXISTS = "EXISTS"
    CMD_ERROR = "ERR"
    CMD_OK = "OK"

    @staticmethod
    def prepare_request(filename):
        return f"{Protocol.CMD_DOWNLOAD} {filename}".encode()

    @staticmethod
    def prepare_response_exists(filesize):
        return f"{Protocol.CMD_EXISTS} {filesize}".encode()

    @staticmethod
    def prepare_response_error(message):
        return f"{Protocol.CMD_ERROR} {message}".encode()

    @staticmethod
    def parse_message(data):
        text = data.decode().strip()
        parts = text.split(" ", 1)
        command = parts[0]
        content = parts[1] if len(parts) > 1 else ""
        return command, content