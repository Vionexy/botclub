from __future__ import annotations
import os

class Settings:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    DATABASE_URL: str = "sqlite+aiosqlite:///./tournament.db"
    MINI_APP_URL: str = "https://vionexy.github.io/club/"
    ADMIN_PANEL_URL: str = "https://vionexy.github.io/club/admin/"
    ADMIN_IDS: str = "[6986627524, 8468489771]"
    
    # Optional proxy support for Telegram connection (e.g., "http://127.0.0.1:10809")
    PROXY: str | None = None

    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    @property
    def admin_ids_list(self) -> list[int]:
        import json
        raw = self.ADMIN_IDS.strip()
        if raw.startswith("[") and raw.endswith("]"):
            try:
                return [int(x) for x in json.loads(raw)]
            except Exception:
                pass
        try:
            return [int(x.strip()) for x in raw.split(",") if x.strip()]
        except Exception:
            return [6986627524, 8468489771]


settings = Settings()
