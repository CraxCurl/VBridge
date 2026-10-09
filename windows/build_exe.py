import os
import sys
import subprocess
import shutil

def build_standalone_exe():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    app_py = os.path.join(script_dir, "app.py")
    ico_path = os.path.join(script_dir, "assets", "app_icon.ico")
    
    if not os.path.exists(ico_path):
        from generate_icon import generate_app_icon
        generate_app_icon(script_dir)

    print("Building standalone VBridge.exe via PyInstaller...")
    
    cmd = [
        sys.executable,
        "-m", "PyInstaller",
        "--noconsole",
        "--onefile",
        "--name=VBridge",
        f"--icon={ico_path}",
        f"--add-data={os.path.join(script_dir, 'assets')};assets",
        "--collect-all=customtkinter",
        "--collect-all=pystray",
        "--collect-all=PIL",
        "--collect-all=sounddevice",
        "--exclude-module=setuptools",
        "--clean",
        "-y",
        app_py
    ]

    print("Running command:", " ".join(cmd))
    res = subprocess.run(cmd, cwd=script_dir)
    if res.returncode == 0:
        dist_exe = os.path.join(script_dir, "dist", "VBridge.exe")
        print("========================================================")
        print(f"BUILD SUCCESS! Standalone Windows App created at:")
        print(dist_exe)
        print("========================================================")
    else:
        print("Build failed with code:", res.returncode)

if __name__ == "__main__":
    build_standalone_exe()
