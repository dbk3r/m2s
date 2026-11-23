"""Minimal Standard MIDI file, one track, for the song test."""

from __future__ import annotations

from pathlib import Path


def _varlen(value: int) -> bytes:
    buffer = value & 0x7F
    out = bytearray()
    value >>= 7
    while value:
        buffer <<= 8
        buffer |= (value & 0x7F) | 0x80
        value >>= 7
    while True:
        out.append(buffer & 0xFF)
        if buffer & 0x80:
            buffer >>= 8
        else:
            break
    return bytes(out)


def _text(kind: int, value: str) -> bytes:
    encoded = value.encode("utf-8")
    return bytes((0xFF, kind, len(encoded))) + encoded


def write_midi(
    path: Path,
    notes: list[tuple[int | None, int]],
    tempo_us: int = 500_000,
    lyrics: list[str] | None = None,
) -> None:
    """notes are (midi or None for a rest, duration in ticks). Quarter = 480 ticks.

    A rest is added to the next event's delta. Lyric events are MIDI text
    events on the sung notes.
    """
    events = bytearray()
    events += b"\x00\xff\x51\x03" + tempo_us.to_bytes(3, "big")
    events += b"\x00\xff\x58\x04\x02\x02\x18\x08"
    pending = 0
    for index, (pitch, duration) in enumerate(notes):
        if pitch is None:
            pending += duration
            continue
        events += _varlen(pending)
        pending = 0
        lyric = "" if lyrics is None else lyrics[index]
        if lyric:
            events += b"\x00" + _text(0x05, lyric)
        events += b"\x00" + bytes((0x90, pitch, 80))
        events += _varlen(duration) + bytes((0x80, pitch, 0))
    events += _varlen(pending) + b"\xff\x2f\x00"
    track = len(events).to_bytes(4, "big")
    header = b"MThd" + (6).to_bytes(4, "big") + (0).to_bytes(2, "big")
    header += (1).to_bytes(2, "big") + (480).to_bytes(2, "big")
    path.write_bytes(header + b"MTrk" + track + events)
