"""IPA segmentation for the singing dictionary.

Length marks ``:`` and ``ː`` after a vowel are one symbol (``a:`` in the
study brief is the same mark as IPA ``aː``). The non-syllabic sign ``̯``
is dropped, so ``ɐ̯`` is the phoneme ``ɐ``. A tie bar keeps an affricate
as one symbol. Stress and syllable dots are structure, not phonemes.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field

# IPA vowel letters. Used only to find the syllable nucleus and to mark
# OpenUtau vowel symbols. The German inventory is whatever the lexicon yields.
VOWEL_LETTERS = frozenset(
    "aeiouyæøœəɐɛɪɔʊʏɒɑʌɯɨɵɜɞɘɤ"
)
ROUNDED_LETTERS = frozenset("øœ")
LENGTH = frozenset("ːˑ:")
TIE = frozenset("͜͡")
DROP = frozenset("̯")
STRESS = frozenset("ˈˌ")
RHOTICS = frozenset("rʁʀ")

# OpenUtau only branches on vowel and semivowel. The other type names are
# the manner labels from the voicebank dictionary note.
STOPS = frozenset("pbtdkɡgʔcq")
NASALS = frozenset("mnŋɲɴ")
FRICATIVES = frozenset("fvszʃʒçʝxɣχʁhɦθðʂʐɕʑβɸ")
LIQUIDS = frozenset("lɫʎɭʀrɾɽ")
SEMIVOWELS = frozenset("jwɥʍ")


@dataclass
class Syllable:
    stress: str | None = None
    phones: list[str] = field(default_factory=list)

    def copy(self) -> Syllable:
        return Syllable(self.stress, list(self.phones))


def is_vowel(symbol: str) -> bool:
    base = symbol.replace("ː", "").replace("ˑ", "").replace(":", "")
    return bool(base) and base[0] in VOWEL_LETTERS


def is_rounded(symbol: str) -> bool:
    base = symbol.replace("ː", "").replace("ˑ", "").replace(":", "")
    return bool(base) and base[0] in ROUNDED_LETTERS


def symbol_type(symbol: str) -> str:
    if symbol in {"SP", "AP"} or is_vowel(symbol):
        return "vowel"
    if "͡" in symbol or "͜" in symbol:
        return "affricate"
    base = symbol.replace("ː", "").replace("ˑ", "")
    letter = base[0] if base else ""
    if letter in STOPS:
        return "stop"
    if letter in NASALS:
        return "nasal"
    if letter in LIQUIDS:
        return "liquid"
    if letter in SEMIVOWELS:
        return "semivowel"
    if letter in FRICATIVES:
        return "fricative"
    return "fricative"


def _combining(char: str) -> bool:
    return unicodedata.category(char) in {"Mn", "Mc"}


def unwrap(ipa: str) -> str:
    text = ipa.strip()
    if len(text) >= 2 and text[0] == "[" and text[-1] == "]":
        text = text[1:-1]
    elif len(text) >= 2 and text[0] == "/" and text[-1] == "/":
        text = text[1:-1]
    return text.replace(" ", "").replace("\u200b", "")


def reject_reason(ipa: str) -> str | None:
    """Malformed Wiktionary IPA. Valid rare phones are kept and counted."""
    raw = ipa.strip()
    if not raw or raw == "-":
        return "empty"
    if raw[0] == "-":
        return "placeholder"
    if any(mark in raw for mark in "{}"):
        return "template"
    if "…" in raw or "..." in raw:
        return "ellipsis"
    if "/" in raw:
        return "slash"
    body = unwrap(raw)
    if not body or set(body) <= set("ˈˌ.\"'"):
        return "stress-only"
    return None


def tokenize(ipa: str) -> list[Syllable]:
    """Split one IPA pronunciation into syllables and phones."""
    reason = reject_reason(ipa)
    if reason:
        raise ValueError(reason)
    text = unwrap(ipa)
    syllables = [Syllable()]
    current = ""
    index = 0

    def flush() -> None:
        nonlocal current
        if not current:
            return
        if current[-1] == ":" and len(current) > 1 and is_vowel(current[:-1]):
            current = current[:-1] + "ː"
        syllables[-1].phones.append(current)
        current = ""

    while index < len(text):
        char = text[index]
        if char in DROP:
            index += 1
            continue
        if char in STRESS or char == ".":
            flush()
            if char in STRESS:
                if syllables[-1].phones or syllables[-1].stress:
                    syllables.append(Syllable(char))
                else:
                    syllables[-1].stress = char
            elif syllables[-1].phones:
                syllables.append(Syllable())
            index += 1
            continue
        if char in TIE:
            current += char
            index += 1
            if index < len(text):
                current += text[index]
                index += 1
            continue
        if current and (_combining(char) or char in LENGTH):
            if char == ":" and not is_vowel(current):
                flush()
                current = char
            else:
                current += char
            index += 1
            continue
        flush()
        current = char
        index += 1
    flush()
    return [syllable for syllable in syllables if syllable.phones or syllable.stress]


def display(syllables: list[Syllable]) -> str:
    parts: list[str] = []
    for syllable in syllables:
        for index, phone in enumerate(syllable.phones):
            if index == 0 and syllable.stress:
                parts.append(syllable.stress + phone)
            else:
                parts.append(phone)
    return " ".join(parts)


def phones_of(syllables: list[Syllable]) -> list[str]:
    return [phone for syllable in syllables for phone in syllable.phones]
