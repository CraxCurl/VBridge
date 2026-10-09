import sys
import os
import threading
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "windows")))
import audio_player as p
import audio_receiver as r
from test_phone_sender import run_test_sender

def main():
    player = p.AudioPlayer(sample_rate=48000, channels=2)
    devices = p.AudioPlayer.get_output_devices()
    print("Found devices:", len(devices))
    for d in devices:
        print(f" - [{d['id']}] {d['name']} ({d['hostapi']}) is_bt={d['is_bluetooth']}")
        
    bt_dev = next((d for d in devices if d['is_bluetooth'] and d['is_wasapi']), devices[0])
    print(f"\n[+] Selecting device: {bt_dev['name']} (#{bt_dev['id']})")
    player.set_device(bt_dev['id'])
    
    receiver = r.AudioReceiver(player)
    receiver.start()
    player.start()
    
    time.sleep(0.5)
    t = threading.Thread(target=run_test_sender, args=('127.0.0.1', '1234', 3))
    t.start()
    t.join()
    
    print("\n[+] Frames played successfully:", player.total_frames_played)
    print("[+] Buffer available:", player.ring_buffer.get_available())
    receiver.stop()
    player.stop()

if __name__ == "__main__":
    main()
