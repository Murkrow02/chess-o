"""Minimal streaming client for any OpenAI-compatible chat endpoint (Ollama, vLLM, llama.cpp)."""

import json
from collections.abc import AsyncIterator

import httpx

from ..config import settings

_client: httpx.AsyncClient | None = None


def client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        headers = {"Authorization": f"Bearer {settings.llm_api_key}"} if settings.llm_api_key else {}
        _client = httpx.AsyncClient(base_url=settings.llm_base_url.rstrip("/"), headers=headers,
                                    timeout=httpx.Timeout(settings.llm_timeout, connect=5))
    return _client


async def stream_chat(messages: list[dict], max_tokens: int = 140, temperature: float = 0.6,
                      model: str | None = None) -> AsyncIterator[str]:
    body = {"model": model or settings.llm_model, "messages": messages, "stream": True,
            "max_tokens": max_tokens, "temperature": temperature}
    if settings.llm_reasoning_effort:
        body["reasoning_effort"] = settings.llm_reasoning_effort
    async with client().stream("POST", "/chat/completions", json=body) as r:
        r.raise_for_status()
        async for line in r.aiter_lines():
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            delta = json.loads(data)["choices"][0].get("delta", {}).get("content")
            if delta:
                yield delta


async def chat(messages: list[dict], **kw) -> str:
    return "".join([t async for t in stream_chat(messages, **kw)])
