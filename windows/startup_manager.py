import os
import sys
import winreg
import logging

logger = logging.getLogger("VBridge.StartupManager")

REG_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "VBridgeAudioRelay"


class StartupManager:
    """
    Manages Windows Registry autorun configuration for VBridge.
    Allows VBridge to launch silently on laptop boot in background.
    """

    @staticmethod
    def get_executable_command() -> str:
        """Get command line to launch VBridge."""
        python_exe = sys.executable
        # Find path to app.py
        current_dir = os.path.dirname(os.path.abspath(__file__))
        app_script = os.path.join(current_dir, "app.py")
        
        # If pythonw.exe is available, use it for silent background launch
        pythonw_exe = os.path.join(os.path.dirname(python_exe), "pythonw.exe")
        if os.path.exists(pythonw_exe):
            launcher = pythonw_exe
        else:
            launcher = python_exe

        return f'"{launcher}" "{app_script}"'

    @staticmethod
    def is_startup_enabled() -> bool:
        """Check if VBridge is registered in Windows Startup registry."""
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_READ) as key:
                val, _ = winreg.QueryValueEx(key, APP_NAME)
                return bool(val)
        except (FileNotFoundError, WindowsError):
            return False

    @staticmethod
    def set_startup_enabled(enable: bool) -> bool:
        """Enable or disable VBridge Windows startup launch."""
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                if enable:
                    cmd = StartupManager.get_executable_command()
                    winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
                    logger.info(f"Registered VBridge in Windows Startup: {cmd}")
                else:
                    try:
                        winreg.DeleteValue(key, APP_NAME)
                        logger.info("Unregistered VBridge from Windows Startup.")
                    except FileNotFoundError:
                        pass
            return True
        except Exception as e:
            logger.error(f"Failed to update Windows Startup registry: {e}")
            return False
