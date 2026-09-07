import functools

import yaml

from aifun.utils.media import ENGINE_ROOT

SETTINGS_PATH = ENGINE_ROOT / "config" / "settings.yaml"


@functools.lru_cache(maxsize=1)
def load_settings() -> dict:
    return yaml.safe_load(SETTINGS_PATH.read_text())
