"""A linked Chess.com account: remember the username and pull in new games automatically.

Chess.com only offers OAuth to approved partners, so "linking" uses the public, read-only
Published-Data API by username. Nothing is stored except the public profile.
"""

import time

import httpx

from . import analysis, learning
from .db import db
from .importers import UA

API = "https://api.chess.com/pub"
KEY = "account:chesscom"
FIRST_SYNC = 20      # games pulled the first time, so linking a ten-year account stays quick
MAX_PER_SYNC = 100
MIN_INTERVAL = 300   # seconds between automatic syncs; a manual sync ignores it


def get() -> dict | None:
    return db.kv_get(KEY)


async def link(username: str) -> dict:
    async with httpx.AsyncClient(headers=UA, timeout=20) as client:
        r = await client.get(f"{API}/player/{username.strip().lower()}")
        if r.status_code == 404:
            raise LookupError(username)
        r.raise_for_status()
        p = r.json()
    account = {"username": p.get("username", username), "name": p.get("name"), "avatar": p.get("avatar"),
               "url": p.get("url"), "linked_at": time.time(), "last_end": 0, "checked_at": 0}
    db.kv_set(KEY, account)
    return account


def unlink() -> None:
    db.execute("DELETE FROM kv WHERE key = ?", (KEY,))


def _month_of(archive_url: str) -> tuple[int, int]:
    year, month = archive_url.rstrip("/").split("/")[-2:]
    return int(year), int(month)


async def _new_games(username: str, since: int) -> list[dict]:
    """Standard-chess games that ended after `since` (unix seconds), newest first."""
    limit = FIRST_SYNC if since == 0 else MAX_PER_SYNC
    since_month = time.gmtime(since)[:2]
    out: list[dict] = []
    async with httpx.AsyncClient(headers=UA, timeout=20) as client:
        r = await client.get(f"{API}/player/{username.lower()}/games/archives")
        r.raise_for_status()
        for url in reversed(r.json().get("archives", [])):
            if since and _month_of(url) < since_month:
                break
            month = await client.get(url)
            month.raise_for_status()
            for g in reversed(month.json().get("games", [])):
                if g.get("end_time", 0) > since and g.get("rules") == "chess" and g.get("pgn"):
                    out.append(g)
            if len(out) >= limit:
                break
    return out[:limit]


async def sync(force: bool = False) -> dict:
    account = get()
    if not account:
        raise LookupError("no account")
    if not force and time.time() - account.get("checked_at", 0) < MIN_INTERVAL:
        return {"account": account, "added": 0}
    games = await _new_games(account["username"], account["last_end"])
    me = account["username"].lower()
    added = 0
    for g in reversed(games):  # oldest first, so ties in created_at keep the game order
        new = not db.one("SELECT 1 FROM games WHERE id = ?", (analysis.game_id(g["pgn"]),))
        try:
            stored = analysis.store_game(g["pgn"], created_at=g["end_time"])
        except analysis.PGNError:
            continue
        added += new
        side = "white" if g["white"].get("username", "").lower() == me else "black"
        if learning.get_side(stored["id"]) is None:
            learning.set_side(stored["id"], side)
    account = {**account, "checked_at": time.time(),
               "last_end": max([account["last_end"], *(g["end_time"] for g in games)])}
    db.kv_set(KEY, account)
    return {"account": account, "added": added}
