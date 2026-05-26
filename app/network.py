from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QAbstractSocket, QSsl, QSslConfiguration, QSslSocket, QTcpSocket


class MuckConnection(QObject):
    connected = Signal()
    disconnected = Signal()
    line_received = Signal(str)
    status_changed = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._socket: QAbstractSocket | None = None
        self._buffer = bytearray()
        self._using_ssl = False

    def connect_to_host(self, host: str, port: int, use_ssl: bool) -> None:
        self.disconnect_from_host()
        self._buffer.clear()
        self._using_ssl = use_ssl

        if use_ssl:
            socket = QSslSocket(self)
            cfg = QSslConfiguration.defaultConfiguration()
            try:
                cfg.setProtocol(QSsl.SslProtocol.TlsV1_2)
            except Exception:
                try:
                    cfg.setProtocol(QSsl.SslProtocol.TlsV1_2OrLater)
                except Exception:
                    pass
            socket.setSslConfiguration(cfg)
            socket.setPeerVerifyMode(QSslSocket.PeerVerifyMode.VerifyNone)
            socket.readyRead.connect(self._on_ready_read)
            socket.connected.connect(self._on_tcp_connected)
            socket.encrypted.connect(self._on_encrypted)
            socket.disconnected.connect(self._on_disconnected)
            socket.errorOccurred.connect(self._on_error)
            socket.sslErrors.connect(self._on_ssl_errors)
            self._socket = socket
            self.status_changed.emit(f"Connecting to {host}:{port} (SSL)...")
            socket.connectToHostEncrypted(host, port)
        else:
            socket = QTcpSocket(self)
            socket.readyRead.connect(self._on_ready_read)
            socket.connected.connect(self._on_connected)
            socket.disconnected.connect(self._on_disconnected)
            socket.errorOccurred.connect(self._on_error)
            self._socket = socket
            self.status_changed.emit(f"Connecting to {host}:{port}...")
            socket.connectToHost(host, port)

    def disconnect_from_host(self) -> None:
        if not self._socket:
            return
        try:
            self._socket.disconnectFromHost()
        finally:
            self._socket.deleteLater()
            self._socket = None

    def send_line(self, text: str) -> None:
        if not self._socket:
            return
        self._socket.write((text + "\r\n").encode("utf-8", errors="replace"))

    def _on_tcp_connected(self) -> None:
        if self._using_ssl:
            self.status_changed.emit("TCP connected, negotiating SSL...")
            return
        self._on_connected()

    def _on_encrypted(self) -> None:
        self.status_changed.emit("SSL connected")
        self.connected.emit()

    def _on_connected(self) -> None:
        self.status_changed.emit("Connected")
        self.connected.emit()

    def _on_disconnected(self) -> None:
        self.status_changed.emit("Disconnected")
        self.disconnected.emit()

    def _on_error(self, _socket_error: object) -> None:
        if self._socket:
            self.error_occurred.emit(self._socket.errorString())

    def _on_ssl_errors(self, errors) -> None:
        if not isinstance(self._socket, QSslSocket):
            return
        self._socket.ignoreSslErrors()

    def _on_ready_read(self) -> None:
        if not self._socket:
            return
        self._buffer.extend(bytes(self._socket.readAll()))
        self._strip_telnet_iac()
        self._emit_complete_lines()

    def _strip_telnet_iac(self) -> None:
        cleaned = bytearray()
        i = 0
        buf = self._buffer
        while i < len(buf):
            byte = buf[i]
            if byte == 255:  # IAC
                if i + 1 >= len(buf):
                    break
                cmd = buf[i + 1]
                if cmd in (251, 252, 253, 254):
                    if i + 2 >= len(buf):
                        break
                    i += 3
                    continue
                if cmd == 250:
                    end = buf.find(b"\xff\xf0", i + 2)
                    if end == -1:
                        break
                    i = end + 2
                    continue
                i += 2
                continue
            cleaned.append(byte)
            i += 1
        self._buffer = cleaned

    def _emit_complete_lines(self) -> None:
        while True:
            positions = [p for p in (self._buffer.find(b"\r\n"), self._buffer.find(b"\n"), self._buffer.find(b"\r")) if p != -1]
            if not positions:
                return
            line_end = min(positions)
            raw_line = bytes(self._buffer[:line_end])
            if self._buffer[line_end:line_end + 2] == b"\r\n":
                del self._buffer[:line_end + 2]
            else:
                del self._buffer[:line_end + 1]
            self.line_received.emit(raw_line.decode("utf-8", errors="replace"))
