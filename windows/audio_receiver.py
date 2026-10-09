import socket
import threading
import json
import time
import logging
try:
    from protocol import (
        HEADER_SIZE,
        DEFAULT_TCP_PORT,
        DEFAULT_UDP_PORT,
        unpack_audio_packet,
        PACKET_TYPE_AUDIO_PCM,
        PACKET_TYPE_KEEPALIVE
    )
except ImportError:
    from windows.protocol import (
        HEADER_SIZE,
        DEFAULT_TCP_PORT,
        DEFAULT_UDP_PORT,
        unpack_audio_packet,
        PACKET_TYPE_AUDIO_PCM,
        PACKET_TYPE_KEEPALIVE
    )

logger = logging.getLogger("VBridge.AudioReceiver")


class AudioReceiver:
    """
    VBridge Audio & Control Receiver Server.
    Manages TCP Handshake / Pairing / Latency RTT & UDP Audio streaming listener.
    Automatically starts playing audio as soon as packets arrive from the phone.
    """

    def __init__(self, audio_player, tcp_port=DEFAULT_TCP_PORT, udp_port=DEFAULT_UDP_PORT):
        self.audio_player = audio_player
        self.tcp_port = tcp_port
        self.udp_port = udp_port

        self.pairing_code = "1234"
        self.auth_token = "VBRIDGE-DEFAULT-PASS"
        self.is_running = False

        self.tcp_socket = None
        self.udp_socket = None

        self.client_connected = False
        self.client_ip = None
        self.client_device_name = "Unknown Phone"
        self.session_id = 0

        self.active_stream = False

        # Latency statistics (in milliseconds)
        self.rtt_latency_ms = 0.0
        self.last_packet_time = 0.0
        self.packets_per_sec = 0
        self._packet_counter = 0
        self._last_sec_time = time.time()

        # Callbacks for UI updates
        self.on_client_connected = None
        self.on_client_disconnected = None
        self.on_stream_status_change = None

        self._threads = []

    @staticmethod
    def get_local_ip():
        """Retrieve local Wi-Fi / LAN IP address."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    @staticmethod
    def get_all_local_ips():
        """Retrieve all host IPv4 network interfaces (Wi-Fi, Phone Hotspot, LAN)."""
        ips = []
        try:
            hostname = socket.gethostname()
            for ip in socket.gethostbyname_ex(hostname)[2]:
                if not ip.startswith("127.") and not ip.startswith("169.254."):
                    ips.append(ip)
        except Exception:
            pass

        primary = AudioReceiver.get_local_ip()
        if primary and primary != "127.0.0.1" and not primary.startswith("169.254."):
            if primary in ips:
                ips.remove(primary)
            ips.insert(0, primary)

        if not ips:
            ips.append("127.0.0.1")
        return ips

    def set_pairing_code(self, code: str):
        self.pairing_code = str(code).strip()

    def start(self):
        """Start TCP and UDP receiver servers."""
        if self.is_running:
            return

        self.is_running = True

        # Start TCP control server thread
        t_tcp = threading.Thread(target=self._run_tcp_server, daemon=True, name="VBridge-TCP-Control")
        t_tcp.start()
        self._threads.append(t_tcp)

        # Start UDP audio receiver thread
        t_udp = threading.Thread(target=self._run_udp_server, daemon=True, name="VBridge-UDP-Audio")
        t_udp.start()
        self._threads.append(t_udp)

        logger.info(f"VBridge Receiver started on IP {self.get_local_ip()} (TCP {self.tcp_port}, UDP {self.udp_port})")

    def stop(self):
        """Stop receiver servers and release network resources."""
        self.is_running = False
        self.client_connected = False
        self.active_stream = False

        if self.tcp_socket:
            try:
                self.tcp_socket.close()
            except Exception:
                pass
            self.tcp_socket = None

        if self.udp_socket:
            try:
                self.udp_socket.close()
            except Exception:
                pass
            self.udp_socket = None

        self.audio_player.stop()
        logger.info("VBridge Receiver stopped.")

    def _run_tcp_server(self):
        """TCP server loop handling incoming client connections and pairing handshakes."""
        try:
            self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.tcp_socket.bind(("0.0.0.0", self.tcp_port))
            self.tcp_socket.listen(3)
            self.tcp_socket.settimeout(1.0)
            logger.info(f"TCP Control server listening on port {self.tcp_port}")
        except Exception as e:
            logger.error(f"Failed to bind TCP server on port {self.tcp_port}: {e}")
            return

        while self.is_running:
            try:
                conn, addr = self.tcp_socket.accept()
                logger.info(f"Incoming TCP connection from {addr}")
                t = threading.Thread(target=self._handle_tcp_client, args=(conn, addr), daemon=True)
                t.start()
            except socket.timeout:
                continue
            except Exception as e:
                if self.is_running:
                    logger.debug(f"TCP accept error: {e}")
                break

    def _recv_exact(self, conn: socket.socket, num_bytes: int):
        """Read exactly num_bytes from TCP socket, handling fragmentations and timeouts."""
        data = bytearray()
        while len(data) < num_bytes and self.is_running:
            try:
                chunk = conn.recv(num_bytes - len(data))
                if not chunk:
                    return None
                data.extend(chunk)
            except socket.timeout:
                continue
            except (ConnectionResetError, ConnectionAbortedError):
                return None
        return bytes(data) if len(data) == num_bytes else None

    def _handle_tcp_client(self, conn: socket.socket, addr):
        """Handle individual TCP client connection, authentication, and ping/pong."""
        conn.settimeout(1.0)
        try:
            while self.is_running:
                raw_len = self._recv_exact(conn, 4)
                if not raw_len:
                    break

                msg_len = int.from_bytes(raw_len, byteorder="big")
                if msg_len <= 0 or msg_len > 65536:
                    logger.warning(f"Invalid message length from {addr}: {msg_len}")
                    break

                data = self._recv_exact(conn, msg_len)
                if not data:
                    break

                msg = json.loads(data.decode("utf-8"))
                msg_type = msg.get("type")

                if msg_type == "AUTH":
                    token = msg.get("token", "")
                    device_name = msg.get("device_name", "Android Phone")
                    # Check token or pairing code
                    if token == self.auth_token or token == self.pairing_code or self.pairing_code == "":
                        self.client_connected = True
                        self.client_ip = addr[0]
                        self.client_device_name = device_name
                        self.session_id = int(time.time()) & 0xFFFF
                        resp = {
                            "status": "OK",
                            "session_id": self.session_id,
                            "udp_port": self.udp_port,
                            "sample_rate": self.audio_player.sample_rate,
                            "channels": self.audio_player.channels,
                            "message": "Authenticated successfully"
                        }
                        self._send_tcp_json(conn, resp)
                        logger.info(f"Client authenticated: {device_name} ({addr[0]})")
                        if self.on_client_connected:
                            self.on_client_connected(self.client_device_name, self.client_ip)
                    else:
                        resp = {"status": "DENIED", "message": "Invalid pairing code or token"}
                        self._send_tcp_json(conn, resp)
                        logger.warning(f"Authentication failed for {addr}: incorrect code '{token}'")

                elif msg_type == "PING":
                    client_ts = msg.get("timestamp", 0)
                    server_ts = int(time.time() * 1000)
                    resp = {
                        "type": "PONG",
                        "client_ts": client_ts,
                        "server_ts": server_ts
                    }
                    self._send_tcp_json(conn, resp)

                elif msg_type == "START_STREAM":
                    self.active_stream = True
                    self.audio_player.start()
                    resp = {"status": "OK", "message": "Stream started"}
                    self._send_tcp_json(conn, resp)
                    if self.on_stream_status_change:
                        self.on_stream_status_change(True)

                elif msg_type == "STOP_STREAM":
                    self.active_stream = False
                    resp = {"status": "OK", "message": "Stream stopped"}
                    self._send_tcp_json(conn, resp)
                    if self.on_stream_status_change:
                        self.on_stream_status_change(False)

                elif msg_type == "LATENCY_REPORT":
                    rtt = msg.get("rtt_ms", 0.0)
                    if rtt > 0:
                        self.rtt_latency_ms = rtt

        except Exception as e:
            logger.debug(f"TCP client connection closed or error ({addr}): {e}")
        finally:
            try:
                conn.close()
            except Exception:
                pass
            if self.client_ip == addr[0]:
                self.client_connected = False
                if self.on_client_disconnected:
                    self.on_client_disconnected()

    def _send_tcp_json(self, conn: socket.socket, payload: dict):
        raw_bytes = json.dumps(payload).encode("utf-8")
        len_prefix = len(raw_bytes).to_bytes(4, byteorder="big")
        conn.sendall(len_prefix + raw_bytes)

    def _run_udp_server(self):
        """UDP server loop receiving real-time audio datagrams."""
        try:
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 2 * 1024 * 1024)
            except Exception:
                pass
            self.udp_socket.bind(("0.0.0.0", self.udp_port))
            self.udp_socket.settimeout(0.5)
            logger.info(f"UDP Audio server listening on port {self.udp_port}")
        except Exception as e:
            logger.error(f"Failed to bind UDP server on port {self.udp_port}: {e}")
            return

        while self.is_running:
            try:
                data, addr = self.udp_socket.recvfrom(65535)
                if not data:
                    continue

                packet = unpack_audio_packet(data)
                if not packet:
                    continue

                self.last_packet_time = time.time()
                self._packet_counter += 1

                now = time.time()
                if now - self._last_sec_time >= 1.0:
                    self.packets_per_sec = self._packet_counter
                    self._packet_counter = 0
                    self._last_sec_time = now

                pkt_ts = packet["timestamp_ms"]
                now_ms = int(time.time() * 1000) & 0xFFFFFFFF
                diff_ms = (now_ms - pkt_ts) & 0xFFFFFFFF
                if 0 <= diff_ms < 500:
                    if self.rtt_latency_ms == 0.0:
                        self.rtt_latency_ms = diff_ms
                    else:
                        self.rtt_latency_ms = (self.rtt_latency_ms * 0.9) + (diff_ms * 0.1)

                if packet["packet_type"] == PACKET_TYPE_AUDIO_PCM:
                    # Feed high-speed PCM payload to AudioRingBuffer
                    self.audio_player.queue_pcm_data(packet["payload"])

                    if not self.active_stream:
                        self.active_stream = True
                        if self.on_stream_status_change:
                            self.on_stream_status_change(True)

            except socket.timeout:
                continue
            except Exception as e:
                if self.is_running:
                    logger.debug(f"UDP recv error: {e}")
                break
