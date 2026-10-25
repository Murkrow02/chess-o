"""Embeddings through Ollama's native /api/embed endpoint."""

import httpx

from ..config import settings


async def embed(texts: list[str], timeout: float = 120.0) -> list[list[float]]:
    async with httpx.AsyncClient(base_url=settings.embed_base_url, timeout=timeout) as client:
        r = await client.post("/api/embed", json={"model": settings.embed_model, "input": texts, "truncate": True})
        r.raise_for_status()
        return r.json()["embeddings"]
