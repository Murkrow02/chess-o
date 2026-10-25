"""Locale files: every user-facing coach string lives in app/locales/<lang>.json."""

import json
from functools import lru_cache
from pathlib import Path

from .config import settings

DIR = Path(__file__).parent / "locales"


@lru_cache
def load(lang: str | None = None) -> dict:
    lang = lang or settings.locale
    path = DIR / f"{lang}.json"
    if not path.exists():
        path = DIR / "en.json"
    return json.loads(path.read_text())
