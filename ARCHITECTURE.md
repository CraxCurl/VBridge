# VBridge Architecture & Technical Design

## 1. System Overview

**VBridge** is an ultra-low latency audio bridge system that relays audio in real time:

$$\text{Android Phone} \xrightarrow[\text{Local Wi-Fi (UDP/TCP)}]{\text{AudioPlaybackCapture}} \text{Windows Laptop (Receiver)} \xrightarrow[\text{WASAPI Low-Latency}]{\text{Bluetooth / Direct}} \text{Bluetooth Earphones}$$

```
+-------------------------------------------------------------+
|                      ANDROID PHONE                          |
|                                                             |
|  [ Media Apps / Games / Mic ]                               |
|               |                                             |
|               v                                             |
|  [ AudioPlaybackCapture / AudioRecord (48kHz, 16-bit) ]     |
|               |                                             |
|               v                                             |
|  [ VBridge Packetizer (16-byte header + 20ms PCM) ]        |
|               |                                             |
|               +--------------------+                        |
|                                    |                        |
+------------------------------------|------------------------+
                                     |
                       Wi-Fi (UDP Port 58001: Audio)
                       Wi-Fi (TCP Port 58000: Control)
                                     |
+------------------------------------|------------------------+
|                      WINDOWS LAPTOP                         |
|                                    |                        |
|  [ UDP Datagram Listener ] <-------+                        |
|               |                                             |
|               v                                             |
|  [ Adaptive Jitter Buffer & Packet Sequencer ]              |
|               |                                             |
|               v                                             |
|  [ Float32 Conversion & Gain / Soft-Limiter ]               |
|               |                                             |
|               v                                             |
|  [ Windows WASAPI Render Engine (sounddevice/PortAudio) ]   |
|               |                                             |
+---------------|---------------------------------------------+
                |
          Bluetooth A2DP / Direct
                |
                v
    [ Bluetooth Earphones / TWS ]
```

---

## 2. Why Classic Bluetooth A2DP Sink Cannot Be Easily Used on Windows

Classic Bluetooth specifies two roles in the Advanced Audio Distribution Profile (A2DP):
1. **A2DP Source (SRC)**: Sends audio (e.g., PC sending audio to headphones).
2. **A2DP Sink (SNK)**: Receives audio (e.g., headphones receiving audio from PC).

### Limitations on Windows:
- Windows is designed primarily as an **A2DP Source**. 
- In Windows 10 (version 1903), Microsoft completely removed user-level A2DP Sink support. While Windows 10 (version 2004+) added partial WinRT `BluetoothAudioSource` APIs, these are restricted, often fail with third-party Bluetooth adapter drivers, require exclusive system-level pairing, and **do not permit a single Windows machine to simultaneously receive an A2DP stream from a phone and re-transmit it as an A2DP stream to Bluetooth earbuds on the same adapter** without severe packet collisions and latency spikes.
- **Solution**: Wi-Fi UDP transmission bypasses all Bluetooth hardware and driver sink limitations, providing far higher bandwidth, lower latency, and lossless 48kHz audio.

---

## 3. Android `AudioPlaybackCapture` API & Limitations

Introduced in Android 10 (API 29), `AudioPlaybackCapture` allows capturing audio played by other applications.

### Requirements & Limitations:
1. **MediaProjection Permission**: The user must explicitly grant permission via a system dialog (`MediaProjectionManager.createScreenCaptureIntent()`).
2. **Foreground Service**: Must run inside a foreground service tagged with `foregroundServiceType="mediaProjection"` with a visible notification.
3. **App Opt-Outs**:
   - Applications can opt out of being captured by setting `AudioAttributes.setAllowedCapturePolicy(ALLOW_CAPTURE_BY_NONE)`.
   - Communication audio (`USAGE_VOICE_COMMUNICATION`, such as standard cellular phone calls) cannot be captured by third-party apps for privacy reasons.
   - Media playback (YouTube, Spotify, games, web browsers) is fully capturable by default (`USAGE_MEDIA`, `USAGE_GAME`, `USAGE_UNKNOWN`).
4. **Microphone Fallback**: VBridge includes a toggle for Microphone capture so users can also capture ambient audio, instruments, or voice when desired.

---

## 4. Transport Protocol & Codec Selection

### Transport:
- **UDP (Port 58001)** for real-time audio datagrams:
  - Eliminates TCP Head-of-Line blocking and retransmission delays.
  - Sub-millisecond packet transmission on local 5GHz / 2.4GHz Wi-Fi networks.
- **TCP (Port 58000)** for control channel:
  - Pairing handshake and token verification.
  - Active Ping-Pong round-trip time (RTT) latency measurement every second.

### Packet Format (16-byte binary header):
```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                       Magic b"VBRG"                           |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
| Version (1B)  | Type (1B)     |       Session ID (2B)         |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                     Sequence Number (4B)                      |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                     Timestamp ms (4B)                         |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                      PCM Audio Payload...                     |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

### Audio Format & Codec:
- **Format**: Linear PCM 16-bit signed, 48,000 Hz, 2 channels (Stereo), little-endian.
- **Frame Size**: 20 ms chunks (960 frames = 3,840 bytes per packet).
- **Bitrate**: 1.536 Mbps (well within typical Wi-Fi throughput of 50–300 Mbps).
- **Rationale**: Zero encode/decode latency on modern devices, uncompressed bit-perfect sound quality.

---

## 5. Windows Audio API (WASAPI)

VBridge leverages **WASAPI (Windows Audio Session API)** in low-latency shared mode:
- Direct audio hardware buffer rendering.
- Enumerates all physical endpoints and filters Bluetooth earphones/headsets.
- Dynamic hot-plug detection and seamless output device switching without interrupting the incoming network stream.
- Peak and RMS calculations for real-time visual level metering.

---

## 6. End-to-End Latency Breakdown

| Stage | Latency |
|---|---|
| Android `AudioRecord` buffer | 10 – 20 ms |
| Wi-Fi Network Transit (UDP LAN) | 2 – 5 ms |
| Windows Jitter Buffer | 10 – 20 ms |
| Windows WASAPI Render Buffer | 10 – 15 ms |
| Bluetooth A2DP Laptop $\to$ Earbuds | 30 – 50 ms (AAC/SBC) |
| **Total Approximate Latency** | **~65 – 110 ms** |

This latency range provides an immediate, smooth, and stutter-free listening experience for music, video, and gaming.
