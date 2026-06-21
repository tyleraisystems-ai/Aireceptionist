from functools import lru_cache
from typing import Any

import yaml

from app.core.settings import get_settings


@lru_cache
def get_business_config() -> dict[str, Any]:
    path = get_settings().business_config_path
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)
