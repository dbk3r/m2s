"""Singing post-processing locked in Studie 1.

Glottal stop: before a vowel-initial word, including an unstressed prefix,
and before a vowel-initial stressed syllable (``ˈ``).
Onset ``r`` / ``ʁ`` / ``ʀ`` become ``ʁ``. A consonantal rhotic in the coda
becomes ``ɐ``.
Final ``-e`` stays ``ə`` in the dictionary. Above the median MIDI note of
sung ``-e`` it opens to ``ɛ``, or to ``œ`` when that syllable's lexicon IPA
already contains ``ø`` or ``œ``.
"""

from __future__ import annotations

import hashlib
import statistics
from dataclasses import dataclass
from pathlib import Path

from m2s.ipa import RHOTICS, Syllable, display, is_rounded, is_vowel, phones_of, tokenize

TRAILING = ".,;:!?\"'“”„»«"


@dataclass(frozen=True)
class SchwaMedian:
    midi: float
    count: int
    transcriptions_sha256: str


def copy_syllables(syllables: list[Syllable]) -> list[Syllable]:
    return [syllable.copy() for syllable in syllables]


def normalize_r(syllables: list[Syllable]) -> list[Syllable]:
    result = copy_syllables(syllables)
    for syllable in result:
        nucleus = next(
            (index for index, phone in enumerate(syllable.phones) if is_vowel(phone)),
            None,
        )
        if nucleus is None:
            continue
        for index, phone in enumerate(syllable.phones):
            if phone not in RHOTICS:
                continue
            syllable.phones[index] = "ʁ" if index < nucleus else "ɐ"
    return result


def insert_glottal(syllables: list[Syllable]) -> list[Syllable]:
    result = copy_syllables(syllables)
    if result and result[0].phones and is_vowel(result[0].phones[0]):
        result[0].phones.insert(0, "ʔ")
    for syllable in result:
        if (
            syllable.stress == "ˈ"
            and syllable.phones
            and is_vowel(syllable.phones[0])
        ):
            syllable.phones.insert(0, "ʔ")
    return result


def lyric_ends_with_e(lyric: str) -> bool:
    text = lyric.strip().rstrip(TRAILING).casefold()
    return text.endswith("e")


def open_schwa(
    syllables: list[Syllable],
    lyric: str,
    midi_note: int | None,
    median: float | None,
) -> list[Syllable]:
    result = copy_syllables(syllables)
    if median is None or midi_note is None or midi_note <= median:
        return result
    if not lyric_ends_with_e(lyric) or not result or not result[-1].phones:
        return result
    if result[-1].phones[-1] != "ə":
        return result
    rounded = any(is_rounded(phone) for phone in result[-1].phones)
    result[-1].phones[-1] = "œ" if rounded else "ɛ"
    return result


def sing(
    ipa: str,
    lyric: str = "",
    midi_note: int | None = None,
    median: float | None = None,
) -> list[Syllable]:
    """Dictionary rules first. Schwa opening only when a note and a median exist."""
    syllables = insert_glottal(normalize_r(tokenize(ipa)))
    return open_schwa(syllables, lyric, midi_note, median)


def sing_display(
    ipa: str,
    lyric: str = "",
    midi_note: int | None = None,
    median: float | None = None,
) -> str:
    return display(sing(ipa, lyric, midi_note, median))


def sing_phones(
    ipa: str,
    lyric: str = "",
    midi_note: int | None = None,
    median: float | None = None,
) -> list[str]:
    return phones_of(sing(ipa, lyric, midi_note, median))


def median_from_notes(notes: list[tuple[str, list[str], int]]) -> SchwaMedian | None:
    """Median of MIDI notes whose lyric ends in -e and whose phones include ə."""
    chosen = sorted(
        midi
        for lyric, phones, midi in notes
        if lyric_ends_with_e(lyric) and "ə" in phones
    )
    if not chosen:
        return None
    return SchwaMedian(float(statistics.median(chosen)), len(chosen), "")


def write_median(path: Path, median: SchwaMedian, transcriptions: Path) -> None:
    digest = hashlib.sha256(transcriptions.read_bytes()).hexdigest()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                f"midi_median\t{median.midi}",
                f"count\t{median.count}",
                f"transcriptions_sha256\t{digest}",
                "",
            ]
        ),
        encoding="utf-8",
    )


def read_median(path: Path) -> SchwaMedian | None:
    if not path.exists():
        return None
    fields: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        key, value = line.split("\t", 1)
        fields[key] = value
    return SchwaMedian(
        float(fields["midi_median"]),
        int(fields["count"]),
        fields["transcriptions_sha256"],
    )
