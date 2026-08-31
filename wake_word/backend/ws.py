"""WebSocket inference handler for browser microphone."""

from __future__ import annotations

import asyncio
import json
import sys
import time
from collections import deque
from pathlib import Path

import numpy as np
from fastapi import WebSocket, WebSocketDisconnect

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import (
    COMMAND_DURATION_SECONDS,
    COOLDOWN_SECONDS,
    SAMPLE_RATE,
    SIGNAL_LENGTH,
    WAKE_THRESHOLD,
)
from inference.engine import InferenceEngine
from backend.brain import NevoBrain
from backend.events import EventBroadcaster


class InferenceSession:
    def __init__(
        self,
        ws: WebSocket,
        engine: InferenceEngine,
        brain: NevoBrain,
        broadcaster: EventBroadcaster,
    ) -> None:
        self.ws = ws
        self.engine = engine
        self.brain = brain
        self.broadcaster = broadcaster
        self.buffer: deque[int] = deque(maxlen=SAMPLE_RATE * (1 + COMMAND_DURATION_SECONDS))
        self.last_wake = 0.0
        self.capturing_command = False
        self.command_deadline = 0.0
        self.command_chunks: list[bytes] = []

    async def run(self) -> None:
        await self.ws.accept()
        await self.broadcaster.connect(self.ws)

        try:
            await self.ws.send_json(
                {
                    "event": "ready",
                    "data": {
                        "sample_rate": SAMPLE_RATE,
                        "window_samples": SIGNAL_LENGTH,
                        "threshold": WAKE_THRESHOLD,
                        "backend": self.engine.backend_name,
                    },
                }
            )

            while True:
                msg = await self.ws.receive()
                if msg["type"] == "websocket.disconnect":
                    break

                if "bytes" in msg and msg["bytes"]:
                    await self._handle_audio(msg["bytes"])
                elif "text" in msg and msg["text"]:
                    await self._handle_text(msg["text"])

        except WebSocketDisconnect:
            pass
        finally:
            await self.broadcaster.disconnect(self.ws)

    async def _handle_text(self, text: str) -> None:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return

        if payload.get("type") == "ping":
            await self.ws.send_json({"event": "pong", "data": {}})

    async def _handle_audio(self, chunk: bytes) -> None:
        samples = np.frombuffer(chunk, dtype=np.int16)
        self.buffer.extend(samples.tolist())

        if self.capturing_command:
            self.command_chunks.append(chunk)
            if time.time() >= self.command_deadline:
                await self._process_command()
            return

        if len(self.buffer) < SIGNAL_LENGTH:
            return

        window = np.array(list(self.buffer)[-SIGNAL_LENGTH:], dtype=np.int16)
        result = self.engine.predict_int16(window)
        now = time.time()

        await self.ws.send_json(
            {
                "event": "inference",
                "data": {
                    "background": round(result.background, 4),
                    "wake_word": round(result.wake_word, 4),
                    "is_wake": result.is_wake,
                },
            }
        )

        if result.is_wake and (now - self.last_wake) > COOLDOWN_SECONDS:
            self.last_wake = now
            self.capturing_command = True
            self.command_deadline = now + COMMAND_DURATION_SECONDS
            self.command_chunks = [window.tobytes()]

            await self.ws.send_json(
                {
                    "event": "wake_detected",
                    "data": {
                        "confidence": round(result.wake_word, 4),
                        "source": "browser",
                    },
                }
            )
            await self.broadcaster.broadcast(
                "wake_detected",
                {
                    "confidence": round(result.wake_word, 4),
                    "source": "browser",
                    "transcript": None,
                },
            )

    async def _process_command(self) -> None:
        self.capturing_command = False
        pcm = b"".join(self.command_chunks)
        self.command_chunks = []

        await self.ws.send_json(
            {"event": "transcribing", "data": {"source": "browser"}}
        )

        result = await self.brain.transcribe_pcm(pcm, source="browser")

        payload = {
            "transcript": result.transcript,
            "reply": result.reply,
            "duration_sec": result.duration_sec,
            "source": "browser",
        }
        await self.ws.send_json({"event": "transcript", "data": payload})
        await self.broadcaster.broadcast("transcript", payload)
