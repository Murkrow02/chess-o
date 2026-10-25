"""Fetch recent public games from Lichess and Chess.com."""

import json

import httpx

UA = {"User-Agent": "chess-o (self-hosted game review; https://github.com/Murkrow02/chess-o)"}


def _summary(pgn: str, white: str, black: str, result: str, when, speed: str, url: str) -> dict:
    return {"pgn": pgn, "white": white, "black": black, "result": result, "date": when, "speed": speed, "url": url}


def _lichess_name(players: dict, side: str) -> str:
    p = players.get(side, {})
    if p.get("user"):
        return p["user"].get("name", "?")
    if p.get("aiLevel"):
        return f"Stockfish level {p['aiLevel']}"
    return "?"


async def lichess(user: str, limit: int = 20) -> list[dict]:
    async with httpx.AsyncClient(headers={**UA, "Accept": "application/x-ndjson"}, timeout=20) as client:
        r = await client.get(f"https://lichess.org/api/games/user/{user}",
                             params={"max": limit, "pgnInJson": "true", "clocks": "false", "evals": "false"})
        if r.status_code == 404:
            return []
        r.raise_for_status()
    out = []
    for line in r.text.splitlines():
        if not line.strip():
            continue
        g = json.loads(line)
        players = g.get("players", {})
        winner = g.get("winner")
        result = "1-0" if winner == "white" else "0-1" if winner == "black" else "½-½"
        out.append(_summary(g.get("pgn", ""), _lichess_name(players, "white"), _lichess_name(players, "black"), result,
                            g.get("createdAt"), g.get("speed", ""), f"https://lichess.org/{g.get('id')}"))
    return out


async def chesscom(user: str, limit: int = 20) -> list[dict]:
    async with httpx.AsyncClient(headers=UA, timeout=20) as client:
        r = await client.get(f"https://api.chess.com/pub/player/{user.lower()}/games/archives")
        if r.status_code == 404:
            return []
        r.raise_for_status()
        archives = r.json().get("archives", [])
        games: list[dict] = []
        for url in reversed(archives):
            month = await client.get(url)
            month.raise_for_status()
            games.extend(reversed(month.json().get("games", [])))
            if len(games) >= limit:
                break
    out = []
    for g in games[:limit]:
        if g.get("rules") != "chess" or not g.get("pgn"):
            continue
        w, b = g["white"], g["black"]
        result = "1-0" if w.get("result") == "win" else "0-1" if b.get("result") == "win" else "½-½"
        out.append(_summary(g["pgn"], w.get("username", "?"), b.get("username", "?"), result,
                            (g.get("end_time") or 0) * 1000, g.get("time_class", ""), g.get("url", "")))
    return out
