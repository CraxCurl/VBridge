import json
import os
import logging

logger = logging.getLogger("VBridge.ConfigManager")


class ConfigManager:
    """
    Manages persistent JSON configuration for VBridge in AppData.
    Stores audio output preference, pairing code, and startup state.
    """

    def __init__(self):
        appdata_dir = os.getenv("APPDATA", os.path.expanduser("~"))
        self.config_dir = os.path.join(appdata_dir, "VBridge")
        self.config_path = os.path.join(self.config_dir, "config.json")
        self._ensure_dir()
        self.settings = self._load()

    def _ensure_dir(self):
        try:
            os.makedirs(self.config_dir, exist_ok=True)
        except Exception as e:
            logger.debug(f"Could not create config dir: {e}")

    def _load(self) -> dict:
        default_settings = {
            "pairing_code": "1234",
            "volume": 1.0,
            "selected_device_name": "",
            "keep_anti_sleep": True,
            "launch_at_startup": False
        }
        if not os.path.exists(self.config_path):
            return default_settings

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                default_settings.update(loaded)
                return default_settings
        except Exception as e:
            logger.warning(f"Error reading config: {e}. Using defaults.")
            return default_settings

    def save(self):
        try:
            self._ensure_dir()
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to write config: {e}")

    def get(self, key, default=None):
        return self.settings.get(key, default)

    def set(self, key, value):
        self.settings[key] = value
        self.save()
