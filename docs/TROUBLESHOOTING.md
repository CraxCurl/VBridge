# Troubleshooting & FAQ

### 1. The Phone Cannot Connect to the Laptop ("Connection Refused" or "Timeout")
- **Same Wi-Fi Network**: Ensure both phone and laptop are on the same Wi-Fi subnet (e.g. `192.168.1.x`).
- **Windows Firewall**: Windows Firewall may block incoming TCP port 58000 or UDP port 58001.
  - To allow in PowerShell (Run as Administrator):
    ```powershell
    New-NetFirewallRule -DisplayName "VBridge Receiver" -Direction Inbound -LocalPort 58000,58001 -Protocol TCP,UDP -Action Allow
    ```
- **Wi-Fi AP Isolation**: Some public or university Wi-Fi networks enable "Client Isolation" preventing devices from talking to each other. In that case, enable **Mobile Hotspot** on Windows and connect your phone directly to the laptop's Wi-Fi hotspot.

---

### 2. Audio Stutters or Cuts Out
- **Bluetooth Interference**: 2.4GHz Wi-Fi and Bluetooth share the same frequency band. If possible, connect your laptop and phone to a **5 GHz Wi-Fi band** or use the laptop's 5GHz mobile hotspot.
- **Audio Output Selection**: Ensure you select the `[WASAPI]` device in the dropdown menu for minimum buffer latency.

---

### 3. No Audio Heard from Certain Android Apps
- **App Opt-Out**: Some apps (e.g. bank apps or DRM-protected streams) explicitly set `AudioAttributes.setAllowedCapturePolicy(ALLOW_CAPTURE_BY_NONE)`.
- **VoIP / Phone Calls**: Phone calls (`USAGE_VOICE_COMMUNICATION`) are restricted by Android OS from third-party capture for privacy.
- **Solution**: Switch to **Microphone / Ambient Audio** mode in the VBridge Android app if you need to stream voice or external audio.

---

### 4. Bluetooth Earbuds Disconnect
- VBridge monitors device connection states. If your Bluetooth earbuds disconnect or power off, simply turn them back on, wait for Windows to connect, and click **🔄 Refresh** in VBridge to select them again without needing to restart the Android stream.
