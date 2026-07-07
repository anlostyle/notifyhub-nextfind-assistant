import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

from notifyhub.plugins.utils import get_plugin_config

logger = logging.getLogger(__name__)
PLUGIN_ID = "nextfind_assistant"


class Config:
    def __init__(self):
        self._cache = None
        self._cache_at = 0

    def _data(self) -> Dict[str, Any]:
        if self._cache is None or time.time() - self._cache_at > 30:
            try:
                self._cache = get_plugin_config(PLUGIN_ID) or {}
            except Exception as e:
                logger.error("获取 NextFind 助手配置失败: %s", e)
                self._cache = {}
            self._cache_at = time.time()
        return self._cache

    def get(self, key: str, default: Any = "") -> Any:
        return self._data().get(key, default)

    @property
    def nextfind_base_url(self) -> str:
        return self.get("nextfind_base_url", "").rstrip("/")

    @property
    def nextfind_api_key(self) -> str:
        return self.get("nextfind_api_key", "")

    @property
    def qywx_base_url(self) -> str:
        return self.get("qywx_base_url", "").rstrip("/")

    @property
    def sCorpID(self) -> str:
        return self.get("sCorpID", "")

    @property
    def sCorpsecret(self) -> str:
        return self.get("sCorpsecret", "")

    @property
    def sAgentid(self) -> str:
        return self.get("sAgentid", "")

    @property
    def sToken(self) -> str:
        return self.get("sToken", "")

    @property
    def sEncodingAESKey(self) -> str:
        return self.get("sEncodingAESKey", "")


config = Config()


class UserState:
    def __init__(self):
        base = Path(os.environ.get("WORKDIR") or "/data")
        self.path = base / "plugins" / PLUGIN_ID / "state.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> Dict[str, Any]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8") or "{}")
        except Exception:
            return {}

    def get(self, user: str) -> Dict[str, Any]:
        return self._load().get(user, {"search": [], "resources": [], "current": None})

    def save(self, user: str, **parts):
        data = self._load()
        current = data.get(user, {"search": [], "resources": [], "current": None})
        current.update(parts)
        current["updated_at"] = time.time()
        data[user] = current
        self.path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
