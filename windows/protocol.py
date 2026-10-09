import struct
import time

"""
VBridge Binary Network Protocol Specification

Control Channel (TCP):
- Port: 58000 (default)
- Message structure (JSON with length prefix):
    [4 bytes big-endian length][UTF-8 JSON payload]
- Handshake Request:
    { "type": "AUTH", "token": "<token>", "device_name": "<name>", "sample_rate": 48000, "channels": 2 }
- Handshake Response:
    { "status": "OK" | "DENIED", "session_id": "<id>", "message": "<msg>" }
- Ping / Pong for RTT Latency:
    { "type": "PING", "timestamp": 1234567890 } -> { "type": "PONG", "timestamp": 1234567890 }

Audio Streaming Channel (UDP):
- Port: 58001 (default)
- Packet Header (16 bytes):
    Magic (4 bytes): b"VBRG"
    Version (1 byte): 1
    Packet Type (1 byte): 1 = Audio PCM, 2 = Audio Opus/Compressed, 3 = Keepalive
    Auth Token Hash / Session ID (2 bytes): uint16
    Sequence Number (4 bytes): uint32 (monotonically increasing)
    Timestamp (4 bytes): uint32 (Unix timestamp ms & 0xFFFFFFFF)
- Payload (variable, e.g. 1920 bytes = 960 stereo 16-bit PCM samples = 20ms @ 48kHz):
    Raw 16-bit signed PCM, little-endian, interleaved stereo (L, R, L, R...)
"""

HEADER_MAGIC = b"VBRG"
HEADER_FORMAT = "!4sBBHII"  # magic(4), version(1), type(1), session_id(2), seq(4), timestamp_ms(4)
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)  # 16 bytes

PACKET_TYPE_AUDIO_PCM = 1
PACKET_TYPE_AUDIO_OPUS = 2
PACKET_TYPE_KEEPALIVE = 3

DEFAULT_TCP_PORT = 58000
DEFAULT_UDP_PORT = 58001
DEFAULT_SAMPLE_RATE = 48000
DEFAULT_CHANNELS = 2
DEFAULT_SAMPLE_WIDTH = 2  # 16-bit PCM = 2 bytes per sample
DEFAULT_FRAME_MS = 20     # 20ms audio chunks = 960 samples per channel = 3840 bytes stereo (or 10ms = 480 samples = 1920 bytes)


def pack_audio_packet(session_id: int, seq_num: int, timestamp_ms: int, pcm_data: bytes, packet_type: int = PACKET_TYPE_AUDIO_PCM) -> bytes:
    """Pack header + PCM payload into binary packet."""
    header = struct.pack(
        HEADER_FORMAT,
        HEADER_MAGIC,
        1,  # version
        packet_type,
        session_id & 0xFFFF,
        seq_num & 0xFFFFFFFF,
        timestamp_ms & 0xFFFFFFFF
    )
    return header + pcm_data


def unpack_audio_packet(data: bytes):
    """
    Unpack binary packet into (session_id, seq_num, timestamp_ms, packet_type, payload).
    Returns None if packet is invalid or magic doesn't match.
    """
    if len(data) < HEADER_SIZE:
        return None
    magic, version, packet_type, session_id, seq_num, timestamp_ms = struct.unpack(
        HEADER_FORMAT, data[:HEADER_SIZE]
    )
    if magic != HEADER_MAGIC or version != 1:
        return None
    payload = data[HEADER_SIZE:]
    return {
        "session_id": session_id,
        "seq_num": seq_num,
        "timestamp_ms": timestamp_ms,
        "packet_type": packet_type,
        "payload": payload
    }
