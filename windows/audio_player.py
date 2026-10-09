import sounddevice as sd
import numpy as np
import threading
import logging
import time

logger = logging.getLogger("VBridge.AudioPlayer")


class AudioRingBuffer:
    """
    Thread-safe Circular Ring Buffer for Float32 stereo audio samples.
    Delivers zero-latency, stutter-free playback without blocking.
    """

    def __init__(self, capacity_frames=96000, channels=2):
        self.channels = channels
        self.capacity = capacity_frames
        self.buffer = np.zeros((capacity_frames, channels), dtype=np.float32)
        self.write_pos = 0
        self.read_pos = 0
        self.available_frames = 0
        self.lock = threading.Lock()

    def write(self, data: np.ndarray):
        """Write 2D float32 numpy array [frames, channels] into ring buffer."""
        frames_to_write = len(data)
        if frames_to_write == 0:
            return

        with self.lock:
            # If incoming data exceeds capacity, keep newest
            if frames_to_write >= self.capacity:
                data = data[-self.capacity:]
                frames_to_write = self.capacity
                self.write_pos = 0
                self.read_pos = 0
                self.available_frames = 0

            # If writing causes overflow, advance read_pos to drop oldest samples
            if self.available_frames + frames_to_write > self.capacity:
                overflow = (self.available_frames + frames_to_write) - self.capacity
                self.read_pos = (self.read_pos + overflow) % self.capacity
                self.available_frames -= overflow

            # Copy data into circular buffer
            end_pos = self.write_pos + frames_to_write
            if end_pos <= self.capacity:
                self.buffer[self.write_pos:end_pos] = data
            else:
                first_part = self.capacity - self.write_pos
                second_part = frames_to_write - first_part
                self.buffer[self.write_pos:self.capacity] = data[:first_part]
                self.buffer[0:second_part] = data[first_part:]

            self.write_pos = (self.write_pos + frames_to_write) % self.capacity
            self.available_frames += frames_to_write

    def read(self, out_array: np.ndarray, frames_needed: int) -> int:
        """
        Read requested number of frames into out_array.
        Always outputs available frames immediately without locking out playback.
        """
        with self.lock:
            if self.available_frames == 0:
                return 0

            actual_frames = min(frames_needed, self.available_frames)
            end_pos = self.read_pos + actual_frames
            if end_pos <= self.capacity:
                out_array[:actual_frames] = self.buffer[self.read_pos:end_pos]
            else:
                first_part = self.capacity - self.read_pos
                second_part = actual_frames - first_part
                out_array[:first_part] = self.buffer[self.read_pos:self.capacity]
                out_array[first_part:actual_frames] = self.buffer[0:second_part]

            self.read_pos = (self.read_pos + actual_frames) % self.capacity
            self.available_frames -= actual_frames

            # If buffer builds up beyond 150ms (7200 frames), trim oldest to keep latency ultra-low
            if self.available_frames > 7200:
                excess = self.available_frames - 2880
                self.read_pos = (self.read_pos + excess) % self.capacity
                self.available_frames -= excess

            return actual_frames

    def get_available(self):
        with self.lock:
            return self.available_frames

    def clear(self):
        with self.lock:
            self.write_pos = 0
            self.read_pos = 0
            self.available_frames = 0


class AudioPlayer:
    """
    High-Fidelity Low-Latency WASAPI Audio Output Engine for VBridge.
    Supports Laptop Speakers, Realtek, FxSound, USB, and Bluetooth Earbuds.
    """

    def __init__(self, sample_rate=48000, channels=2, buffer_size=480):
        self.sample_rate = sample_rate
        self.channels = channels
        self.buffer_size = buffer_size  # 480 frames = 10ms block @ 48kHz
        self.stream = None
        self.selected_device_id = None
        self.selected_device_name = ""
        self.volume = 1.0
        self.is_muted = False
        self.is_playing = False
        self._lock = threading.Lock()

        # 96000 frames capacity = 2.0 second ring buffer
        self.ring_buffer = AudioRingBuffer(capacity_frames=96000, channels=channels)
        self.keep_alive_anti_sleep = True

        # Real-time metrics
        self.peak_level_left = 0.0
        self.peak_level_right = 0.0
        self.rms_level = 0.0
        self.underrun_count = 0
        self.total_frames_played = 0

    @staticmethod
    def get_output_devices(force_reinit=False):
        """
        Enumerate all audio output devices on Windows.
        Only re-initializes PortAudio backend when force_reinit=True (manual refresh)
        to prevent destroying active playback streams.
        """
        devices = []
        try:
            if force_reinit:
                try:
                    sd._terminate()
                    sd._initialize()
                except Exception as pe:
                    logger.debug(f"PortAudio re-init note: {pe}")

            device_list = sd.query_devices()
            host_apis = sd.query_hostapis()
            default_wasapi_out = -1

            for api in host_apis:
                if "WASAPI" in api.get("name", ""):
                    default_wasapi_out = api.get("default_output_device", -1)
                    break

            for idx, dev in enumerate(device_list):
                if dev.get("max_output_channels", 0) > 0:
                    hostapi_idx = dev.get("hostapi", 0)
                    hostapi_name = host_apis[hostapi_idx]["name"] if hostapi_idx < len(host_apis) else "Unknown"
                    name = dev.get("name", f"Device {idx}")
                    clean_name = name.strip()

                    # Ignore internal raw driver clutter or empty device names
                    if "@System32" in name or "@system32" in name or name.startswith("Output ") or "WDM-KS" in hostapi_name or clean_name == "Headphones ()" or clean_name == "Speakers ()":
                        continue

                    # Heuristic to detect bluetooth or headsets
                    is_bt = any(term in clean_name.lower() for term in [
                        "airbass", "airdopes", "bluetooth", "earbuds", "airpods", "buds",
                        "headset", "headphones", "hands-free", "tws", "wireless", "boat", "realme", "noise", "oneplus"
                    ])
                    is_default = (idx == default_wasapi_out) or (idx == sd.default.device[1])
                    is_wasapi = "WASAPI" in hostapi_name

                    devices.append({
                        "id": idx,
                        "name": clean_name,
                        "hostapi": hostapi_name,
                        "channels": dev.get("max_output_channels", 2),
                        "default_samplerate": dev.get("default_samplerate", 48000),
                        "is_default": is_default,
                        "is_bluetooth": is_bt,
                        "is_wasapi": is_wasapi
                    })

            # Sort: Bluetooth devices first (WASAPI > DirectSound > MME), then others
            devices.sort(key=lambda d: (
                not d["is_bluetooth"],
                not d["is_wasapi"],
                not d["is_default"],
                d["name"]
            ))
        except Exception as e:
            logger.error(f"Failed to query audio devices: {e}")
        return devices

    def set_device(self, device_id: int):
        """Switch audio output device seamlessly without interrupting stream."""
        with self._lock:
            self.selected_device_id = device_id
            try:
                dev_info = sd.query_devices(device_id)
                self.selected_device_name = dev_info.get("name", f"Device {device_id}")
                logger.info(f"Selected audio output device: [{device_id}] {self.selected_device_name}")
            except Exception as e:
                logger.warning(f"Could not inspect device {device_id}: {e}")
                self.selected_device_name = f"Device {device_id}"

            # Restart stream on the new device
            self._stop_stream_internal()
            self._start_stream_internal()
            self.is_playing = (self.stream is not None)

    def set_volume(self, volume: float):
        """Set playback gain (0.0 to 1.5)."""
        self.volume = max(0.0, min(1.5, volume))

    def set_mute(self, muted: bool):
        """Set mute state."""
        self.is_muted = muted

    def queue_pcm_data(self, pcm_bytes: bytes):
        """
        Directly convert and push raw 16-bit signed PCM bytes (Little Endian, Stereo)
        into the AudioRingBuffer with zero thread delay.
        """
        if not pcm_bytes or len(pcm_bytes) < 4:
            return

        try:
            aligned_len = len(pcm_bytes) - (len(pcm_bytes) % 4)
            if aligned_len <= 0:
                return

            # Convert 16-bit signed PCM to float32 [-1.0, 1.0]
            audio_int16 = np.frombuffer(pcm_bytes[:aligned_len], dtype=np.int16)
            audio_float = audio_int16.astype(np.float32) * (1.0 / 32768.0)

            if self.channels == 2:
                num_frames = len(audio_float) // 2
                audio_data = audio_float[:num_frames * 2].reshape(num_frames, 2)
            else:
                audio_data = audio_float.reshape(-1, 1)

            self.ring_buffer.write(audio_data)

            # Auto-start stream if not already active
            if not self.is_playing:
                self.start()

        except Exception as e:
            logger.error(f"Error processing PCM audio frame: {e}")

    def _audio_callback(self, outdata, frames, time_info, status):
        """
        WASAPI low-latency callback called directly by the Windows audio engine.
        Reads clean frames from the AudioRingBuffer with smooth volume and soft-limiting.
        """
        if status:
            if status.output_underflow:
                self.underrun_count += 1

        buffer = np.zeros((frames, self.channels), dtype=np.float32)
        read_frames = self.ring_buffer.read(buffer, frames)

        if read_frames < frames:
            missing = frames - read_frames
            if self.keep_alive_anti_sleep:
                dither = np.random.uniform(-1e-6, 1e-6, size=(missing, self.channels)).astype(np.float32)
                buffer[read_frames:] = dither
            else:
                buffer[read_frames:].fill(0.0)

        # Apply volume gain and soft limiting
        if self.is_muted:
            buffer.fill(0.0)
        else:
            if self.volume != 1.0:
                buffer *= self.volume
            np.clip(buffer, -1.0, 1.0, out=buffer)

        outdata[:] = buffer
        self.total_frames_played += frames

        # Calculate live peak metrics for UI meter
        try:
            if self.channels == 2:
                self.peak_level_left = float(np.max(np.abs(buffer[:, 0]))) if len(buffer) > 0 else 0.0
                self.peak_level_right = float(np.max(np.abs(buffer[:, 1]))) if len(buffer) > 0 else 0.0
                self.rms_level = float(np.sqrt(np.mean(buffer ** 2)))
            else:
                peak = float(np.max(np.abs(buffer))) if len(buffer) > 0 else 0.0
                self.peak_level_left = peak
                self.peak_level_right = peak
                self.rms_level = float(np.sqrt(np.mean(buffer ** 2)))
        except Exception:
            pass

    def start(self):
        """Start audio playback stream."""
        with self._lock:
            if self.is_playing and self.stream is not None:
                return
            self._start_stream_internal()
            self.is_playing = (self.stream is not None)

    def _start_stream_internal(self):
        """Open audio output stream with fallback protection."""
        device = self.selected_device_id
        extra_settings = None

        if device is not None:
            try:
                dev_info = sd.query_devices(device)
                host_apis = sd.query_hostapis()
                hostapi_idx = dev_info.get("hostapi", -1)
                if 0 <= hostapi_idx < len(host_apis):
                    if "WASAPI" in host_apis[hostapi_idx].get("name", ""):
                        extra_settings = sd.WasapiSettings(exclusive=False)
            except Exception:
                extra_settings = None

        # Attempt 1: Start on requested device
        try:
            self.stream = sd.OutputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="float32",
                device=device,
                blocksize=self.buffer_size,
                callback=self._audio_callback,
                extra_settings=extra_settings,
                latency='low'
            )
            self.stream.start()
            logger.info(f"Audio output active on device {device} ({self.selected_device_name})")
            return
        except Exception as e:
            logger.warning(f"Failed to open with low latency on device {device}: {e}. Retrying standard...")

        # Attempt 2: Try without WasapiSettings and automatic block size
        try:
            self.stream = sd.OutputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="float32",
                device=device,
                callback=self._audio_callback
            )
            self.stream.start()
            logger.info(f"Audio output active (standard) on device {device} ({self.selected_device_name})")
            return
        except Exception as e:
            logger.error(f"Could not open device {device}: {e}. Falling back to default output...")

        # Attempt 3: Fallback to system default output
        try:
            self.stream = sd.OutputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="float32",
                device=None,
                callback=self._audio_callback
            )
            self.stream.start()
            logger.info("Opened audio stream on Windows default output device.")
        except Exception as e2:
            logger.critical(f"Fatal: Could not initialize audio output: {e2}")
            self.stream = None

    def stop(self):
        """Stop audio playback and clear buffers."""
        with self._lock:
            if not self.is_playing:
                return
            self._stop_stream_internal()
            self.is_playing = False
            self.ring_buffer.clear()
            self.peak_level_left = 0.0
            self.peak_level_right = 0.0
            self.rms_level = 0.0

    def _stop_stream_internal(self):
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception as e:
                logger.debug(f"Error closing stream: {e}")
            finally:
                self.stream = None
