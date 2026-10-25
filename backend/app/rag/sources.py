"""Freely licensed chess texts for the knowledge base, plus the user's own files.

Every source here is public domain or CC BY-SA. Raw downloads are cached under
knowledge/sources/ (git-ignored) so a re-run does not hit the network again.
"""

import io
import json
import logging
import re
import urllib.parse
from pathlib import Path

import chess
import httpx

from ..config import settings

log = logging.getLogger(__name__)
UA = {"User-Agent": "chess-o knowledge ingest (https://github.com/Murkrow02/chess-o)"}

# (id, title, author, regex where the chess part ends)
GUTENBERG = [
    (33870, "Chess Fundamentals", "José Raúl Capablanca", None),
    (5614, "Chess Strategy", "Edward Lasker", None),
    (4913, "Chess and Checkers: the Way to Mastership", "Edward Lasker", r"\n\s*PART II\s*\n(?![\s\S]*\n\s*PART II\s*\n)"),
]

WIKIPEDIA = [
    # tactics
    "Chess tactic", "Fork (chess)", "Pin (chess)", "Skewer (chess)", "Discovered attack", "Double check",
    "Zwischenzug", "Sacrifice (chess)", "Deflection (chess)", "Decoy (chess)", "Overloading (chess)",
    "Interference (chess)", "Desperado (chess)", "Back-rank checkmate", "Smothered mate", "Windmill (chess)",
    "Undermining (chess)", "X-ray (chess)", "Checkmate pattern", "Swindle (chess)",
    # strategy
    "Chess strategy", "Pawn structure", "Isolated pawn", "Doubled pawns", "Backward pawn", "Passed pawn",
    "Outpost (chess)", "Fianchetto", "Initiative (chess)", "Tempo (chess)",
    "Castling", "Open file", "Prophylaxis (chess)", "Minority attack", "Exchange (chess)",
    "Chess piece relative value", "Compensation (chess)",
    # endgame
    "Chess endgame", "Opposition (chess)", "Zugzwang", "Triangulation (chess)", "Lucena position",
    "Philidor position", "Rook and pawn versus rook endgame", "King and pawn versus king endgame",
    "Wrong rook pawn", "Fortress (chess)", "Key square",
    # openings and general
    "Chess opening", "Gambit", "Queen's Pawn Game", "King's Pawn Game", "Sicilian Defence", "French Defence",
    "Caro–Kann Defence", "Italian Game", "Ruy Lopez", "Queen's Gambit", "King's Indian Defence",
    "London System", "Scandinavian Defense", "Pirc Defence", "English Opening", "Scholar's mate",
    "Fool's mate", "Threefold repetition", "Stalemate", "Fifty-move rule", "Time trouble",
]

SKIP_SECTIONS = re.compile(r"^(see also|references|notes|external links|further reading|bibliography|sources|"
                           r"statistics|theory table|footnotes|citations|all possible replies)$", re.I)

CC_BY_SA = "CC BY-SA 4.0"


def _cache(name: str) -> Path:
    p = settings.knowledge_dir / "sources" / name
    p.mkdir(parents=True, exist_ok=True)
    return p


def _get(client: httpx.Client, url: str, params: dict | None = None) -> httpx.Response:
    r = client.get(url, params=params, headers=UA, follow_redirects=True, timeout=60)
    r.raise_for_status()
    return r


def chunk(text: str, target: int = 650, hard: int = 900) -> list[str]:
    """Split on paragraphs into pieces of about `target` characters (the coach prompt keeps ~700)."""
    paras = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", text)]
    out, cur = [], ""
    for p in paras:
        if len(p) < 3:
            continue
        while len(p) > hard:  # break a long paragraph at a sentence end
            cut = p.rfind(". ", 0, target) + 1 or target
            pieces = (p[:cut].strip(), p[cut:].strip())
            if cur:
                out.append(cur)
                cur = ""
            out.append(pieces[0])
            p = pieces[1]
        if cur and len(cur) + len(p) + 1 > target:
            out.append(cur)
            cur = p
        else:
            cur = f"{cur} {p}".strip()
    if cur:
        out.append(cur)
    return [c for c in out if len(c) >= 120]


# Descriptive notation ("Kt x P", "Q - B 3") and move numbers: a chunk that is mostly a game score
# only confuses the coach, which must not quote moves outside the engine lines anyway.
NOTATION = re.compile(r"\b(?:Kt|[KQRBP])\s?[x-]\s?(?:Kt|[KQRBP])?\s?\d?|\b\d+\.\s?\.{0,3}")


def _prose(text: str) -> bool:
    if re.search(r"checker|draughts", text, re.I):  # Lasker's book covers both games
        return False
    return len(NOTATION.findall(text)) * 40 < len(text)


def _strip_wiki(extract: str) -> str:
    """Drop reference-ish sections from a MediaWiki plain-text extract and the heading markers."""
    keep, skipping = [], False
    for line in extract.splitlines():
        m = re.match(r"^(=+)\s*(.*?)\s*=+$", line.strip())
        if m:
            skipping = bool(SKIP_SECTIONS.match(m.group(2)))
            keep.append("")
            continue
        if not skipping:
            keep.append(line)
    return "\n".join(keep)


def gutenberg(refresh: bool = False) -> list[dict]:
    cache, docs = _cache("gutenberg"), []
    with httpx.Client() as client:
        for gid, title, author, stop in GUTENBERG:
            f = cache / f"pg{gid}.txt"
            if refresh or not f.exists():
                f.write_text(_get(client, f"https://www.gutenberg.org/cache/epub/{gid}/pg{gid}.txt").text)
            raw = f.read_text()
            start = re.search(r"\*\*\* ?START OF.*?\*\*\*", raw)
            end = re.search(r"\*\*\* ?END OF", raw)
            body = raw[start.end() if start else 0:end.start() if end else len(raw)]
            body = body.replace("\r\n", "\n")
            if stop and (m := re.search(stop, body)):
                body = body[:m.start()]
            body = re.sub(r"\[Illustration[^\]]*\]|\{\d+\}", "", body)
            docs.append({"title": f"{title} ({author})", "url": f"https://www.gutenberg.org/ebooks/{gid}",
                         "license": "Public domain", "chunks": [c for c in chunk(body) if _prose(c)]})
    return docs


def _extracts(client: httpx.Client, api: str, titles: list[str]) -> dict[str, str]:
    """Plain-text extracts for up to 20 titles per request (the API's limit for whole pages)."""
    out = {}
    for i in range(0, len(titles), 20):
        r = _get(client, api, {"action": "query", "prop": "extracts", "explaintext": 1, "redirects": 1,
                               "exlimit": "max", "titles": "|".join(titles[i:i + 20]), "format": "json"}).json()
        for page in r.get("query", {}).get("pages", {}).values():
            if "extract" in page:
                out[page["title"]] = page["extract"]
    return out


def wikipedia(refresh: bool = False) -> list[dict]:
    f = _cache("wikipedia") / "extracts.json"
    if refresh or not f.exists():
        with httpx.Client() as client:
            # One title per request: extracts of whole articles are capped at one page per call.
            data = {}
            for t in WIKIPEDIA:
                data.update(_extracts(client, "https://en.wikipedia.org/w/api.php", [t]))
        f.write_text(json.dumps(data))
    data = json.loads(f.read_text())
    # A few list entries redirect to the general "Chess" article, which is too broad to help.
    data.pop("Chess", None)
    return [{"title": f"{t} (Wikipedia)", "url": "https://en.wikipedia.org/wiki/" + urllib.parse.quote(t.replace(" ", "_")),
             "license": CC_BY_SA, "chunks": chunk(_strip_wiki(text))} for t, text in data.items()]


def _path_board(title: str) -> chess.Board | None:
    """'Chess Opening Theory/1. d4/1...d6/2. c4' -> the board after 1.d4 d6 2.c4."""
    board = chess.Board()
    for step in title.split("/")[1:]:
        san = re.sub(r"^\d+\.(\.\.)?\s*", "", step.strip())
        try:
            board.push_san(san)
        except ValueError:
            return None
    return board


def strip_wikitext(text: str) -> str:
    """Rough wikitext to plain text: enough for prose paragraphs, not for tables or diagrams."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"<ref[^>/]*/>|<ref.*?</ref>", "", text, flags=re.S)
    text = re.sub(r"<table.*?</table>", "", text, flags=re.S | re.I)
    text = re.sub(r"^\{\|.*?^\|\}", "", text, flags=re.S | re.M)
    prev = None
    while prev != text:  # innermost templates first, so nesting unwinds
        prev, text = text, re.sub(r"\{\{[^{}]*\}\}", "", text)
    text = re.sub(r"\[\[(?:[a-z]{2,3}|Category|File|Image):[^\]]*\]\]", "", text, flags=re.I)
    text = re.sub(r"\[\[[^\]|]*\|([^\]]*)\]\]", r"\1", text)
    text = re.sub(r"\[\[([^\]]*)\]\]", r"\1", text)
    text = re.sub(r"\[https?://\S+ ([^\]]*)\]", r"\1", text)
    text = re.sub(r"'{2,}", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    return _strip_wiki(text)


def _batched(client: httpx.Client, api: str, titles: list[str]) -> dict[str, str]:
    """Raw wikitext for 50 titles per request."""
    out = {}
    for i in range(0, len(titles), 50):
        # POST: fifty long move-path titles overflow a GET URL.
        r = client.post(api, data={"action": "query", "prop": "revisions", "rvprop": "content", "rvslots": "main",
                                   "titles": "|".join(titles[i:i + 50]), "format": "json", "formatversion": 2},
                        headers=UA, timeout=60)
        r.raise_for_status()
        r = r.json()
        for page in r.get("query", {}).get("pages", []):
            if page.get("revisions"):
                out[page["title"]] = page["revisions"][0]["slots"]["main"]["content"]
    return out


def wikibooks(refresh: bool = False) -> list[dict]:
    """Wikibooks' Chess Opening Theory: one page per position, keyed by EPD so transpositions match."""
    f = _cache("wikibooks") / "opening_theory.json"
    api = "https://en.wikibooks.org/w/api.php"
    if refresh or not f.exists():
        with httpx.Client() as client:
            titles, cont = [], {}
            while True:
                r = _get(client, api, {"action": "query", "list": "allpages", "apprefix": "Chess Opening Theory/",
                                       "apnamespace": 0, "aplimit": "max", "apfilterredir": "nonredirects",
                                       "format": "json", **cont}).json()
                titles += [p["title"] for p in r["query"]["allpages"]]
                if "continue" not in r:
                    break
                cont = r["continue"]
            log.info("wikibooks: fetching %d opening pages", len(titles))
            data = _batched(client, api, titles)
        f.write_text(json.dumps(data))
    data = json.loads(f.read_text())
    docs = []
    for title, wikitext in data.items():
        board = _path_board(title)
        if board is None:
            continue
        name = re.search(r"\{\{Chess Opening Theory/Position\s*(?:\|=)?\s*\|(?:name\s*=\s*)?([^|\n=}]+)", wikitext)
        name = name.group(1).strip() if name else ""
        body = strip_wikitext(wikitext).strip()
        if len(re.sub(r"\s+", " ", body)) < 80:
            continue  # stub pages: just a theory table
        line = title.split("/", 1)[1].replace("/", " ")
        head = f"Opening line {line}" + (f" ({name})" if name and name.lower() != "universal" else "")
        pieces = chunk(f"{head}.\n\n{body}", target=700) or [f"{head}. {re.sub(chr(10), ' ', body)}"]
        docs.append({"title": f"{name or line} (Wikibooks)", "url": "https://en.wikibooks.org/wiki/" + urllib.parse.quote(title.replace(" ", "_")),
                     "license": CC_BY_SA, "epd": board.epd(), "chunks": pieces[:2]})
    return docs


def custom(refresh: bool = False) -> list[dict]:
    """Whatever the user dropped in knowledge/custom: PDF, Markdown or text."""
    folder = settings.knowledge_dir / "custom"
    docs = []
    for p in sorted(folder.rglob("*")):
        if p.name.lower() == "readme.md" or not p.is_file():
            continue
        suffix = p.suffix.lower()
        try:
            if suffix == ".pdf":
                from pypdf import PdfReader
                text = "\n\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(p.read_bytes())).pages)
            elif suffix in (".md", ".txt", ".markdown"):
                text = p.read_text(errors="replace")
            else:
                continue
        except Exception:
            log.exception("custom: could not read %s", p)
            continue
        docs.append({"title": p.stem.replace("_", " "), "url": None, "license": "Your file",
                     "chunks": chunk(text)})
    return docs


ALL = {"gutenberg": gutenberg, "wikipedia": wikipedia, "wikibooks": wikibooks, "custom": custom}
