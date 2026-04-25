from __future__ import annotations

import os
import logging
from typing import List, Optional

import httpx

from server.config import settings

logger = logging.getLogger("bkp-server.openai")


async def chat_completion(
    messages: List[dict],
    instructions: str,
    model: Optional[str] = None,
) -> str:
    """Call OpenAI Chat Completions API and return the assistant's reply text."""
    api_key = settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
    if not api_key:
        return "(OpenAI API key is not configured)"

    model = model or settings.OPENAI_CHAT_MODEL

    api_messages = [{"role": "system", "content": instructions}]
    api_messages.extend(messages)

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": api_messages,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


async def transcribe_audio(
    audio_bytes: bytes,
    filename: str = "audio.webm",
    model: str = "whisper-1",
    timeout: float = 60.0,
) -> str:
    """Transcribe audio using OpenAI.

    Prefer the official OpenAI Python SDK when available (better semantics
    and error handling). Fall back to the REST implementation via `httpx`.

    If no API key is available, fall back to a deterministic mock used by
    tests and local development.
    """
    api_key = settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")

    # Development fallback
    if not api_key:
        if b"trigger-stt-error" in audio_bytes:
            raise RuntimeError("STT worker failed")
        return f"Transcribed audio ({len(audio_bytes)} bytes)"

    # Try official OpenAI SDK first if present
    try:
        import openai

        openai.api_key = api_key
        # The SDK exposes an audio transcription helper. Use the file-like
        # interface: openai.Audio.transcribe or openai.Audio.transcriptions.create
        try:
            # Newer SDKs use openai.Audio.transcriptions.create
            resp = openai.Audio.transcriptions.create(file=audio_bytes, model=model)
            text = resp.get("text") or resp.get("transcript")
            if text:
                return text
        except Exception:
            # Try legacy helper if present
            try:
                resp = openai.Whisper.create(audio=audio_bytes, model=model)
                return resp.get("text") or ""
            except Exception:
                logger.exception("OpenAI SDK transcription failed, falling back to REST")
                # fall through to REST implementation
    except Exception:
        # SDK not available; continue to REST path
        pass

    # REST fallback using httpx
    url = "https://api.openai.com/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {api_key}"}

    async with httpx.AsyncClient(timeout=timeout) as client:
        files = {"file": (filename, audio_bytes, "application/octet-stream")}
        data = {"model": model}
        resp = await client.post(url, headers=headers, files=files, data=data)
        resp.raise_for_status()
        body = resp.json()
    return body.get("text") or body.get("transcript") or ""
