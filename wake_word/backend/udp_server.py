"""UDP server for ESP32 audio streaming."""

from __future__ import annotations

import asyncio
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import COMMAND_DURATION_SECONDS, SAMPLE_RATE, UDP_PORT
from protocol import PacketType, parse_udp_packet

if TYPE_CHECKING:
    from backend.brain import NevoBrain
    from backend.events import EventBroadcaster


@dataclass
class DeviceStatus:
    connected: bool = False
    last_packet_at: float | None = None
    last_wake_at: float | None = None
    packet_count: int = 0
    device_ip: str | None = None
    streaming: bool = False
    audio_buffer: list[bytes] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "connected": self.connected,
            "last_packet_at": self.last_packet_at,
            "last_wake_at": self.last_wake_at,
            "packet_count": self.packet_count,
            "device_ip": self.device_ip,
            "streaming": self.streaming,
        }


class UdpServer:
    def __init__(
        self,
        broadcaster: EventBroadcaster,
        brain: NevoBrain,
        host: str = "0.0.0.0",
        port: int = UDP_PORT,
    ) -> None:
        self.broadcaster = broadcaster
        self.brain = brain
        self.host = host
        self.port = port
        self.status = DeviceStatus()
        self._transport = None
        self._stream_deadline: float | None = None

    async def start(self) -> None:
        loop = asyncio.get_running_loop()
        self._transport, _ = await loop.create_datagram_endpoint(
            lambda: _UdpProtocol(self),
            local_addr=(self.host, self.port),
        )

    async def stop(self) -> None:
        if self._transport:
            self._transport.close()

    async def handle_datagram(self, data: bytes, addr: tuple[str, int]) -> None:
        packet = parse_udp_packet(data)
        if packet is None:
            return

        now = time.time()
        self.status.connected = True
        self.status.last_packet_at = now
        self.status.packet_count += 1
        self.status.device_ip = addr[0]

        if packet.is_wake:
            self.status.last_wake_at = now
            self.status.streaming = True
            self.status.audio_buffer = [packet.audio]
            self._stream_deadline = now + COMMAND_DURATION_SECONDS

            await self.broadcaster.broadcast(
                "device_wake",
                {
                    "device_ip": addr[0],
                    "sequence": packet.sequence,
                    "confidence": 1.0,
                    "source": "esp32",
                },
            )
        elif self.status.streaming:
            self.status.audio_buffer.append(packet.audio)
            if self._stream_deadline and now >= self._stream_deadline:
                await self._finish_stream()

        await self.broadcaster.broadcast(
            "device_status",
            self.status.to_dict(),
        )

    async def _finish_stream(self) -> None:
        self.status.streaming = False
        self._stream_deadline = None
        pcm = b"".join(self.status.audio_buffer)
        self.status.audio_buffer = []

        result = await self.brain.transcribe_pcm(pcm, source="esp32")
        await self.broadcaster.broadcast(
            "wake_detected",
            {
                "transcript": result.transcript,
                "reply": result.reply,
                "duration_sec": result.duration_sec,
                "source": "esp32",
            },
        )


class _UdpProtocol(asyncio.DatagramProtocol):
    def __init__(self, server: UdpServer) -> None:
        self.server = server

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        asyncio.create_task(self.server.handle_datagram(data, addr))
