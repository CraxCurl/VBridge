import customtkinter as ctk
import tkinter as tk
from PIL import Image, ImageTk
import qrcode
import threading
import time
import logging
import sys
import os

try:
    from audio_player import AudioPlayer
    from audio_receiver import AudioReceiver
    from startup_manager import StartupManager
    from config_manager import ConfigManager
except ImportError:
    from windows.audio_player import AudioPlayer
    from windows.audio_receiver import AudioReceiver
    from windows.startup_manager import StartupManager
    from windows.config_manager import ConfigManager

try:
    import pystray
    from pystray import MenuItem as TrayItem
    HAS_PYSTRAY = True
except ImportError:
    HAS_PYSTRAY = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(threadName)s) %(message)s"
)
logger = logging.getLogger("VBridge.App")

# Material Design 3 / Google Dark Theme Color Palette
GOOGLE_COLORS = {
    "bg_main": "#131314",             # Google surface dark (AMOLED / deep blackish)
    "surface": "#1E1F20",             # Surface container
    "surface_high": "#28292A",        # Surface container high
    "surface_highest": "#333537",     # Surface container highest / input fields
    "outline": "#444746",             # Subtle border outline
    "primary": "#A8C7FA",             # Google Material You Blue accent
    "primary_text": "#041E49",        # On primary button text
    "secondary_container": "#374967", # Soft pill background
    "text_high": "#E3E3E3",           # High emphasis text
    "text_med": "#C4C7C5",            # Medium emphasis text
    "text_muted": "#8E918F",          # Caption / subtle text
    "status_green": "#6DD58C",        # Connected / active green
    "status_green_bg": "#1C3725",     # Pill green background
    "status_red": "#F28B82",          # Disconnected red
    "status_red_bg": "#3B1C1A",       # Pill red background
    "status_amber": "#FDE293",        # Connecting amber
    "accent_mint": "#A8E8BC",         # Audio VU Left
    "accent_sky": "#7FCFFF",          # Audio VU Right
}

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class VBridgeApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Persistent configuration
        self.config = ConfigManager()

        self.title("VBridge — Google Material Audio Relay")
        self.geometry("800x860")
        self.minsize(720, 780)
        self.configure(fg_color=GOOGLE_COLORS["bg_main"])

        # Window Icon
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.ico_path = os.path.join(self.script_dir, "assets", "app_icon.ico")
        self.png_path = os.path.join(self.script_dir, "assets", "app_icon.png")
        if not os.path.exists(self.ico_path):
            try:
                from generate_icon import generate_app_icon
                generate_app_icon(self.script_dir)
            except Exception:
                pass

        if os.path.exists(self.ico_path):
            try:
                self.iconbitmap(self.ico_path)
            except Exception as e:
                logger.debug(f"Could not set iconbitmap: {e}")

        # Audio engine and Receiver instances
        saved_vol = self.config.get("volume", 1.0)
        self.audio_player = AudioPlayer(sample_rate=48000, channels=2, buffer_size=480)
        self.audio_player.set_volume(saved_vol)
        self.audio_player.keep_alive_anti_sleep = self.config.get("keep_anti_sleep", True)

        self.audio_receiver = AudioReceiver(self.audio_player)
        saved_code = self.config.get("pairing_code", "1234")
        self.audio_receiver.set_pairing_code(saved_code)

        # Connect receiver callbacks
        self.audio_receiver.on_client_connected = self._on_client_connected
        self.audio_receiver.on_client_disconnected = self._on_client_disconnected
        self.audio_receiver.on_stream_status_change = self._on_stream_status_change

        self.device_map = {}  # display_name -> device_id
        self.is_streaming_active = False

        self._build_ui()

        # System tray icon
        self.tray_icon = None
        self._init_tray()

        # Start receiver servers in background
        self.audio_receiver.start()
        # Start audio player immediately to lock Bluetooth output and keep-alive
        self.audio_player.start()

        # Start periodic UI refresh timer (audio meter, latency, device list)
        self.after(40, self._update_metrics_loop)
        self.after(3000, self._periodic_device_check)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        # Top App Bar (Google Style)
        self.top_bar = ctk.CTkFrame(self, corner_radius=16, fg_color=GOOGLE_COLORS["surface"], border_width=1, border_color=GOOGLE_COLORS["outline"])
        self.top_bar.pack(fill="x", padx=20, pady=(18, 10))

        bar_inner = ctk.CTkFrame(self.top_bar, fg_color="transparent")
        bar_inner.pack(fill="x", padx=20, pady=16)

        # Icon and Title
        title_box = ctk.CTkFrame(bar_inner, fg_color="transparent")
        title_box.pack(side="left")

        lbl_app = ctk.CTkLabel(
            title_box,
            text="🎧 VBridge Audio Relay",
            font=ctk.CTkFont(family="Segoe UI", size=21, weight="bold"),
            text_color=GOOGLE_COLORS["text_high"]
        )
        lbl_app.pack(anchor="w")

        lbl_sub = ctk.CTkLabel(
            title_box,
            text="Phone  ➜  Laptop Receiver  ➜  Bluetooth Earbuds",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=GOOGLE_COLORS["text_med"]
        )
        lbl_sub.pack(anchor="w", pady=(2, 0))

        # Right-side action controls
        controls_right = ctk.CTkFrame(bar_inner, fg_color="transparent")
        controls_right.pack(side="right")

        # Minimize to Tray Button
        self.btn_tray = ctk.CTkButton(
            controls_right,
            text="🗕 Tray",
            width=70,
            height=32,
            corner_radius=16,
            fg_color=GOOGLE_COLORS["surface_highest"],
            hover_color=GOOGLE_COLORS["outline"],
            text_color=GOOGLE_COLORS["text_high"],
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self._minimize_to_tray
        )
        self.btn_tray.pack(side="right", padx=(6, 0))

        # Live Hub Status Badge
        self.badge_hub = ctk.CTkFrame(controls_right, corner_radius=20, fg_color=GOOGLE_COLORS["surface_highest"], border_width=1, border_color=GOOGLE_COLORS["outline"])
        self.badge_hub.pack(side="right", padx=4)

        self.lbl_hub_status = ctk.CTkLabel(
            self.badge_hub,
            text="● RECEIVER READY",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=GOOGLE_COLORS["primary"]
        )
        self.lbl_hub_status.pack(padx=14, pady=6)

        # Main scrollable container
        self.main_container = ctk.CTkScrollableFrame(self, corner_radius=16, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True, padx=16, pady=(0, 10))

        # 1. Google Pill Status & Metrics Card
        self._build_status_card()

        # 2. Output Device Selection Card
        self._build_device_card()

        # 3. Audio Controls & Live VU Meters Card
        self._build_controls_card()

        # 4. Phone Pairing & Connection Details Card
        self._build_pairing_card()

    def _build_status_card(self):
        card = ctk.CTkFrame(
            self.main_container,
            corner_radius=16,
            fg_color=GOOGLE_COLORS["surface"],
            border_width=1,
            border_color=GOOGLE_COLORS["outline"]
        )
        card.pack(fill="x", pady=6, padx=4)

        header = ctk.CTkLabel(
            card,
            text="LIVE CONNECTION & LATENCY STATUS",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=GOOGLE_COLORS["text_muted"]
        )
        header.pack(anchor="w", padx=18, pady=(14, 8))

        grid = ctk.CTkFrame(card, fg_color="transparent")
        grid.pack(fill="x", padx=14, pady=(0, 14))
        grid.columnconfigure((0, 1), weight=1)

        # 1. Bluetooth Earbuds Output Status Box
        self.bt_frame = ctk.CTkFrame(grid, fg_color=GOOGLE_COLORS["surface_high"], corner_radius=12, border_width=1, border_color=GOOGLE_COLORS["outline"])
        self.bt_frame.grid(row=0, column=0, padx=4, pady=4, sticky="ew")
        ctk.CTkLabel(self.bt_frame, text="🎧 Bluetooth Output (Laptop ➔ Earbuds)", font=ctk.CTkFont(family="Segoe UI", size=11), text_color=GOOGLE_COLORS["text_med"]).pack(pady=(10, 2))
        self.lbl_bt_status = ctk.CTkLabel(
            self.bt_frame,
            text="🟢 Output Ready",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=GOOGLE_COLORS["status_green"]
        )
        self.lbl_bt_status.pack(pady=(0, 10))

        # 2. Phone Wi-Fi Link Box
        self.p_frame = ctk.CTkFrame(grid, fg_color=GOOGLE_COLORS["surface_high"], corner_radius=12, border_width=1, border_color=GOOGLE_COLORS["outline"])
        self.p_frame.grid(row=0, column=1, padx=4, pady=4, sticky="ew")
        ctk.CTkLabel(self.p_frame, text="📱 Phone Wi-Fi Link (Phone ➔ Laptop)", font=ctk.CTkFont(family="Segoe UI", size=11), text_color=GOOGLE_COLORS["text_med"]).pack(pady=(10, 2))
        self.lbl_phone_status = ctk.CTkLabel(
            self.p_frame,
            text="🔴 Phone Disconnected",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=GOOGLE_COLORS["status_red"]
        )
        self.lbl_phone_status.pack(pady=(0, 10))

        # 3. Audio Stream Status Pill Box
        self.s_frame = ctk.CTkFrame(grid, fg_color=GOOGLE_COLORS["surface_high"], corner_radius=12, border_width=1, border_color=GOOGLE_COLORS["outline"])
        self.s_frame.grid(row=1, column=0, padx=4, pady=4, sticky="ew")
        ctk.CTkLabel(self.s_frame, text="Audio Stream State", font=ctk.CTkFont(family="Segoe UI", size=11), text_color=GOOGLE_COLORS["text_med"]).pack(pady=(10, 2))
        self.lbl_stream_status = ctk.CTkLabel(
            self.s_frame,
            text="⏹ Standby",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=GOOGLE_COLORS["text_muted"]
        )
        self.lbl_stream_status.pack(pady=(0, 10))

        # 4. Latency Metric Pill Box
        self.l_frame = ctk.CTkFrame(grid, fg_color=GOOGLE_COLORS["surface_high"], corner_radius=12, border_width=1, border_color=GOOGLE_COLORS["outline"])
        self.l_frame.grid(row=1, column=1, padx=4, pady=4, sticky="ew")
        ctk.CTkLabel(self.l_frame, text="Network Latency (RTT)", font=ctk.CTkFont(family="Segoe UI", size=11), text_color=GOOGLE_COLORS["text_med"]).pack(pady=(10, 2))
        self.lbl_latency = ctk.CTkLabel(
            self.l_frame,
            text="-- ms",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=GOOGLE_COLORS["status_green"]
        )
        self.lbl_latency.pack(pady=(0, 10))

    def _build_device_card(self):
        card = ctk.CTkFrame(
            self.main_container,
            corner_radius=16,
            fg_color=GOOGLE_COLORS["surface"],
            border_width=1,
            border_color=GOOGLE_COLORS["outline"]
        )
        card.pack(fill="x", pady=6, padx=4)

        header = ctk.CTkLabel(
            card,
            text="AUDIO OUTPUT ROUTING",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=GOOGLE_COLORS["text_muted"]
        )
        header.pack(anchor="w", padx=18, pady=(14, 4))

        sub = ctk.CTkLabel(
            card,
            text="Select your connected Bluetooth Earphones / Headphones or Windows playback device:",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=GOOGLE_COLORS["text_med"]
        )
        sub.pack(anchor="w", padx=18, pady=(0, 10))

        dev_row = ctk.CTkFrame(card, fg_color="transparent")
        dev_row.pack(fill="x", padx=18, pady=(0, 8))

        self.device_combo = ctk.CTkOptionMenu(
            dev_row,
            values=["Searching for output devices..."],
            command=self._on_device_selected,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            height=40,
            corner_radius=20,
            fg_color=GOOGLE_COLORS["surface_highest"],
            button_color=GOOGLE_COLORS["outline"],
            button_hover_color="#5E6266",
            text_color=GOOGLE_COLORS["text_high"]
        )
        self.device_combo.pack(side="left", fill="x", expand=True, padx=(0, 10))

        btn_refresh = ctk.CTkButton(
            dev_row,
            text="🔄 Refresh",
            width=100,
            height=40,
            corner_radius=20,
            command=lambda: self.refresh_devices(force_reinit=True),
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color=GOOGLE_COLORS["surface_high"],
            text_color=GOOGLE_COLORS["text_high"],
            hover_color=GOOGLE_COLORS["surface_highest"],
            border_width=1,
            border_color=GOOGLE_COLORS["outline"]
        )
        btn_refresh.pack(side="right")

        # Helpful mixing tip banner
        tip_frame = ctk.CTkFrame(card, fg_color=GOOGLE_COLORS["surface_high"], corner_radius=10, border_width=1, border_color=GOOGLE_COLORS["outline"])
        tip_frame.pack(fill="x", padx=18, pady=(0, 10))
        ctk.CTkLabel(
            tip_frame,
            text="💡 Tip: To hear Laptop videos (YouTube/Games) and Phone audio simultaneously in your earbuds,\nclick the Speaker icon on your Windows Taskbar (bottom-right) and set output to your Earbuds.",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=GOOGLE_COLORS["primary"],
            justify="left"
        ).pack(anchor="w", padx=12, pady=8)

        # Anti-sleep & active endpoint info row
        opt_row = ctk.CTkFrame(card, fg_color="transparent")
        opt_row.pack(fill="x", padx=18, pady=(0, 8))

        self.lbl_device_info = ctk.CTkLabel(
            opt_row,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=GOOGLE_COLORS["primary"]
        )
        self.lbl_device_info.pack(side="left")

        self.chk_anti_sleep = ctk.CTkCheckBox(
            opt_row,
            text="🔒 Keep Bluetooth Awake",
            command=self._on_anti_sleep_toggled,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=GOOGLE_COLORS["text_high"],
            fg_color=GOOGLE_COLORS["primary"],
            border_color=GOOGLE_COLORS["outline"]
        )
        if self.config.get("keep_anti_sleep", True):
            self.chk_anti_sleep.select()
        else:
            self.chk_anti_sleep.deselect()
        self.chk_anti_sleep.pack(side="right")

        # Windows Startup and Background row
        sys_row = ctk.CTkFrame(card, fg_color="transparent")
        sys_row.pack(fill="x", padx=18, pady=(0, 12))

        self.chk_startup = ctk.CTkCheckBox(
            sys_row,
            text="🚀 Start Automatically with Windows (Always Ready in Background)",
            command=self._on_startup_toggled,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=GOOGLE_COLORS["primary"],
            fg_color=GOOGLE_COLORS["primary"],
            border_color=GOOGLE_COLORS["outline"]
        )
        is_startup = StartupManager.is_startup_enabled()
        if is_startup:
            self.chk_startup.select()
        else:
            self.chk_startup.deselect()
        self.chk_startup.pack(side="left")

        self.refresh_devices()

    def _build_controls_card(self):
        card = ctk.CTkFrame(
            self.main_container,
            corner_radius=16,
            fg_color=GOOGLE_COLORS["surface"],
            border_width=1,
            border_color=GOOGLE_COLORS["outline"]
        )
        card.pack(fill="x", pady=6, padx=4)

        header = ctk.CTkLabel(
            card,
            text="PLAYBACK CONTROLS & LIVE METERS",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=GOOGLE_COLORS["text_muted"]
        )
        header.pack(anchor="w", padx=18, pady=(14, 6))

        # Main Stream Action Button (Material You Pill)
        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.pack(fill="x", padx=18, pady=6)

        self.btn_toggle_stream = ctk.CTkButton(
            btn_frame,
            text="▶ Start Audio Stream",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            height=44,
            corner_radius=22,
            command=self._toggle_stream,
            fg_color=GOOGLE_COLORS["primary"],
            text_color=GOOGLE_COLORS["primary_text"],
            hover_color="#BFD8FF"
        )
        self.btn_toggle_stream.pack(fill="x")

        # Volume Slider and Mute Checkbox
        vol_frame = ctk.CTkFrame(card, fg_color="transparent")
        vol_frame.pack(fill="x", padx=18, pady=(10, 6))

        ctk.CTkLabel(
            vol_frame,
            text="Volume:",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=GOOGLE_COLORS["text_med"]
        ).pack(side="left", padx=(0, 8))

        self.slider_vol = ctk.CTkSlider(
            vol_frame,
            from_=0.0,
            to=1.5,
            number_of_steps=30,
            command=self._on_volume_changed,
            button_color=GOOGLE_COLORS["primary"],
            progress_color=GOOGLE_COLORS["primary"],
            button_hover_color="#BFD8FF",
            fg_color=GOOGLE_COLORS["surface_highest"]
        )
        self.slider_vol.set(1.0)
        self.slider_vol.pack(side="left", fill="x", expand=True, padx=8)

        self.lbl_vol_val = ctk.CTkLabel(
            vol_frame,
            text="100%",
            width=45,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=GOOGLE_COLORS["text_high"]
        )
        self.lbl_vol_val.pack(side="left", padx=4)

        self.chk_mute = ctk.CTkCheckBox(
            vol_frame,
            text="Mute",
            command=self._on_mute_toggled,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=GOOGLE_COLORS["text_high"],
            fg_color=GOOGLE_COLORS["status_red"],
            hover_color="#E06A61",
            border_color=GOOGLE_COLORS["outline"]
        )
        self.chk_mute.pack(side="right", padx=(8, 0))

        # Audio Level Meters (L & R Channels)
        meter_frame = ctk.CTkFrame(
            card,
            fg_color=GOOGLE_COLORS["surface_high"],
            corner_radius=12,
            border_width=1,
            border_color=GOOGLE_COLORS["outline"]
        )
        meter_frame.pack(fill="x", padx=18, pady=(10, 16))

        m_l_row = ctk.CTkFrame(meter_frame, fg_color="transparent")
        m_l_row.pack(fill="x", padx=14, pady=(12, 4))
        ctk.CTkLabel(m_l_row, text="L", width=22, font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=GOOGLE_COLORS["accent_mint"]).pack(side="left")
        self.meter_bar_l = ctk.CTkProgressBar(
            m_l_row,
            orientation="horizontal",
            height=10,
            corner_radius=5,
            progress_color=GOOGLE_COLORS["accent_mint"],
            fg_color=GOOGLE_COLORS["surface_highest"]
        )
        self.meter_bar_l.set(0.0)
        self.meter_bar_l.pack(side="left", fill="x", expand=True, padx=8)

        m_r_row = ctk.CTkFrame(meter_frame, fg_color="transparent")
        m_r_row.pack(fill="x", padx=14, pady=(4, 12))
        ctk.CTkLabel(m_r_row, text="R", width=22, font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=GOOGLE_COLORS["accent_sky"]).pack(side="left")
        self.meter_bar_r = ctk.CTkProgressBar(
            m_r_row,
            orientation="horizontal",
            height=10,
            corner_radius=5,
            progress_color=GOOGLE_COLORS["accent_sky"],
            fg_color=GOOGLE_COLORS["surface_highest"]
        )
        self.meter_bar_r.set(0.0)
        self.meter_bar_r.pack(side="left", fill="x", expand=True, padx=8)

    def _build_pairing_card(self):
        card = ctk.CTkFrame(
            self.main_container,
            corner_radius=16,
            fg_color=GOOGLE_COLORS["surface"],
            border_width=1,
            border_color=GOOGLE_COLORS["outline"]
        )
        card.pack(fill="x", pady=6, padx=4)

        header = ctk.CTkLabel(
            card,
            text="PHONE PAIRING & WI-FI CONNECTION",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=GOOGLE_COLORS["text_muted"]
        )
        header.pack(anchor="w", padx=18, pady=(14, 6))

        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(fill="x", padx=18, pady=(0, 16))

        left_info = ctk.CTkFrame(content, fg_color="transparent")
        left_info.pack(side="left", fill="both", expand=True, padx=(0, 12))

        all_ips = self.audio_receiver.get_all_local_ips()
        self.selected_ip = all_ips[0]

        # IP / Hotspot selection row
        ip_row = ctk.CTkFrame(left_info, fg_color="transparent")
        ip_row.pack(fill="x", pady=(2, 6))
        ctk.CTkLabel(
            ip_row,
            text="📡 Laptop IP / Hotspot:",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=GOOGLE_COLORS["text_med"]
        ).pack(side="left", padx=(0, 8))

        self.combo_ip = ctk.CTkOptionMenu(
            ip_row,
            values=all_ips,
            command=self._on_ip_selected,
            font=ctk.CTkFont(family="Consolas", size=12),
            height=32,
            corner_radius=16,
            fg_color=GOOGLE_COLORS["surface_highest"],
            button_color=GOOGLE_COLORS["outline"],
            text_color=GOOGLE_COLORS["text_high"]
        )
        self.combo_ip.set(self.selected_ip)
        self.combo_ip.pack(side="left", fill="x", expand=True)

        info_lines = [
            f"🔌 Control Port: {self.audio_receiver.tcp_port} (TCP)",
            f"🔊 Audio Port:   {self.audio_receiver.udp_port} (UDP)",
        ]
        for line in info_lines:
            ctk.CTkLabel(
                left_info,
                text=line,
                font=ctk.CTkFont(family="Consolas", size=12),
                text_color=GOOGLE_COLORS["text_high"],
                anchor="w"
            ).pack(fill="x", pady=2)

        # Pairing Code row
        code_frame = ctk.CTkFrame(
            left_info,
            fg_color=GOOGLE_COLORS["surface_high"],
            corner_radius=10,
            border_width=1,
            border_color=GOOGLE_COLORS["outline"]
        )
        code_frame.pack(fill="x", pady=(8, 6))
        ctk.CTkLabel(
            code_frame,
            text="Pairing Code:",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=GOOGLE_COLORS["text_med"]
        ).pack(side="left", padx=12, pady=8)

        self.entry_code = ctk.CTkEntry(
            code_frame,
            width=90,
            height=32,
            corner_radius=8,
            font=ctk.CTkFont(family="Consolas", size=13, weight="bold"),
            fg_color=GOOGLE_COLORS["surface_highest"],
            border_color=GOOGLE_COLORS["outline"],
            text_color=GOOGLE_COLORS["text_high"]
        )
        self.entry_code.insert(0, self.audio_receiver.pairing_code)
        self.entry_code.pack(side="left", padx=6)

        btn_set_code = ctk.CTkButton(
            code_frame,
            text="Update Code",
            width=95,
            height=32,
            corner_radius=16,
            command=self._on_update_code,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color=GOOGLE_COLORS["surface_highest"],
            hover_color="#43464A",
            text_color=GOOGLE_COLORS["text_high"]
        )
        btn_set_code.pack(side="left", padx=6)

        ctk.CTkLabel(
            left_info,
            text="Scan this QR code with the Android companion app to connect instantly:",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=GOOGLE_COLORS["text_muted"]
        ).pack(anchor="w", pady=(8, 0))

        # QR Code Display Container (Clean Google White Plate)
        self.qr_frame = ctk.CTkFrame(
            content,
            width=140,
            height=140,
            fg_color="#FFFFFF",
            corner_radius=12
        )
        self.qr_frame.pack(side="right", padx=6)
        self.lbl_qr = ctk.CTkLabel(self.qr_frame, text="")
        self.lbl_qr.pack(padx=4, pady=4)

        self._generate_qr_code(self.selected_ip, self.audio_receiver.tcp_port, self.audio_receiver.pairing_code)

    def _on_ip_selected(self, new_ip):
        self.selected_ip = new_ip
        self._generate_qr_code(self.selected_ip, self.audio_receiver.tcp_port, self.audio_receiver.pairing_code)

    def _generate_qr_code(self, ip: str, port: int, code: str):
        try:
            payload = f"vbridge://{ip}:{port}?code={code}"
            qr = qrcode.QRCode(box_size=3, border=1)
            qr.add_data(payload)
            qr.make(fit=True)
            img = qr.make_image(fill_color="#131314", back_color="#FFFFFF")
            ctk_img = ctk.CTkImage(light_image=img.get_image(), dark_image=img.get_image(), size=(128, 128))
            self.lbl_qr.configure(image=ctk_img)
        except Exception as e:
            logger.warning(f"Could not render QR code: {e}")
            self.lbl_qr.configure(text="QR Unavailable")

    def _on_update_code(self):
        new_code = self.entry_code.get().strip()
        self.audio_receiver.set_pairing_code(new_code)
        self.config.set("pairing_code", new_code)
        self._generate_qr_code(self.selected_ip, self.audio_receiver.tcp_port, new_code)

    def refresh_devices(self, force_reinit=False):
        """Enumerate output devices and populate dropdown menu."""
        devices = AudioPlayer.get_output_devices(force_reinit=force_reinit)
        prev_selection = self.device_combo.get()
        self.device_map.clear()
        display_names = []
        bt_wasapi_name = None
        bt_any_name = None
        default_name = None

        for dev in devices:
            if dev["is_bluetooth"]:
                tag = " [WASAPI - Recommended]" if dev["is_wasapi"] else f" [{dev['hostapi']}]"
                name = f"🎧 {dev['name']}{tag}"
            else:
                tag = " [WASAPI]" if dev["is_wasapi"] else f" [{dev['hostapi']}]"
                def_tag = " ⭐ [Default]" if dev["is_default"] else ""
                name = f"🔊 {dev['name']}{tag}{def_tag}"

            self.device_map[name] = dev["id"]
            display_names.append(name)

            if dev["is_bluetooth"] and dev["is_wasapi"] and bt_wasapi_name is None:
                bt_wasapi_name = name
            elif dev["is_bluetooth"] and bt_any_name is None:
                bt_any_name = name
            elif dev["is_default"] and default_name is None:
                default_name = name

        if not display_names:
            display_names = ["No audio output devices found"]
            selected_name = display_names[0]
        else:
            # Preserve existing user selection if still valid; otherwise prefer BT then Default
            if prev_selection in self.device_map:
                selected_name = prev_selection
            else:
                selected_name = bt_wasapi_name or bt_any_name or default_name or display_names[0]

        self.device_combo.configure(values=display_names)
        self.device_combo.set(selected_name)
        self._on_device_selected(selected_name)

    def _on_startup_toggled(self):
        enabled = (self.chk_startup.get() == 1)
        StartupManager.set_startup_enabled(enabled)
        self.config.set("launch_at_startup", enabled)
        logger.info(f"Windows Autorun set to: {enabled}")

    def _on_anti_sleep_toggled(self):
        enabled = (self.chk_anti_sleep.get() == 1)
        self.audio_player.keep_alive_anti_sleep = enabled
        self.config.set("keep_anti_sleep", enabled)
        logger.info(f"Bluetooth Anti-Sleep Keep-Alive set to: {enabled}")

    def _on_device_selected(self, choice):
        dev_id = self.device_map.get(choice)
        if dev_id is not None:
            self.audio_player.set_device(dev_id)
            self.config.set("selected_device_name", choice)
            clean_name = choice.split('[')[0].strip()
            self.lbl_device_info.configure(text=f"Active Endpoint: Device #{dev_id} ({clean_name})")
            is_bt = "Bluetooth" in choice or "Earbuds" in choice or "Headset" in choice or "Air" in choice or "Airdopes" in choice
            if is_bt:
                self.lbl_bt_status.configure(
                    text=f"🟢 {clean_name}",
                    text_color=GOOGLE_COLORS["status_green"]
                )
            else:
                self.lbl_bt_status.configure(
                    text=f"🟢 {clean_name}",
                    text_color=GOOGLE_COLORS["text_high"]
                )

    def _periodic_device_check(self):
        """Detect if Bluetooth devices or output hardware were plugged/unplugged."""
        try:
            if self.audio_player.selected_device_id is not None:
                curr_id = self.audio_player.selected_device_id
                devices = AudioPlayer.get_output_devices()
                valid_ids = [d["id"] for d in devices]
                if curr_id not in valid_ids:
                    logger.warning(f"Previously selected device #{curr_id} is no longer available. Re-enumerating...")
                    self.refresh_devices()
        except Exception as e:
            logger.debug(f"Device check error: {e}")
        finally:
            self.after(3000, self._periodic_device_check)

    def _toggle_stream(self):
        if not self.is_streaming_active:
            self.audio_player.start()
            self.is_streaming_active = True
            self.lbl_stream_status.configure(text="🟢 Active (Listening)", text_color=GOOGLE_COLORS["status_green"])
            self.btn_toggle_stream.configure(
                text="⏹ Stop Audio Stream",
                fg_color=GOOGLE_COLORS["status_red"],
                hover_color="#E06A61",
                text_color="#1E1F20"
            )
        else:
            self.audio_player.stop()
            self.is_streaming_active = False
            self.lbl_stream_status.configure(text="⏹ Standby", text_color=GOOGLE_COLORS["text_muted"])
            self.btn_toggle_stream.configure(
                text="▶ Start Audio Stream",
                fg_color=GOOGLE_COLORS["primary"],
                hover_color="#BFD8FF",
                text_color=GOOGLE_COLORS["primary_text"]
            )

    def _on_volume_changed(self, val):
        vol = float(val)
        self.audio_player.set_volume(vol)
        self.config.set("volume", vol)
        self.lbl_vol_val.configure(text=f"{int(vol * 100)}%")

    def _on_mute_toggled(self):
        muted = (self.chk_mute.get() == 1)
        self.audio_player.set_mute(muted)

    def _on_client_connected(self, device_name, ip):
        self.after(0, lambda: self.lbl_phone_status.configure(
            text=f"🟢 {device_name}",
            text_color=GOOGLE_COLORS["status_green"]
        ))
        self.after(0, lambda: self.lbl_hub_status.configure(
            text="● STREAMING READY",
            text_color=GOOGLE_COLORS["status_green"]
        ))

    def _on_client_disconnected(self):
        self.after(0, lambda: self.lbl_phone_status.configure(
            text="🔴 Phone Disconnected",
            text_color=GOOGLE_COLORS["status_red"]
        ))
        self.after(0, lambda: self.lbl_hub_status.configure(
            text="● RECEIVER READY",
            text_color=GOOGLE_COLORS["primary"]
        ))
        self.after(0, lambda: self.lbl_latency.configure(text="-- ms"))

    def _on_stream_status_change(self, is_active):
        self.is_streaming_active = is_active
        if is_active:
            self.after(0, lambda: self.lbl_stream_status.configure(text="🟢 Streaming", text_color=GOOGLE_COLORS["status_green"]))
            self.after(0, lambda: self.btn_toggle_stream.configure(
                text="⏹ Stop Audio Stream",
                fg_color=GOOGLE_COLORS["status_red"],
                hover_color="#E06A61",
                text_color="#1E1F20"
            ))
        else:
            self.after(0, lambda: self.lbl_stream_status.configure(text="⏹ Standby", text_color=GOOGLE_COLORS["text_muted"]))
            self.after(0, lambda: self.btn_toggle_stream.configure(
                text="▶ Start Audio Stream",
                fg_color=GOOGLE_COLORS["primary"],
                hover_color="#BFD8FF",
                text_color=GOOGLE_COLORS["primary_text"]
            ))

    def _update_metrics_loop(self):
        # Update audio meters
        lvl_l = min(1.0, self.audio_player.peak_level_left)
        lvl_r = min(1.0, self.audio_player.peak_level_right)
        self.meter_bar_l.set(lvl_l)
        self.meter_bar_r.set(lvl_r)

        # Update latency
        if self.audio_receiver.client_connected or self.audio_receiver.active_stream:
            rtt = self.audio_receiver.rtt_latency_ms
            if rtt > 0:
                self.lbl_latency.configure(text=f"{rtt:.1f} ms")
            else:
                self.lbl_latency.configure(text="< 4 ms")

        self.after(40, self._update_metrics_loop)

    def _init_tray(self):
        if not HAS_PYSTRAY:
            logger.info("pystray not installed; skipping system tray icon.")
            return

        try:
            if os.path.exists(self.png_path):
                tray_img = Image.open(self.png_path)
            elif os.path.exists(self.ico_path):
                tray_img = Image.open(self.ico_path)
            else:
                tray_img = Image.new("RGBA", (64, 64), (168, 199, 250, 255))

            menu = pystray.Menu(
                TrayItem("🎧 Open VBridge", self._show_window, default=True),
                TrayItem("⚡ Start/Stop Stream", lambda icon, item: self.after(0, self._toggle_stream)),
                pystray.Menu.SEPARATOR,
                TrayItem("❌ Exit VBridge", self._quit_app)
            )

            self.tray_icon = pystray.Icon("VBridge", tray_img, "VBridge — Audio Relay", menu=menu)
            tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True, name="VBridge-TrayThread")
            tray_thread.start()
            logger.info("Windows System Tray icon initialized successfully.")
        except Exception as e:
            logger.warning(f"Could not initialize system tray: {e}")

    def _minimize_to_tray(self):
        logger.info("Minimizing VBridge to Windows System Tray...")
        self.withdraw()
        if self.tray_icon is not None:
            try:
                self.tray_icon.notify("VBridge is running in the system tray. Click to reopen.", "VBridge Audio Relay")
            except Exception:
                pass

    def _show_window(self, icon=None, item=None):
        self.after(0, self._restore_window)

    def _restore_window(self):
        self.deiconify()
        self.state("normal")
        self.lift()
        self.focus_force()

    def _on_close(self):
        # When user clicks the 'X' button, minimize to system tray if available
        if self.tray_icon is not None:
            self._minimize_to_tray()
        else:
            self._quit_app()

    def _quit_app(self, icon=None, item=None):
        logger.info("Exiting VBridge Application...")
        try:
            if self.tray_icon is not None:
                self.tray_icon.stop()
        except Exception:
            pass

        try:
            self.audio_receiver.stop()
            self.audio_player.stop()
        except Exception:
            pass

        self.after(0, self.destroy)
        sys.exit(0)


if __name__ == "__main__":
    app = VBridgeApp()
    app.mainloop()

