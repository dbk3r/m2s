"""Align a LilyPond melody with the Phase-1 dictionary.

The score is the public-domain C-major setting. Tempo is not in that file.
The MIDI file uses 120 BPM so a player can open it. That number is not a
claim about the song.

A word's dictionary phones are placed on the score syllables. A diphthong
``aɪ``, ``aʊ`` or ``ɔɪ`` is one nucleus. Between nuclei, the onset is the
longest suffix that the dictionary already uses at a word start and that
the next score syllable can spell. If that fails, the phones stay on the
first note of the word.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from m2s.ipa import is_vowel
from m2s.midi import write_midi

DIPHTHONGS = {("a", "ɪ"), ("a", "ʊ"), ("ɔ", "ɪ")}

PITCH = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11}
NOTE_RE = re.compile(r"([a-gr])(is|es)?([',]*)(\d+)")
NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


@dataclass(frozen=True)
class SyllableNote:
    syllable: str
    word: str
    word_index: int
    first_of_word: bool
    midi: int | None
    duration: int


def lilypond_midi(token: str) -> tuple[int | None, int]:
    match = NOTE_RE.fullmatch(token)
    if not match:
        raise ValueError(token)
    letter, accidental, marks, length = match.groups()
    ticks = 480 * 4 // int(length)
    if letter == "r":
        return None, ticks
    step = PITCH[letter]
    if accidental == "is":
        step += 1
    elif accidental == "es":
        step -= 1
    octave = marks.count("'") - marks.count(",")
    return 48 + 12 * octave + step, ticks


def note_name(midi: int | None) -> str:
    if midi is None:
        return "rest"
    return f"{NAMES[midi % 12]}{midi // 12 - 1}"


def _block(text: str, start: str) -> str:
    index = text.index(start) + len(start)
    depth = 1
    end = index
    while depth:
        if text[end] == "{":
            depth += 1
        elif text[end] == "}":
            depth -= 1
        end += 1
    return text[index : end - 1]


def parse_score(text: str) -> list[SyllableNote]:
    music = _block(text, "\\new Voice {")
    music = music[music.index("{") + 1 : music.index("\\addlyrics")]
    tokens = NOTE_RE.findall(music)
    pitches = []
    for letter, accidental, marks, length in tokens:
        pitches.append(lilypond_midi(f"{letter}{accidental or ''}{marks}{length}"))
    lyric_block = _block(text, "\\addlyrics")
    raw = lyric_block.replace("--", " -- ").split()
    words: list[list[str]] = []
    current: list[str] = []
    pending_join = False
    for token in raw:
        if token == "--":
            pending_join = True
            continue
        syllable = token.strip(".,;:!")
        if not any(character.isalpha() for character in syllable):
            continue
        if pending_join:
            current.append(syllable)
            pending_join = False
        else:
            if current:
                words.append(current)
            current = [syllable]
    if current:
        words.append(current)
    syllables = [(syllable, "".join(parts), index, pos == 0) for index, parts in enumerate(words) for pos, syllable in enumerate(parts)]
    sung = [item for item in pitches if item[0] is not None]
    if len(sung) != len(syllables):
        raise ValueError(f"{len(sung)} sung notes, {len(syllables)} syllables")
    notes: list[SyllableNote] = []
    syllable_index = 0
    for pitch, duration in pitches:
        if pitch is None:
            notes.append(SyllableNote("", "", -1, False, None, duration))
            continue
        syllable, word, word_index, first = syllables[syllable_index]
        notes.append(SyllableNote(syllable, word, word_index, first, pitch, duration))
        syllable_index += 1
    return notes


def nuclei(phones: list[str]) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    index = 0
    while index < len(phones):
        if not is_vowel(phones[index]):
            index += 1
            continue
        end = index + 1
        if end < len(phones) and (phones[index], phones[end]) in DIPHTHONGS:
            end += 1
        spans.append((index, end))
        index = end
    return spans


def attested_onsets(table: dict[str, list[str]]) -> set[tuple[str, ...]]:
    """Phoneme prefixes that start a dictionary pronunciation, before the vowel.

    A leading glottal stop is not part of the cluster. The empty onset is
    included, because a syllable may start with a vowel.
    """
    found: set[tuple[str, ...]] = {()}
    for variants in table.values():
        for line in variants:
            phones = line.split()
            prefix: list[str] = []
            for phone in phones:
                if is_vowel(phone):
                    break
                prefix.append(phone)
            else:
                continue
            if prefix[:1] == ["ʔ"]:
                prefix = prefix[1:]
            found.add(tuple(prefix))
    return found


def onset_matches(syllable: str, onset: tuple[str, ...]) -> bool:
    """Whether this score syllable can start with these onset phones.

    The spellings only choose among onsets the dictionary already attests.
    They do not create a pronunciation.
    """
    text = syllable.casefold()
    if not onset:
        return text[:1] in set("aeiouyäöü")
    spellings = {
        "ʃ": ("sch",),
        "ç": ("ch",),
        "x": ("ch",),
        "ŋ": ("ng",),
        "t͡s": ("tz", "z"),
        "ɡ": ("g",),
        "k": ("k", "ck"),
        "v": ("w",),
        "f": ("f", "v"),
        "z": ("s",),
        "s": ("s", "ss"),
    }
    for phone in onset:
        options = spellings.get(phone, (phone,))
        for option in options:
            if option and text.startswith(option):
                text = text[len(option) :]
                break
        else:
            return False
    return True


def split_phones(
    phones: list[str],
    syllables: list[str],
    onsets: set[tuple[str, ...]],
) -> list[list[str]] | None:
    spans = nuclei(phones)
    if len(spans) != len(syllables) or not syllables:
        return None
    parts: list[list[str]] = []
    cursor = 0
    for position, (start, end) in enumerate(spans):
        if position == 0:
            parts.append(phones[:end])
            cursor = end
            continue
        between = phones[cursor:start]
        cut = None
        for length in range(len(between), -1, -1):
            onset = tuple(between[len(between) - length :])
            if onset in onsets and onset_matches(syllables[position], onset):
                cut = len(between) - length
                break
        if cut is None:
            return None
        parts[-1].extend(phones[cursor : cursor + cut])
        parts.append(phones[cursor + cut : end])
        cursor = end
    parts[-1].extend(phones[cursor:])
    if len(parts) != len(syllables) or any(not part for part in parts):
        return None
    return parts


def load_dictionary(path: Path) -> dict[str, list[str]]:
    table: dict[str, list[str]] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            word, phones = line.rstrip("\n").split("\t", 1)
            table.setdefault(word, []).append(phones)
    return table


def lookup_word(table: dict[str, list[str]], word: str) -> list[str]:
    for key in (word, word.casefold(), word[:1].upper() + word[1:].casefold()):
        found = table.get(key)
        if found:
            return found
    return []


def syllable_phones(
    notes: list[SyllableNote],
    table: dict[str, list[str]],
    onsets: set[tuple[str, ...]],
) -> list[list[str]]:
    grouped: dict[int, list[int]] = {}
    for index, note in enumerate(notes):
        if note.midi is None:
            continue
        grouped.setdefault(note.word_index, []).append(index)
    assigned: list[list[str]] = [[] for _ in notes]
    for indexes in grouped.values():
        word = notes[indexes[0]].word
        variants = lookup_word(table, word)
        phones = variants[0].split() if variants else []
        parts = split_phones(phones, [notes[index].syllable for index in indexes], onsets) if phones else None
        if parts is None:
            assigned[indexes[0]] = phones
            continue
        for index, part in zip(indexes, parts):
            assigned[index] = part
    return assigned


def _flags(tokens: list[str], missing: bool, unsplit: bool) -> str:
    flags: list[str] = []
    if tokens[:1] == ["ʔ"]:
        flags.append("glottal")
    if "ç" in tokens:
        flags.append("ç")
    if "x" in tokens:
        flags.append("x")
    if "ə" in tokens:
        flags.append("schwa")
    if "ɐ" in tokens:
        flags.append("vocalic-r")
    if missing:
        flags.append("missing")
    if unsplit:
        flags.append("unsplit")
    return ",".join(flags)


def write_report(path: Path, notes: list[SyllableNote], table: dict[str, list[str]]) -> None:
    onsets = attested_onsets(table)
    per_note = syllable_phones(notes, table, onsets)
    lines = [
        "index\tsyllable\tword\tfirst\tmidi\tname\tticks\tphonemes\tvariants\tflags"
    ]
    for index, note in enumerate(notes):
        if note.midi is None:
            lines.append(f"{index + 1}\t\t\t\t\trest\t{note.duration}\t\t\t")
            continue
        variants = lookup_word(table, note.word) if note.first_of_word else []
        tokens = per_note[index]
        unsplit = note.first_of_word and bool(tokens) and sum(
            1 for item in notes if item.word_index == note.word_index and item.midi is not None
        ) > 1 and not any(
            per_note[other]
            for other, item in enumerate(notes)
            if item.word_index == note.word_index and not item.first_of_word
        )
        lines.append(
            "\t".join(
                [
                    str(index + 1),
                    note.syllable,
                    note.word,
                    "1" if note.first_of_word else "0",
                    str(note.midi),
                    note_name(note.midi),
                    str(note.duration),
                    " ".join(tokens),
                    str(len(variants)) if note.first_of_word else "",
                    _flags(tokens, note.first_of_word and not variants, unsplit),
                ]
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def export_song(score: Path, dictionary: Path, out: Path) -> list[SyllableNote]:
    notes = parse_score(score.read_text(encoding="utf-8"))
    table = load_dictionary(dictionary)
    per_note = syllable_phones(notes, table, attested_onsets(table))
    lyrics = [" ".join(phones) for phones in per_note]
    out.parent.mkdir(parents=True, exist_ok=True)
    write_midi(
        out.with_suffix(".mid"),
        [(note.midi, note.duration) for note in notes],
        lyrics=lyrics,
    )
    write_report(out.with_suffix(".tsv"), notes, table)
    write_ustx(out.with_suffix(".ustx"), notes)
    return notes


def write_ustx(path: Path, notes: list[SyllableNote]) -> None:
    """OpenUtau project. Lyrics are the score syllables, not our IPA phones.

    The phonemizer is the class in DiffSingerGermanMarzipanPhonemizer.cs
    on OpenUtau master. In the program it is labeled DIFFS DE MARZ.
    The singer stays empty until a voicebank is chosen.
    """
    phonemizer = "OpenUtau.Core.DiffSinger.DiDiffSingerGermanMarzipanPhonemizerr"
    lines = [
        "name: Hänschen klein",
        "comment: Gemeinfreie C-Dur-Fassung. Sänger in OpenUtau wählen, Phonemizer DIFFS DE MARZ.",
        "output_dir: Vocal",
        "cache_dir: UCache",
        'ustx_version: "0.6"',
        "resolution: 480",
        "bpm: 120",
        "beat_per_bar: 2",
        "beat_unit: 4",
        "tracks:",
        "- singer: \"\"",
        f"  phonemizer: {phonemizer}",
        "  renderer_settings:",
        "    renderer: DIFFSINGER",
        "  track_name: Vocal",
        "  mute: false",
        "  solo: false",
        "  volume: 0",
        "voice_parts:",
        "- name: Haenschen klein",
        '  comment: ""',
        "  track_no: 0",
        "  position: 0",
        "  notes:",
    ]
    position = 0
    for note in notes:
        if note.midi is None:
            position += note.duration
            continue
        lyric = note.syllable.replace('"', "")
        lines.extend(
            [
                f"  - position: {position}",
                f"    duration: {note.duration}",
                f"    tone: {note.midi}",
                f"    lyric: \"{lyric}\"",
                "    pitch:",
                "      data:",
                "      - {x: -40, y: 0, shape: io}",
                "      - {x: 40, y: 0, shape: io}",
                "      snap_first: true",
                "    vibrato: {length: 0, period: 175, depth: 25, in: 10, out: 10, shift: 0, drift: 0}",
                "    phoneme_expressions: []",
                "    phoneme_overrides: []",
            ]
        )
        position += note.duration
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
