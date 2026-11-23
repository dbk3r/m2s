"""Pitch display, take check, and 24-bit WAV writing."""

from __future__ import annotations

import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np

DISPLAY_CENTER_CENTS = 35
DISPLAY_NEAR_CENTS = 80
NEEDLE_CENTS = 100.0
DISPLAY_RMS = 0.01
# RMS in dBFS. Display only, same role as the cent bands. Not an acceptance gate.
LEVEL_ZONE = {
    "leise": (-36.0, -24.0),
    "laut": (-18.0, -8.0),
}


def cents(hz: float, target_hz: float) -> float:
    return 1200.0 * np.log2(hz / target_hz)


def rms(samples: np.ndarray) -> float:
    if samples.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(samples))))


def dbfs(samples: np.ndarray) -> float:
    level = rms(samples)
    if level <= 1e-9:
        return -120.0
    return float(20.0 * np.log10(level))


def detect_hz(samples: np.ndarray, sample_rate: int, fmin: float = 50.0, fmax: float = 1000.0) -> float | None:
    if rms(samples) < DISPLAY_RMS:
        return None
    window = samples.astype(np.float64)
    window = window - window.mean()
    if window.size < 8:
        return None
    corr = np.correlate(window, window, mode="full")
    corr = corr[corr.size // 2 :]
    min_lag = max(1, int(sample_rate / fmax))
    max_lag = min(corr.size - 2, int(sample_rate / fmin))
    if max_lag <= min_lag:
        return None
    lag = int(np.argmax(corr[min_lag:max_lag])) + min_lag
    lag = _parabolic(corr, lag)
    if lag <= 0:
        return None
    return sample_rate / lag


def level_hint(level_db: float, dynamic: str) -> str:
    low, high = LEVEL_ZONE[dynamic]
    if level_db < low:
        return "lauter"
    if level_db > high:
        return "leiser"
    return "passt"


@dataclass(frozen=True)
class TakeCheck:
    usable: bool
    reasons: tuple[str, ...]
    seconds: float
    median_cents: float | None
    level_db: float | None

    def line(self) -> str:
        head = f"{self.seconds:.1f} s"
        if self.median_cents is not None and self.level_db is not None:
            head = f"{head} · {self.median_cents:.0f} Cent · {self.level_db:.0f} dBFS"
        if self.usable:
            return f"{head} · brauchbar"
        return f"{head} · nochmal: {', '.join(self.reasons)}"


def check_take(samples: np.ndarray, sample_rate: int, note: str, dynamic: str) -> TakeCheck:
    """Advice after a take. Same spans as the live display. Does not block keeping the take.

    Length 3–6 s is the study cut. Pitch uses the 80-cent display edge on the median
    of windows where a tone was found. Level uses that same sung audio against LEVEL_ZONE.
    A sample at full scale is clipping.
    """
    from m2s.record_jobs import note_hz

    seconds = samples.size / sample_rate if sample_rate else 0.0
    reasons: list[str] = []
    if seconds < 3 or seconds > 6:
        reasons.append("außerhalb 3–6 s")
    if samples.size and float(np.max(np.abs(samples))) >= 1.0:
        reasons.append("übersteuert")
    window = 2048
    offsets: list[float] = []
    voiced: list[np.ndarray] = []
    target = note_hz(note)
    if samples.size >= window:
        for start in range(0, samples.size - window + 1, window):
            chunk = samples[start : start + window]
            hz = detect_hz(chunk, sample_rate)
            if hz is None:
                continue
            offsets.append(abs(float(cents(hz, target))))
            voiced.append(chunk)
    median = float(np.median(offsets)) if offsets else None
    level = dbfs(np.concatenate(voiced)) if voiced else None
    if median is None:
        reasons.append("kein Ton")
    elif median > DISPLAY_NEAR_CENTS:
        reasons.append("Tonhöhe weit daneben")
    if level is not None:
        hint = level_hint(level, dynamic)
        if hint == "lauter":
            reasons.append("zu leise")
        elif hint == "leiser":
            reasons.append("zu laut")
    return TakeCheck(not reasons, tuple(reasons), seconds, median, level)


def display_band(cents_off: float) -> str:
    distance = abs(cents_off)
    if distance <= DISPLAY_CENTER_CENTS:
        return "mittig"
    if distance <= DISPLAY_NEAR_CENTS:
        return "daneben"
    return "weit"


def write_wav24(path: Path, samples: np.ndarray, sample_rate: int = 44100) -> None:
    clipped = np.clip(samples.astype(np.float64), -1.0, 1.0)
    ints = np.rint(clipped * (2**23 - 1)).astype(np.int32)
    raw = b"".join(int(value).to_bytes(4, "little", signed=True)[:3] for value in ints)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(3)
        handle.setframerate(sample_rate)
        handle.writeframes(raw)


def _parabolic(corr: np.ndarray, lag: int) -> float:
    left, center, right = float(corr[lag - 1]), float(corr[lag]), float(corr[lag + 1])
    denom = left - 2 * center + right
    if denom == 0:
        return float(lag)
    return lag + 0.5 * (left - right) / denom
