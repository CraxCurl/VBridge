import socket
import time
import math
import struct
import json
import sys
import os

# Add windows folder to path to import protocol
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "windows")))
from protocol import (
    pack_audio_packet,
    DEFAULT_TCP_PORT,
    DEFAULT_UDP_PORT,
    PACKET_TYPE_AUDIO_PCM,
    PACKET_TYPE_KEEPALIVE
)

def run_test_sender(server_ip="127.0.0.1", pairing_code="1234", duration_seconds=30):
    print(f"[*] Connecting to VBridge Server at {server_ip}:{DEFAULT_TCP_PORT} (Code: {pairing_code})...")
    
    tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        tcp_sock.connect((server_ip, DEFAULT_TCP_PORT))
    except Exception as e:
        print(f"[-] Failed to connect via TCP: {e}")
        return

    # Send AUTH
    auth_msg = {
        "type": "AUTH",
        "token": pairing_code,
        "device_name": "Test Audio Generator (Python)",
        "sample_rate": 48000,
        "channels": 2
    }
    raw = json.dumps(auth_msg).encode("utf-8")
    tcp_sock.sendall(len(raw).to_bytes(4, "big") + raw)

    # Read response
    resp_len = int.from_bytes(tcp_sock.recv(4), "big")
    resp = json.loads(tcp_sock.recv(resp_len).decode("utf-8"))
    print(f"[+] Server Response: {resp}")

    if resp.get("status") != "OK":
        print("[-] Authentication rejected.")
        tcp_sock.close()
        return

    session_id = resp.get("session_id", 1)
    udp_port = resp.get("udp_port", DEFAULT_UDP_PORT)

    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    dest_addr = (server_ip, udp_port)

    # Inform server we are starting stream
    start_msg = {"type": "START_STREAM"}
    raw = json.dumps(start_msg).encode("utf-8")
    tcp_sock.sendall(len(raw).to_bytes(4, "big") + raw)

    print(f"[+] Streaming 440Hz / 880Hz test stereo tone to UDP {dest_addr} for {duration_seconds}s...")
    
    sample_rate = 48000
    channels = 2
    chunk_frames = 960  # 20ms @ 48kHz
    freq_left = 440.0   # A4 tone
    freq_right = 554.37 # C#5 tone (musical major third harmony)

    seq_num = 0
    t_start = time.time()
    next_frame_time = t_start

    try:
        while time.time() - t_start < duration_seconds:
            # Generate 20ms sine wave audio PCM 16-bit
            samples = bytearray()
            for i in range(chunk_frames):
                t = (seq_num * chunk_frames + i) / sample_rate
                # Harmonic tone with gentle amplitude
                val_l = int(12000.0 * math.sin(2.0 * math.pi * freq_left * t))
                val_r = int(12000.0 * math.sin(2.0 * math.pi * freq_right * t))
                samples.extend(struct.pack("<hh", val_l, val_r))

            timestamp_ms = int(time.time() * 1000) & 0xFFFFFFFF
            packet = pack_audio_packet(session_id, seq_num, timestamp_ms, bytes(samples))
            udp_sock.sendto(packet, dest_addr)

            seq_num += 1

            # Precision pacing (20ms per packet)
            next_frame_time += 0.020
            sleep_time = next_frame_time - time.time()
            if sleep_time > 0:
                time.sleep(sleep_time)

            # Every 100 frames (~2s), send a ping to measure latency
            if seq_num % 100 == 0:
                ping_msg = {"type": "PING", "timestamp": int(time.time() * 1000)}
                raw_ping = json.dumps(ping_msg).encode("utf-8")
                tcp_sock.sendall(len(raw_ping).to_bytes(4, "big") + raw_ping)

    except KeyboardInterrupt:
        print("\n[*] Stopped by user.")
    finally:
        print("[*] Closing test streamer...")
        try:
            stop_msg = {"type": "STOP_STREAM"}
            raw = json.dumps(stop_msg).encode("utf-8")
            tcp_sock.sendall(len(raw).to_bytes(4, "big") + raw)
            tcp_sock.close()
            udp_sock.close()
        except Exception:
            pass
        print("[+] Done.")

if __name__ == "__main__":
    ip = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    code = sys.argv[2] if len(sys.argv) > 2 else "1234"
    run_test_sender(ip, code)
