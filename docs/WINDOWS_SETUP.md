# Windows Setup & Run Guide

## Prerequisites
- Windows 10 (1903+) or Windows 11.
- Python 3.10+ (ensure "Add Python to PATH" was checked during installation).
- Bluetooth Earphones / Headphones paired to Windows.

## Installation

1. Open PowerShell or Command Prompt in the `VBridge\windows` directory:
   ```powershell
   cd windows
   ```

2. Install the required Python dependencies:
   ```powershell
   python -m pip install -r requirements.txt
   ```

## Running the Application

Double-click `windows/run.bat` or run:
```powershell
python app.py
```

### In the Application:
1. **Audio Output Routing**: In the "Audio Output Routing" dropdown, select your Bluetooth Earphones / Headset (tagged with `🎧 [Bluetooth/Headset] [WASAPI]`).
2. **Phone Pairing**: Note the **Local IP Address** (e.g. `192.168.1.15`) and the **Pairing Code** (default: `1234`), or scan the displayed QR code.
3. Click **Start Audio Stream**.

---

## Testing Without an Android Device

You can test the Windows receiver immediately using the built-in test audio streamer:
```powershell
python scripts/test_phone_sender.py 127.0.0.1 1234
```
You should hear a stereo test tone playing through your selected Bluetooth earphones with live volume meters and latency metrics updating in the VBridge window.
