"""Locale files: every user-facing coach string lives in app/locales/<lang>.json.

The language follows the request (the frontend sets a `chesso_lang` cookie); background
prefetch tasks inherit it because asyncio copies context variables into new tasks.
"""

import json
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path

from .config import settings

DIR = Path(__file__).parent / "locales"
current: ContextVar[str | None] = ContextVar("lang", default=None)


def available() -> set[str]:
    return {p.stem for p in DIR.glob("*.json")}


@lru_cache
def _read(lang: str) -> dict:
    path = DIR / f"{lang}.json"
    if not path.exists():
        path = DIR / "en.json"
    return json.loads(path.read_text())


def lang() -> str:
    return current.get() or settings.locale


def load(lang_code: str | None = None) -> dict:
    return _read(lang_code or lang())
