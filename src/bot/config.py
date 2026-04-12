import json
import os

from dotenv import load_dotenv


class Config:
    def __init__(self, profile_name: str, base_dir: str = "."):
        self.profile_name = profile_name
        self.base_dir = os.path.abspath(base_dir)
        self.profile_dir = os.path.join(self.base_dir, "profiles", profile_name)

        load_dotenv(os.path.join(self.base_dir, ".env"))

        config_path = os.path.join(self.profile_dir, "config.json")
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config not found: {config_path}")

        with open(config_path, "r", encoding="utf-8") as f:
            self._data = json.load(f)

    def get(self, *keys, default=None):
        val = self._data
        for k in keys:
            if not isinstance(val, dict):
                return default
            val = val.get(k)
            if val is None:
                return default
        return val

    def api_key(self, name: str) -> str:
        return os.getenv(f"{name.upper()}_API_KEY", "")

    def token_path(self) -> str:
        return os.path.join(self.profile_dir, "token.json")

    def client_secrets_path(self) -> str:
        return os.path.join(self.base_dir, "client_secrets.json")

    def history_path(self) -> str:
        return os.path.join(self.profile_dir, "upload_history.json")
