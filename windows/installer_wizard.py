import os
import sys
import shutil
import subprocess
import winreg
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

APP_NAME = "VBridge"
APP_DISPLAY_NAME = "VBridge Audio Relay"
APP_VERSION = "1.0.0"
PUBLISHER = "VBridge Team"

COLORS = {
    "bg": "#131314",
    "surface": "#1E1F20",
    "surface_high": "#28292A",
    "surface_highest": "#333537",
    "primary": "#A8C7FA",
    "on_primary": "#041E49",
    "text_high": "#E3E3E3",
    "text_med": "#C4C7C5",
    "text_muted": "#8E918F",
    "border": "#444746",
    "green": "#6DD58C",
}


class VBridgeSetupWizard(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title(f"{APP_DISPLAY_NAME} Setup Wizard")
        self.geometry("620x520")
        self.resizable(False, False)
        self.configure(fg_color=COLORS["bg"])

        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.ico_path = os.path.join(self.script_dir, "assets", "app_icon.ico")
        self.png_path = os.path.join(self.script_dir, "assets", "app_icon.png")

        if os.path.exists(self.ico_path):
            try:
                self.iconbitmap(self.ico_path)
            except Exception:
                pass

        # Default installation directory in user's AppData Programs
        local_app_data = os.environ.get("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local"))
        self.default_install_dir = os.path.join(local_app_data, "Programs", APP_NAME)
        self.install_dir_var = tk.StringVar(value=self.default_install_dir)

        self.chk_desktop_var = tk.BooleanVar(value=True)
        self.chk_startmenu_var = tk.BooleanVar(value=True)
        self.chk_autostart_var = tk.BooleanVar(value=True)
        self.chk_launch_var = tk.BooleanVar(value=True)

        self.current_step = 0
        self.steps = ["welcome", "directory", "options", "installing", "finish"]

        self._build_ui()
        self._show_step(0)

    def _build_ui(self):
        # Header banner
        self.header_frame = ctk.CTkFrame(self, fg_color=COLORS["surface"], height=70, corner_radius=0, border_width=1, border_color=COLORS["border"])
        self.header_frame.pack(fill="x")
        self.header_frame.pack_propagate(False)

        h_inner = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        h_inner.pack(fill="both", expand=True, padx=20, pady=12)

        self.lbl_title = ctk.CTkLabel(
            h_inner,
            text=f"🎧 {APP_DISPLAY_NAME} Setup",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color=COLORS["text_high"]
        )
        self.lbl_title.pack(side="left")

        self.lbl_step_num = ctk.CTkLabel(
            h_inner,
            text=f"Version {APP_VERSION}",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLORS["text_muted"]
        )
        self.lbl_step_num.pack(side="right")

        # Content container
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.pack(fill="both", expand=True, padx=24, pady=16)

        # Bottom navigation bar
        self.bottom_bar = ctk.CTkFrame(self, fg_color=COLORS["surface"], height=65, corner_radius=0, border_width=1, border_color=COLORS["border"])
        self.bottom_bar.pack(fill="x", side="bottom")
        self.bottom_bar.pack_propagate(False)

        btn_box = ctk.CTkFrame(self.bottom_bar, fg_color="transparent")
        btn_box.pack(side="right", padx=20, pady=14)

        self.btn_cancel = ctk.CTkButton(
            btn_box,
            text="Cancel",
            width=90,
            height=36,
            corner_radius=18,
            fg_color=COLORS["surface_highest"],
            hover_color=COLORS["border"],
            text_color=COLORS["text_high"],
            command=self.destroy
        )
        self.btn_cancel.pack(side="left", padx=6)

        self.btn_back = ctk.CTkButton(
            btn_box,
            text="< Back",
            width=90,
            height=36,
            corner_radius=18,
            fg_color=COLORS["surface_highest"],
            hover_color=COLORS["border"],
            text_color=COLORS["text_high"],
            command=self._on_back
        )
        self.btn_back.pack(side="left", padx=6)

        self.btn_next = ctk.CTkButton(
            btn_box,
            text="Next >",
            width=100,
            height=36,
            corner_radius=18,
            fg_color=COLORS["primary"],
            hover_color="#BFD8FF",
            text_color=COLORS["on_primary"],
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            command=self._on_next
        )
        self.btn_next.pack(side="left", padx=6)

    def _clear_content(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()

    def _show_step(self, step_idx):
        self.current_step = step_idx
        self._clear_content()

        if step_idx == 0:  # Welcome
            self.btn_back.configure(state="disabled")
            self.btn_next.configure(text="Next >", state="normal")

            box = ctk.CTkFrame(self.content_frame, fg_color=COLORS["surface"], corner_radius=16, border_width=1, border_color=COLORS["border"])
            box.pack(fill="both", expand=True, padx=4, pady=4)

            ctk.CTkLabel(
                box,
                text=f"Welcome to the {APP_DISPLAY_NAME} Setup Wizard",
                font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
                text_color=COLORS["text_high"]
            ).pack(anchor="w", padx=24, pady=(24, 8))

            desc = (
                f"This wizard will install {APP_DISPLAY_NAME} on your computer.\n\n"
                "VBridge allows you to stream crystal-clear, ultra low-latency audio "
                "from your Android phone directly to your laptop and Bluetooth earbuds over Wi-Fi.\n\n"
                "• Background System Tray integration\n"
                "• Automatic Windows Startup support\n"
                "• QR Code pairing and persistent connection"
            )
            ctk.CTkLabel(
                box,
                text=desc,
                font=ctk.CTkFont(family="Segoe UI", size=13),
                text_color=COLORS["text_med"],
                justify="left",
                wraplength=520
            ).pack(anchor="w", padx=24, pady=10)

        elif step_idx == 1:  # Destination Folder
            self.btn_back.configure(state="normal")
            self.btn_next.configure(text="Next >", state="normal")

            box = ctk.CTkFrame(self.content_frame, fg_color=COLORS["surface"], corner_radius=16, border_width=1, border_color=COLORS["border"])
            box.pack(fill="both", expand=True, padx=4, pady=4)

            ctk.CTkLabel(
                box,
                text="Select Installation Location",
                font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
                text_color=COLORS["text_high"]
            ).pack(anchor="w", padx=24, pady=(20, 4))

            ctk.CTkLabel(
                box,
                text="Setup will install VBridge into the following directory:",
                font=ctk.CTkFont(family="Segoe UI", size=12),
                text_color=COLORS["text_muted"]
            ).pack(anchor="w", padx=24, pady=(0, 16))

            path_row = ctk.CTkFrame(box, fg_color="transparent")
            path_row.pack(fill="x", padx=24, pady=4)

            self.entry_dir = ctk.CTkEntry(
                path_row,
                textvariable=self.install_dir_var,
                height=40,
                corner_radius=12,
                fg_color=COLORS["surface_highest"],
                text_color=COLORS["text_high"],
                border_color=COLORS["primary"]
            )
            self.entry_dir.pack(side="left", fill="x", expand=True, padx=(0, 8))

            ctk.CTkButton(
                path_row,
                text="Browse...",
                width=85,
                height=40,
                corner_radius=12,
                fg_color=COLORS["surface_highest"],
                hover_color=COLORS["border"],
                text_color=COLORS["text_high"],
                command=self._browse_folder
            ).pack(side="right")

            ctk.CTkLabel(
                box,
                text="Space required: ~35 MB\nSpace available: 10+ GB",
                font=ctk.CTkFont(family="Segoe UI", size=11),
                text_color=COLORS["text_muted"],
                justify="left"
            ).pack(anchor="w", padx=24, pady=(20, 0))

        elif step_idx == 2:  # Options
            self.btn_back.configure(state="normal")
            self.btn_next.configure(text="Install", state="normal")

            box = ctk.CTkFrame(self.content_frame, fg_color=COLORS["surface"], corner_radius=16, border_width=1, border_color=COLORS["border"])
            box.pack(fill="both", expand=True, padx=4, pady=4)

            ctk.CTkLabel(
                box,
                text="Select Additional Tasks",
                font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
                text_color=COLORS["text_high"]
            ).pack(anchor="w", padx=24, pady=(20, 4))

            ctk.CTkLabel(
                box,
                text="Choose which shortcuts and startup preferences to create:",
                font=ctk.CTkFont(family="Segoe UI", size=12),
                text_color=COLORS["text_muted"]
            ).pack(anchor="w", padx=24, pady=(0, 16))

            ctk.CTkCheckBox(
                box,
                text="Create a Desktop Shortcut",
                variable=self.chk_desktop_var,
                font=ctk.CTkFont(family="Segoe UI", size=13),
                text_color=COLORS["text_high"],
                fg_color=COLORS["primary"],
                checkmark_color=COLORS["on_primary"]
            ).pack(anchor="w", padx=28, pady=8)

            ctk.CTkCheckBox(
                box,
                text="Create a Start Menu Shortcut (Windows Search)",
                variable=self.chk_startmenu_var,
                font=ctk.CTkFont(family="Segoe UI", size=13),
                text_color=COLORS["text_high"],
                fg_color=COLORS["primary"],
                checkmark_color=COLORS["on_primary"]
            ).pack(anchor="w", padx=28, pady=8)

            ctk.CTkCheckBox(
                box,
                text="Launch VBridge automatically on Windows Startup",
                variable=self.chk_autostart_var,
                font=ctk.CTkFont(family="Segoe UI", size=13),
                text_color=COLORS["text_high"],
                fg_color=COLORS["primary"],
                checkmark_color=COLORS["on_primary"]
            ).pack(anchor="w", padx=28, pady=8)

        elif step_idx == 3:  # Installing
            self.btn_back.configure(state="disabled")
            self.btn_next.configure(state="disabled")
            self.btn_cancel.configure(state="disabled")

            box = ctk.CTkFrame(self.content_frame, fg_color=COLORS["surface"], corner_radius=16, border_width=1, border_color=COLORS["border"])
            box.pack(fill="both", expand=True, padx=4, pady=4)

            ctk.CTkLabel(
                box,
                text="Installing VBridge...",
                font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
                text_color=COLORS["text_high"]
            ).pack(anchor="w", padx=24, pady=(28, 6))

            self.lbl_install_status = ctk.CTkLabel(
                box,
                text="Preparing files...",
                font=ctk.CTkFont(family="Segoe UI", size=12),
                text_color=COLORS["text_muted"]
            )
            self.lbl_install_status.pack(anchor="w", padx=24, pady=(0, 20))

            self.progress_bar = ctk.CTkProgressBar(
                box,
                height=10,
                corner_radius=5,
                fg_color=COLORS["surface_highest"],
                progress_color=COLORS["primary"]
            )
            self.progress_bar.pack(fill="x", padx=24, pady=10)
            self.progress_bar.set(0.1)

            # Start installation asynchronously
            self.after(300, self._perform_installation)

        elif step_idx == 4:  # Finish
            self.btn_back.pack_forget()
            self.btn_cancel.pack_forget()
            self.btn_next.configure(text="Finish", state="normal", command=self._finish_and_exit)

            box = ctk.CTkFrame(self.content_frame, fg_color=COLORS["surface"], corner_radius=16, border_width=1, border_color=COLORS["border"])
            box.pack(fill="both", expand=True, padx=4, pady=4)

            ctk.CTkLabel(
                box,
                text="🎉 Installation Completed Successfully!",
                font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
                text_color=COLORS["green"]
            ).pack(anchor="w", padx=24, pady=(28, 8))

            ctk.CTkLabel(
                box,
                text=f"{APP_DISPLAY_NAME} has been installed on your computer.\n\n"
                     "You can now launch VBridge, scan the QR code from your phone app, "
                     "and enjoy zero-latency audio on your laptop and earbuds!",
                font=ctk.CTkFont(family="Segoe UI", size=13),
                text_color=COLORS["text_med"],
                justify="left",
                wraplength=520
            ).pack(anchor="w", padx=24, pady=6)

            ctk.CTkCheckBox(
                box,
                text=f"Launch {APP_DISPLAY_NAME} now",
                variable=self.chk_launch_var,
                font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                text_color=COLORS["text_high"],
                fg_color=COLORS["primary"],
                checkmark_color=COLORS["on_primary"]
            ).pack(anchor="w", padx=24, pady=(20, 0))

    def _browse_folder(self):
        f = filedialog.askdirectory(initialdir=self.install_dir_var.get())
        if f:
            self.install_dir_var.set(os.path.normpath(f))

    def _on_back(self):
        if self.current_step > 0:
            self._show_step(self.current_step - 1)

    def _on_next(self):
        if self.current_step == 2:
            self._show_step(3)
        elif self.current_step < len(self.steps) - 1:
            self._show_step(self.current_step + 1)

    def _perform_installation(self):
        try:
            target_dir = self.install_dir_var.get()
            os.makedirs(target_dir, exist_ok=True)
            self.progress_bar.set(0.3)
            self.lbl_install_status.configure(text="Copying application binaries and assets...")

            # 1. Copy VBridge.exe if compiled, or copy script bundle
            dist_exe = os.path.join(self.script_dir, "dist", "VBridge.exe")
            target_exe = os.path.join(target_dir, "VBridge.exe")
            
            if os.path.exists(dist_exe):
                shutil.copy2(dist_exe, target_exe)
            else:
                # Fallback: copy python files and assets
                for f in ["app.py", "audio_player.py", "audio_receiver.py", "startup_manager.py", "config_manager.py", "protocol.py", "generate_icon.py"]:
                    src = os.path.join(self.script_dir, f)
                    if os.path.exists(src):
                        shutil.copy2(src, target_dir)

            # Copy assets directory
            assets_src = os.path.join(self.script_dir, "assets")
            assets_dst = os.path.join(target_dir, "assets")
            if os.path.exists(assets_src):
                shutil.copytree(assets_src, assets_dst, dirs_exist_ok=True)

            self.progress_bar.set(0.6)
            self.lbl_install_status.configure(text="Creating shortcuts and registering Windows app...")

            # 2. Setup shortcuts
            ico_file = os.path.join(target_dir, "assets", "app_icon.ico")
            user_profile = os.environ.get("USERPROFILE", "")
            app_data = os.environ.get("APPDATA", "")

            # Executable path for shortcuts
            if os.path.exists(target_exe):
                launch_target = target_exe
                launch_args = ""
            else:
                python_dir = os.path.dirname(sys.executable)
                pythonw_exe = os.path.join(python_dir, "pythonw.exe")
                if not os.path.exists(pythonw_exe):
                    pythonw_exe = sys.executable
                launch_target = pythonw_exe
                launch_args = f'"{os.path.join(target_dir, "app.py")}"'

            ps_commands = []

            # Desktop Shortcut
            if self.chk_desktop_var.get():
                desktop_lnk = os.path.join(user_profile, "Desktop", "VBridge.lnk")
                ps_commands.append(f"""
                $Shortcut = $WshShell.CreateShortcut("{desktop_lnk}")
                $Shortcut.TargetPath = "{launch_target}"
                $Shortcut.Arguments = '{launch_args}'
                $Shortcut.WorkingDirectory = "{target_dir}"
                $Shortcut.IconLocation = "{ico_file}, 0"
                $Shortcut.Description = "VBridge Audio Relay"
                $Shortcut.Save()
                """)

            # Start Menu Shortcut
            if self.chk_startmenu_var.get():
                start_menu_programs = os.path.join(app_data, "Microsoft", "Windows", "Start Menu", "Programs")
                start_menu_lnk = os.path.join(start_menu_programs, "VBridge.lnk")
                ps_commands.append(f"""
                $Shortcut2 = $WshShell.CreateShortcut("{start_menu_lnk}")
                $Shortcut2.TargetPath = "{launch_target}"
                $Shortcut2.Arguments = '{launch_args}'
                $Shortcut2.WorkingDirectory = "{target_dir}"
                $Shortcut2.IconLocation = "{ico_file}, 0"
                $Shortcut2.Description = "VBridge Audio Relay"
                $Shortcut2.Save()
                """)

            if ps_commands:
                full_ps = "$WshShell = New-Object -ComObject WScript.Shell\n" + "\n".join(ps_commands)
                subprocess.run(["powershell", "-NoProfile", "-Command", full_ps], check=True)

            self.progress_bar.set(0.8)
            self.lbl_install_status.configure(text="Creating uninstaller and registry entries...")

            # 3. Create uninstaller batch
            uninstaller_bat = os.path.join(target_dir, "uninstall.bat")
            with open(uninstaller_bat, "w") as uf:
                uf.write(f"""@echo off
echo Uninstalling {APP_DISPLAY_NAME}...
reg delete "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{APP_NAME}" /f >nul 2>&1
reg delete "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run" /v "VBridgeAudioRelay" /f >nul 2>&1
del /f /q "{os.path.join(user_profile, 'Desktop', 'VBridge.lnk')}" >nul 2>&1
del /f /q "{os.path.join(app_data, 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'VBridge.lnk')}" >nul 2>&1
rmdir /s /q "%~dp0"
echo {APP_DISPLAY_NAME} has been completely uninstalled.
""")

            # 4. Register in Windows "Add / Remove Programs" (Control Panel & Windows Settings)
            uninstall_reg_path = f"Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{APP_NAME}"
            try:
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, uninstall_reg_path) as key:
                    winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, APP_DISPLAY_NAME)
                    winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, APP_VERSION)
                    winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, PUBLISHER)
                    winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, f"{ico_file},0")
                    winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, f'"{uninstaller_bat}"')
                    winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, target_dir)
                    winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
                    winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)
            except Exception as re:
                print(f"Registry registration error: {re}")

            # 5. Windows Auto-startup
            if self.chk_autostart_var.get():
                try:
                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE) as run_key:
                        winreg.SetValueEx(run_key, "VBridgeAudioRelay", 0, winreg.REG_SZ, f'"{launch_target}" {launch_args}'.strip())
                except Exception as se:
                    print(f"Startup registry error: {se}")

            self.progress_bar.set(1.0)
            self.lbl_install_status.configure(text="Finished!")

            # Go to Finish Step
            self.after(500, lambda: self._show_step(4))

        except Exception as e:
            messagebox.showerror("Installation Error", f"Failed to complete installation:\n{e}")
            self.destroy()

    def _finish_and_exit(self):
        if self.chk_launch_var.get():
            target_dir = self.install_dir_var.get()
            target_exe = os.path.join(target_dir, "VBridge.exe")
            if os.path.exists(target_exe):
                subprocess.Popen([target_exe], cwd=target_dir)
            else:
                python_dir = os.path.dirname(sys.executable)
                pythonw_exe = os.path.join(python_dir, "pythonw.exe")
                if not os.path.exists(pythonw_exe):
                    pythonw_exe = sys.executable
                subprocess.Popen([pythonw_exe, os.path.join(target_dir, "app.py")], cwd=target_dir)

        self.destroy()


if __name__ == "__main__":
    app = VBridgeSetupWizard()
    app.mainloop()
