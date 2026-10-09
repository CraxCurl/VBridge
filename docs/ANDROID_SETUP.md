# Android Setup & Installation Guide

## Prerequisites
- Android 10 (API level 29) or higher.
- Phone and Windows laptop connected to the **same local Wi-Fi network** (or phone connected to laptop's Mobile Hotspot).
- Android Studio (Hedgehog / Iguana / Jellyfish or later) or Gradle command line.

## Building and Installing

### Option 1: Using Android Studio (Recommended)
1. Launch Android Studio.
2. Select **Open** and select the `VBridge/android` folder.
3. Allow Gradle to sync dependencies.
4. Connect your Android phone via USB with USB Debugging enabled.
5. Click **Run 'app'** (Green Play button).

### Option 2: Using Gradle Command Line
From the `VBridge/android` directory:
```bash
# On Windows
gradlew.bat assembleDebug

# On macOS/Linux
./gradlew assembleDebug
```
The resulting APK will be located at:
`android/app/build/outputs/apk/debug/app-debug.apk`

Install the APK onto your device:
```bash
adb install android/app/build/outputs/apk/debug/app-debug.apk
```

---

## Using the Companion App

1. Launch **VBridge** on your Android phone.
2. Enter the **Laptop IP Address** and **Pairing Code** shown on the Windows VBridge application.
3. Tap **Connect to Laptop**.
4. Select **Internal System & Media Audio**.
5. Tap **▶ Start Audio Streaming**.
6. When prompted by Android with *"VBridge will start capturing everything that's displayed on your screen or played from your device"*, tap **Start now**.
7. Start playing music, videos, or games on your phone. The audio will stream through your laptop directly to your Bluetooth earphones!
