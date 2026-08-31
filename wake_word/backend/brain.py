"""Post-wake transcription and optional LLM reply."""

from __future__ import annotations

import asyncio
import io
import os
import struct
import wave
from dataclasses import dataclass
from typing import Any

import numpy as np

from config import SAMPLE_RATE


@dataclass
class BrainResult:
    transcript: str
    reply: str | None
    duration_sec: float
    source: str


class NevoBrain:
    def __init__(self) -> None:
        self._whisper = None
        self._whisper_lock = asyncio.Lock()
        self.llm_enabled = os.getenv("NEVO_LLM_ENABLED", "false").lower() == "true"
        self.llm_url = os.getenv("NEVO_LLM_URL", "http://localhost:11434/api/generate")
        self.llm_model = os.getenv("NEVO_LLM_MODEL", "phi3")

    async def _get_whisper(self):
        async with self._whisper_lock:
            if self._whisper is None:
                try:
                    from faster_whisper import WhisperModel
                except ImportError:
                    raise RuntimeError(
                        "faster-whisper not installed. Run: pip install faster-whisper"
                    )
                model_size = os.getenv("NEVO_WHISPER_MODEL", "tiny")
                self._whisper = WhisperModel(
                    model_size, device="cpu", compute_type="int8"
                )
            return self._whisper

    def _pcm_to_wav(self, pcm_bytes: bytes) -> bytes:
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(pcm_bytes)
        return buffer.getvalue()

    async def transcribe_pcm(self, pcm_bytes: bytes, source: str = "browser") -> BrainResult:
        if len(pcm_bytes) < SAMPLE_RATE * 2:
            return BrainResult(
                transcript="(audio too short)",
                reply=None,
                duration_sec=len(pcm_bytes) / (SAMPLE_RATE * 2),
                source=source,
            )

        wav_bytes = self._pcm_to_wav(pcm_bytes)
        duration = len(pcm_bytes) / (SAMPLE_RATE * 2)

        try:
            model = await self._get_whisper()
            audio = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            segments, _ = await asyncio.to_thread(
                model.transcribe,
                audio,
                language="he",
                beam_size=1,
            )
            transcript = " ".join(seg.text.strip() for seg in segments).strip()
            if not transcript:
                transcript = "(no speech detected)"
        except Exception as exc:
            transcript = f"(transcription error: {exc})"

        reply = None
        if self.llm_enabled and transcript and not transcript.startswith("("):
            reply = await self._generate_reply(transcript)

        return BrainResult(
            transcript=transcript,
            reply=reply,
            duration_sec=duration,
            source=source,
        )

    async def _generate_reply(self, transcript: str) -> str | None:
        try:
            import httpx

            prompt = (
                f"User said in Hebrew: '{transcript}'. "
                "Reply briefly and helpfully in Hebrew (1-2 sentences)."
            )
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    self.llm_url,
                    json={"model": self.llm_model, "prompt": prompt, "stream": False},
                )
                if resp.status_code == 200:
                    return resp.json().get("response", "").strip()
        except Exception:
            pass
        return None


def pcm_chunks_to_bytes(chunks: list[bytes]) -> bytes:
    return b"".join(chunks)


def int16_array_to_bytes(arr: np.ndarray) -> bytes:
    return arr.astype(np.int16).tobytes()
