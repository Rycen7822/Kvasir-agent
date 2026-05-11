from __future__ import annotations

from pathlib import Path

from ..config import ConfigManager


class CloudLinkService:
    def __init__(self, home: Path) -> None:
        self.home = home
        self.config_manager = ConfigManager(home)

    def snapshot(self) -> dict:
        config = self.config_manager.load_named("config")
        cloud = config.get("cloud", {})
        return {
            "linked": bool(cloud.get("enabled", False) and (cloud.get("token") or cloud.get("token_env"))),
            "base_url": cloud.get("base_url", "https://deepscientist.cc"),
            "sync_mode": cloud.get("sync_mode", "disabled"),
        }
