import os
import sys
import subprocess

def create_windows_shortcuts():
    """
    Creates Start Menu and Desktop shortcuts for VBridge
    pointing to pythonw.exe so it runs as a native background/GUI app with no console.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    app_py = os.path.join(script_dir, "app.py")
    ico_path = os.path.join(script_dir, "assets", "app_icon.ico")
    
    # Locate pythonw.exe (windowless python interpreter)
    python_dir = os.path.dirname(sys.executable)
    pythonw_exe = os.path.join(python_dir, "pythonw.exe")
    if not os.path.exists(pythonw_exe):
        pythonw_exe = sys.executable

    # Paths for Desktop and Start Menu
    user_profile = os.environ.get("USERPROFILE", "")
    app_data = os.environ.get("APPDATA", "")

    desktop_lnk = os.path.join(user_profile, "Desktop", "VBridge.lnk")
    start_menu_programs = os.path.join(app_data, "Microsoft", "Windows", "Start Menu", "Programs")
    start_menu_lnk = os.path.join(start_menu_programs, "VBridge.lnk")

    ps_script = f"""
    $WshShell = New-Object -ComObject WScript.Shell

    # Desktop Shortcut
    $Shortcut = $WshShell.CreateShortcut("{desktop_lnk}")
    $Shortcut.TargetPath = "{pythonw_exe}"
    $Shortcut.Arguments = '"{app_py}"'
    $Shortcut.WorkingDirectory = "{script_dir}"
    $Shortcut.IconLocation = "{ico_path}, 0"
    $Shortcut.Description = "VBridge Audio Relay to Windows Laptop"
    $Shortcut.Save()

    # Start Menu Shortcut
    $Shortcut2 = $WshShell.CreateShortcut("{start_menu_lnk}")
    $Shortcut2.TargetPath = "{pythonw_exe}"
    $Shortcut2.Arguments = '"{app_py}"'
    $Shortcut2.WorkingDirectory = "{script_dir}"
    $Shortcut2.IconLocation = "{ico_path}, 0"
    $Shortcut2.Description = "VBridge Audio Relay to Windows Laptop"
    $Shortcut2.Save()
    """

    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], check=True)
        print(f"Created Desktop shortcut: {desktop_lnk}")
        print(f"Created Start Menu shortcut: {start_menu_lnk}")
        return True
    except Exception as e:
        print(f"Failed to create shortcuts: {e}")
        return False

if __name__ == "__main__":
    create_windows_shortcuts()
