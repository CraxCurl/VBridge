# 🎧 VBridge — Real-Time Low-Latency Audio Bridge

**Audio Path:** `Android Phone ➔ Windows Laptop ➔ Bluetooth Earphones`

VBridge connects your Android phone's system/media audio to your Windows laptop over a local Wi-Fi connection (UDP) and immediately routes the received audio to your laptop-connected Bluetooth earphones or headphones via Windows WASAPI with ultra-low latency (~65–110 ms).

---

## 🌟 Key Features

- **True Audio Routing:** Real-time 48 kHz stereo PCM audio captured on Android and rendered through Windows WASAPI.
- **Low Latency Pipeline:** High-performance UDP packetizer with timestamps, sequence IDs, and an adaptive jitter buffer.
- **Google Material You Dark UI:** AMOLED black (`#131314`) theme with multi-tiered surface cards, pill buttons, live RTT latency, and dual VU meters.
- **Bluetooth Endpoint Selector:** Enumerate and select Bluetooth TWS earbuds, headphones, or DACs with automatic hot-plug recovery.
- **Pairing & Security:** Dynamic QR code generation, 4-digit pairing code, and local-network-only binding.
- **Dual Audio Capture Modes:** Android 10+ `AudioPlaybackCapture` (system/media audio) and Microphone fallback mode.

---

## 📐 Architecture & Latency

```
+-------------------------------------------------------------+
|                      ANDROID PHONE                          |
|                                                             |
|  [ Media Apps / Spotify / YouTube / Games / Mic ]           |
|               |                                             |
|               v                                             |
|  [ AudioPlaybackCapture / AudioRecord (48kHz, 16-bit) ]     |
|               |                                             |
|               v                                             |
|  [ VBridge Packetizer (16-byte header + 20ms PCM) ]        |
+-------------------------------------------------------------+
                               |
               Local Wi-Fi (UDP 58001: Audio Data)
               Local Wi-Fi (TCP 58000: Control & Ping/Pong)
                               |
+-------------------------------------------------------------+
|                      WINDOWS LAPTOP                         |
|                                                             |
|  [ UDP Datagram Listener & Adaptive Jitter Buffer ]         |
|               |                                             |
|               v                                             |
|  [ Windows WASAPI Render Engine (sounddevice/PortAudio) ]   |
+-------------------------------------------------------------+
                               |
                   Bluetooth A2DP / Direct
                               v
               [ Bluetooth Earphones / TWS ]
```

### Latency Breakdown
| Stage | Latency |
|---|---|
| Android `AudioRecord` capture buffer | 10 – 20 ms |
| Wi-Fi LAN Transit (UDP) | 2 – 5 ms |
| Windows Jitter Buffer | 10 – 20 ms |
| Windows WASAPI Render Buffer | 10 – 15 ms |
| Bluetooth A2DP Laptop $\to$ Earbuds | 30 – 50 ms (AAC/SBC) |
| **Total End-to-End Latency** | **~65 – 110 ms** |

---

## 💻 1. Windows Application Setup

### Prerequisites
- **Operating System:** Windows 10 (version 1903+) or Windows 11.
- **Python:** Python 3.10 or higher installed. (Make sure *"Add Python to PATH"* was checked during installation).
- **Bluetooth:** Pair your Bluetooth Earphones / Headphones to Windows via **Windows Settings ➔ Bluetooth & Devices**.

### Installation Steps

1. Open PowerShell or Command Prompt in the project's `windows` directory:
   ```powershell
   cd c:\Users\vinay\Desktop\git-reps\VBridge\windows
   ```

2. Install the required Python dependencies:
   ```powershell
   python -m pip install -r requirements.txt
   ```

3. Launch the VBridge Windows Application:
   ```powershell
   python app.py
   ```
   *(Or simply double-click `windows/run.bat`)*

### Windows Firewall Configuration (If prompted)
If Windows Firewall blocks incoming connections from the phone, run this one-time command in PowerShell (**Run as Administrator**):
```powershell
New-NetFirewallRule -DisplayName "VBridge Audio Relay" -Direction Inbound -LocalPort 58000,58001 -Protocol TCP,UDP -Action Allow
```

---

## 📱 2. Android Companion App Setup

### Prerequisites
- **Android Version:** Android 10 (API Level 29) or higher.
- **Wi-Fi:** Phone and Windows laptop must be connected to the **same Wi-Fi network** (or phone connected to the laptop's Mobile Hotspot).

### Building and Installing the APK

#### Option A: Using Android Studio (Recommended)
1. Launch Android Studio.
2. Click **Open** and choose the `VBridge/android` folder.
3. Wait for Gradle sync to complete.
4. Connect your Android phone via USB (with **USB Debugging** enabled in Developer Options).
5. Click the green **Run 'app'** button (or press `Shift + F10`).

#### Option B: Building via Gradle CLI
From the `VBridge/android` directory:
```powershell
# On Windows
.\gradlew.bat assembleDebug

# On macOS/Linux
./gradlew assembleDebug
```
Install the generated APK onto your phone using ADB:
```powershell
adb install app\build\outputs\apk\debug\app-debug.apk
```

---

## 🚀 3. End-to-End Usage Walkthrough

### Method A: One-Tap Instant QR Code Connect (Fastest)

1. **On your Windows Laptop:**
   - Connect your **Bluetooth Earbuds** to Windows.
   - Start the Windows app:
     ```powershell
     python windows/app.py
     ```
   - In **Laptop IP / Hotspot**, make sure your active Wi-Fi or Phone Hotspot network is selected.
   - Ensure the QR code is visible on screen.

2. **On your Android Phone:**
   - Open the **VBridge** app.
   - Tap **`📷 Scan QR Code on Laptop`**.
   - Point your camera at the QR code on your laptop screen.
   - The app automatically fills the IP, port, and code, and connects immediately!
   - Tap **`▶ Start Audio Streaming`** and accept the system prompt (*"Start now"*).
   - Play audio on your phone (YouTube, Spotify, games)—it streams instantly to your earbuds!

---

### Method B: Manual Connection & Phone Hotspot Support

1. **When using your Phone's Mobile Hotspot:**
   - Turn on **Mobile Hotspot** on your phone.
   - Connect your laptop's Wi-Fi to your phone's hotspot.
   - On the Windows VBridge app, select the Hotspot IP from the **Laptop IP / Hotspot** dropdown (e.g. `192.168.43.x`).
   - Tap **`📷 Scan QR Code on Laptop`** on your phone (or type the IP manually) and tap **Connect to Laptop**.
   - Tap **`▶ Start Audio Streaming`**.

---

## 🧪 4. Immediate Test Verification (No Phone Required)

You can verify the Windows receiver, WASAPI routing, and Bluetooth audio output immediately on your PC using the included test generator script:

```powershell
python scripts/test_phone_sender.py 127.0.0.1 1234
```

This streams a 440 Hz / 554 Hz stereo harmonic tone over TCP/UDP to the VBridge app. You will immediately see:
- Live dual VU meters bouncing.
- Latency display updating.
- Test audio playing cleanly through your selected Bluetooth earbuds.

---

## 🔧 5. Troubleshooting & FAQ

### 1. The phone cannot connect ("Connection Refused" or "Timeout")
- **Same Network:** Confirm both devices are connected to the same Wi-Fi router.
- **Firewall:** Ensure Windows Firewall isn't blocking ports `58000` (TCP) and `58001` (UDP).
- **Public / University Wi-Fi (AP Isolation):** Many public networks block peer-to-peer traffic between devices.
  - *Fix:* Turn on **Mobile Hotspot** on your Windows laptop (Settings ➔ Network & Internet ➔ Mobile Hotspot), then connect your phone's Wi-Fi to the laptop's hotspot.

### 2. Audio stutters or drops packets
- **2.4 GHz vs 5 GHz Wi-Fi:** 2.4 GHz Wi-Fi shares frequencies with Bluetooth and can cause interference. Connect to a **5 GHz Wi-Fi** network or use 5 GHz Hotspot.
- **Output Device:** Make sure you select the output device with the `[WASAPI]` tag in the VBridge dropdown.

### 3. No sound from certain apps
- Some banking or DRM-protected apps explicitly opt out of capture via `ALLOW_CAPTURE_BY_NONE`.
- Cellular phone calls (`USAGE_VOICE_COMMUNICATION`) are restricted by Android for privacy.
- *Workaround:* Switch to **Microphone / Ambient Audio** mode in the Android app to capture external/voice audio.

### 4. Earbuds disconnect or power off
- When Bluetooth earbuds reconnect to Windows, click **🔄 Refresh** in the VBridge app to re-select them. You do not need to restart the Android stream.

---

## 📂 Project Repository Map

| Path | Purpose |
|---|---|
| [windows/app.py](file:///c:/Users/vinay/Desktop/git-reps/VBridge/windows/app.py) | Main Windows GUI application (CustomTkinter Google Material You Dark) |
| [windows/audio_player.py](file:///c:/Users/vinay/Desktop/git-reps/VBridge/windows/audio_player.py) | WASAPI audio render engine, device switcher, and volume/VU meter |
| [windows/audio_receiver.py](file:///c:/Users/vinay/Desktop/git-reps/VBridge/windows/audio_receiver.py) | UDP audio listener, adaptive jitter buffer, and TCP control server |
| [windows/protocol.py](file:///c:/Users/vinay/Desktop/git-reps/VBridge/windows/protocol.py) | Binary packet header serialization and control protocol specs |
| [windows/run.bat](file:///c:/Users/vinay/Desktop/git-reps/VBridge/windows/run.bat) | Windows launcher script |
| [android/](file:///c:/Users/vinay/Desktop/git-reps/VBridge/android/) | Complete Android Companion App Studio Project |
| [scripts/test_phone_sender.py](file:///c:/Users/vinay/Desktop/git-reps/VBridge/scripts/test_phone_sender.py) | Independent test tone streaming utility |
| [ARCHITECTURE.md](file:///c:/Users/vinay/Desktop/git-reps/VBridge/ARCHITECTURE.md) | In-depth technical architecture and protocol specification |
