"""Knowledge base tables: documents, chunks and a sqlite-vec index over chunk embeddings."""

import hashlib

import sqlite_vec

from ..db import db

DIM = 1024  # bge-m3

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS rag_docs (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT,
    license TEXT NOT NULL,
    epd TEXT
);
CREATE INDEX IF NOT EXISTS rag_docs_source ON rag_docs (source);
CREATE INDEX IF NOT EXISTS rag_docs_epd ON rag_docs (epd);
CREATE TABLE IF NOT EXISTS rag_chunks (
    id INTEGER PRIMARY KEY,
    doc_id INTEGER NOT NULL REFERENCES rag_docs (id) ON DELETE CASCADE,
    hash TEXT NOT NULL,
    text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS rag_chunks_doc ON rag_chunks (doc_id);
CREATE INDEX IF NOT EXISTS rag_chunks_hash ON rag_chunks (hash);
CREATE VIRTUAL TABLE IF NOT EXISTS rag_vec USING vec0(embedding float[{DIM}] distance_metric=cosine);
CREATE TABLE IF NOT EXISTS rag_embed_cache (
    hash TEXT PRIMARY KEY,
    embedding BLOB NOT NULL
);
"""

with db.lock:
    db.conn.executescript(SCHEMA)


def text_hash(text: str) -> str:
    return hashlib.sha1(text.encode()).hexdigest()


def count() -> int:
    return db.one("SELECT COUNT(*) AS n FROM rag_chunks")["n"]


def sources() -> list[dict]:
    rows = db.all("SELECT source, license, COUNT(DISTINCT d.id) AS docs, COUNT(c.id) AS chunks "
                  "FROM rag_docs d LEFT JOIN rag_chunks c ON c.doc_id = d.id GROUP BY source, license")
    return [dict(r) for r in rows]


def cached_embeddings(hashes: list[str]) -> dict[str, bytes]:
    if not hashes:
        return {}
    out: dict[str, bytes] = {}
    for i in range(0, len(hashes), 500):
        part = hashes[i:i + 500]
        rows = db.all(f"SELECT hash, embedding FROM rag_embed_cache WHERE hash IN ({','.join('?' * len(part))})",
                      tuple(part))
        out.update({r["hash"]: r["embedding"] for r in rows})
    return out


def cache_embeddings(pairs: list[tuple[str, list[float]]]) -> None:
    db.executemany("INSERT OR REPLACE INTO rag_embed_cache (hash, embedding) VALUES (?, ?)",
                   [(h, sqlite_vec.serialize_float32(v)) for h, v in pairs])


def replace_source(source: str, docs: list[dict]) -> int:
    """Swap every document of `source` for `docs` (each with `chunks` as (hash, text, blob))."""
    with db.lock:
        c = db.conn
        old = [r[0] for r in c.execute(
            "SELECT c.id FROM rag_chunks c JOIN rag_docs d ON d.id = c.doc_id WHERE d.source = ?", (source,))]
        for i in range(0, len(old), 500):
            part = old[i:i + 500]
            c.execute(f"DELETE FROM rag_vec WHERE rowid IN ({','.join('?' * len(part))})", part)
        c.execute("DELETE FROM rag_chunks WHERE doc_id IN (SELECT id FROM rag_docs WHERE source = ?)", (source,))
        c.execute("DELETE FROM rag_docs WHERE source = ?", (source,))
        n = 0
        for d in docs:
            doc_id = c.execute("INSERT INTO rag_docs (source, title, url, license, epd) VALUES (?,?,?,?,?)",
                               (source, d["title"], d.get("url"), d["license"], d.get("epd"))).lastrowid
            for h, text, blob in d["chunks"]:
                cid = c.execute("INSERT INTO rag_chunks (doc_id, hash, text) VALUES (?,?,?)", (doc_id, h, text)).lastrowid
                c.execute("INSERT INTO rag_vec (rowid, embedding) VALUES (?, ?)", (cid, blob))
                n += 1
        c.commit()
    return n


def search(vector: list[float], k: int, max_distance: float) -> list[dict]:
    rows = db.all(
        "SELECT v.rowid AS id, v.distance, c.text, d.title, d.source, d.url, d.license "
        "FROM (SELECT rowid, distance FROM rag_vec WHERE embedding MATCH ? AND k = ?) v "
        "JOIN rag_chunks c ON c.id = v.rowid JOIN rag_docs d ON d.id = c.doc_id ORDER BY v.distance",
        (sqlite_vec.serialize_float32(vector), k))
    return [dict(r) for r in rows if r["distance"] <= max_distance]


def by_epd(epd: str) -> dict | None:
    row = db.one("SELECT c.text, d.title, d.source, d.url, d.license FROM rag_docs d "
                 "JOIN rag_chunks c ON c.doc_id = d.id WHERE d.epd = ? ORDER BY c.id LIMIT 1", (epd,))
    return dict(row) if row else None
