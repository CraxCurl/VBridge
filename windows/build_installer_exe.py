import os
import sys
import subprocess

def build_setup_exe():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    wizard_py = os.path.join(script_dir, "installer_wizard.py")
    ico_path = os.path.join(script_dir, "assets", "app_icon.ico")
    
    if not os.path.exists(ico_path):
        from generate_icon import generate_app_icon
        generate_app_icon(script_dir)

    print("========================================================")
    print("Building Website Installer Setup Executable: VBridge-Setup.exe")
    print("========================================================")

    cmd = [
        sys.executable,
        "-m", "PyInstaller",
        "--noconsole",
        "--onefile",
        "--name=VBridge-Setup",
        f"--icon={ico_path}",
        f"--add-data={os.path.join(script_dir, 'assets')};assets",
        f"--add-data={os.path.join(script_dir, 'dist')};dist",
        "--collect-all=customtkinter",
        "--collect-all=PIL",
        "--exclude-module=setuptools",
        "--clean",
        "-y",
        wizard_py
    ]

    res = subprocess.run(cmd, cwd=script_dir)
    if res.returncode == 0:
        setup_exe = os.path.join(script_dir, "dist", "VBridge-Setup.exe")
        print("\n========================================================")
        print("SUCCESS! Website Installer Setup created at:")
        print(setup_exe)
        print("========================================================")
        return setup_exe
    else:
        print("Failed to build installer setup with code:", res.returncode)
        return None

if __name__ == "__main__":
    build_setup_exe()
