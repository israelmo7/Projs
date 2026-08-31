"""UDP packet format for ESP32 ↔ host communication."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import IntEnum

from config import UDP_PACKET_AUDIO_SIZE


class PacketType(IntEnum):
    WAKE_WITH_BUFFER = 0
    STREAM_CHUNK = 1


@dataclass
class UdpPacket:
    packet_type: PacketType
    sequence: int
    timestamp_ms: int
    audio: bytes

    @property
    def is_wake(self) -> bool:
        return self.packet_type == PacketType.WAKE_WITH_BUFFER


def parse_udp_packet(data: bytes) -> UdpPacket | None:
    """
    Parse ESP32 UDP packet.

    Wake packet: 8-byte header (seq u32, timestamp u32) + 32000 bytes int16 audio.
    Stream packet: 8-byte header + up to 1024 bytes int16 audio.
    """
    if len(data) < 8:
        return None

    sequence, timestamp_ms = struct.unpack_from("<II", data, 0)
    audio = data[8:]

    if len(audio) >= 32000:
        packet_type = PacketType.WAKE_WITH_BUFFER
        audio = audio[:32000]
    else:
        packet_type = PacketType.STREAM_CHUNK
        audio = audio[:UDP_PACKET_AUDIO_SIZE]

    return UdpPacket(
        packet_type=packet_type,
        sequence=sequence,
        timestamp_ms=timestamp_ms,
        audio=audio,
    )
