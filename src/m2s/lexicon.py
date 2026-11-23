"""Word → IPA from a wiktextract JSONL extract of German Wiktionary.

Each line is one JSON object. German entries are ``lang_code`` ``de``.
Pronunciations are ``sounds[].ipa``; dialect labels stay in ``sounds[].tags``.
Audio-only sound objects are skipped. Malformed IPA is rejected instead of
being mapped onto a neighbour phone.
"""

from __future__ import annotations

import gzip
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator

from m2s.ipa import reject_reason
from m2s.rules import sing_phones

# Dump dated 2026-11-01, read from the Kaikki raw-data page on 2026-11-23.
# That page states the dump date and the wiktextract commits. It does not
# state a license sentence; none is invented here.
KAIKKI_URL = "https://kaikki.org/dewiktionary/raw-wiktextract-data.jsonl.gz"
KAIKKI_PAGE = "https://kaikki.org/dewiktionary/rawdata.html"
DUMP_DATE = "2026-11-01"
WIKTEXTRACT_COMMIT = "19f9a3006a405fb7bfb40193dca41c7117a009a5"
WIKITEXTPROCESSOR_COMMIT = "6f96ddf5f3466707f1869fe6618390fd77dfd109"


@dataclass
class Pronunciation:
    ipa: str
    tags: list[str]
    phonemes: list[str]


@dataclass
class Entry:
    word: str
    pronunciations: list[Pronunciation] = field(default_factory=list)


@dataclass
class Rejected:
    word: str
    ipa: str
    reason: str


def open_text(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    return path.open(encoding="utf-8")


def iter_german(path: Path) -> Iterator[tuple[Entry | None, list[Rejected]]]:
    with open_text(path) as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if record.get("lang_code") != "de":
                continue
            word = record.get("word")
            if not isinstance(word, str) or not word:
                continue
            entry = Entry(word)
            rejected: list[Rejected] = []
            for sound in record.get("sounds") or []:
                ipa = sound.get("ipa")
                if not isinstance(ipa, str):
                    continue
                tags = [tag for tag in (sound.get("tags") or []) if isinstance(tag, str)]
                reason = reject_reason(ipa)
                if reason:
                    rejected.append(Rejected(word, ipa, reason))
                    continue
                try:
                    phonemes = sing_phones(ipa, lyric=word)
                except ValueError as error:
                    rejected.append(Rejected(word, ipa, str(error)))
                    continue
                if not phonemes:
                    rejected.append(Rejected(word, ipa, "empty"))
                    continue
                entry.pronunciations.append(Pronunciation(ipa, tags, phonemes))
            if entry.pronunciations or rejected:
                yield entry if entry.pronunciations else None, rejected


def load(path: Path) -> tuple[dict[str, Entry], list[Rejected]]:
    merged: dict[str, Entry] = {}
    rejected: list[Rejected] = []
    for entry, bad in iter_german(path):
        rejected.extend(bad)
        if entry is None:
            continue
        current = merged.get(entry.word)
        if current is None:
            merged[entry.word] = entry
        else:
            current.pronunciations.extend(entry.pronunciations)
    return merged, rejected


def count_phonemes(
    entries: Iterable[Entry],
) -> dict[str, dict[str, object]]:
    counts: dict[str, dict[str, object]] = {}
    for entry in entries:
        seen: set[str] = set()
        for pronunciation in entry.pronunciations:
            for phone in pronunciation.phonemes:
                bucket = counts.setdefault(
                    phone, {"count": 0, "examples": []}
                )
                if phone not in seen:
                    bucket["count"] = int(bucket["count"]) + 1
                    seen.add(phone)
                examples: list[str] = bucket["examples"]  # type: ignore[assignment]
                if entry.word not in examples and len(examples) < 3:
                    examples.append(entry.word)
    return counts


def phoneme_list(counts: dict[str, dict[str, object]]) -> list[str]:
    ordered = sorted(counts, key=lambda phone: (-int(counts[phone]["count"]), phone))
    for marker in ("SP", "AP"):
        if marker not in ordered:
            ordered.append(marker)
    return ordered


def write_lexicon(path: Path, entries: dict[str, Entry]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for word in sorted(entries):
            entry = entries[word]
            payload = {
                "word": word,
                "pronunciations": [
                    {
                        "ipa": item.ipa,
                        "tags": item.tags,
                        "phonemes": item.phonemes,
                    }
                    for item in entry.pronunciations
                ],
            }
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def write_dictionary(path: Path, entries: dict[str, Entry]) -> None:
    """DiffSinger training dictionary: syllable, tab, phones separated by space."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for word in sorted(entries):
            seen: set[tuple[str, ...]] = set()
            for item in entries[word].pronunciations:
                key = tuple(item.phonemes)
                if key in seen:
                    continue
                seen.add(key)
                handle.write(f"{word}\t{' '.join(item.phonemes)}\n")


def write_rejected(path: Path, rejected: list[Rejected]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write("word\tipa\treason\n")
        for item in rejected:
            ipa = item.ipa.replace("\t", " ").replace("\n", " ")
            handle.write(f"{item.word}\t{ipa}\t{item.reason}\n")


def write_counts(path: Path, counts: dict[str, dict[str, object]], phones: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write("phoneme\tcount\texamples\n")
        for phone in phones:
            if phone in {"SP", "AP"}:
                handle.write(f"{phone}\t0\t\n")
                continue
            bucket = counts[phone]
            examples = " ".join(bucket["examples"])  # type: ignore[arg-type]
            handle.write(f"{phone}\t{bucket['count']}\t{examples}\n")


def write_phonemes(path: Path, phones: list[str]) -> None:
    path.write_text("\n".join(phones) + "\n", encoding="utf-8")


def lookup(entries: dict[str, Entry], word: str) -> Entry | None:
    found = entries.get(word)
    if found is not None:
        return found
    return entries.get(word.casefold()) or entries.get(word[:1].upper() + word[1:].casefold())


def missing_symbols(phonemes: list[str], allowed: set[str]) -> list[str]:
    return [phone for phone in phonemes if phone not in allowed]


def example_phones(entries: dict[str, Entry]) -> set[str]:
    found: set[str] = set()
    for entry in entries.values():
        for item in entry.pronunciations:
            found.update(item.phonemes)
    return found
