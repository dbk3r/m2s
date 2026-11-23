"""OpenUtau ``dsdict-de.yaml`` and the DiffSinger symbol list.

``DiffSingerGermanPhonemizer.GetDictionaryName()`` returns ``dsdict-de.yaml``.
``GermanG2p.cs`` lists symbol names and does not pair them with IPA, so this
writer does not invent a ``replacements`` block. The names are stored beside
the dictionary for the analysis report.
"""

from __future__ import annotations

from pathlib import Path

from m2s.ipa import symbol_type
from m2s.lexicon import Entry

# Copied from DiffSingerGermanPhonemizer.cs (OpenUtau commit cc700f92).
GERMAN_G2P_VOWELS = (
    "aa", "ae", "ah", "ao", "aw", "ax", "ay", "ee", "eh", "er", "ex",
    "ih", "iy", "oe", "ohh", "ooh", "oy", "ue", "uh", "uw", "yy",
)
GERMAN_G2P_CONSONANTS = (
    "b", "cc", "ch", "d", "dh", "f", "g", "hh", "jh", "k", "l", "m",
    "n", "ng", "p", "pf", "q", "r", "rr", "s", "sh", "t", "th", "ts",
    "v", "w", "x", "y", "z", "zh",
)


def yaml_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def write_dsdict(path: Path, entries: dict[str, Entry], phones: list[str]) -> None:
    lines = ["symbols:"]
    for phone in phones:
        lines.append(f"- symbol: {yaml_quote(phone)}")
        lines.append(f"  type: {symbol_type(phone)}")
    lines.append("entries:")
    for word in sorted(entries):
        seen: set[tuple[str, ...]] = set()
        for item in entries[word].pronunciations:
            key = tuple(item.phonemes)
            if key in seen:
                continue
            seen.add(key)
            rendered = ", ".join(yaml_quote(phone) for phone in item.phonemes)
            lines.append(f"- grapheme: {yaml_quote(word)}")
            lines.append(f"  phonemes: [{rendered}]")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_german_g2p_symbols(path: Path) -> None:
    vowels = " ".join(GERMAN_G2P_VOWELS)
    consonants = " ".join(GERMAN_G2P_CONSONANTS)
    path.write_text(
        "\n".join(
            [
                "# Source: OpenUtau DiffSingerGermanPhonemizer.cs @ cc700f92",
                "# GermanG2p.cs lists these names and no IPA equivalents.",
                f"vowels\t{vowels}",
                f"consonants\t{consonants}",
                "",
            ]
        ),
        encoding="utf-8",
    )
