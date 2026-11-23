"""CharsiuG2P / ByT5 fallback for words missing from the lexicon.

The German prefix is ``<ger>: ``, including the space after the colon.
``ger`` is the code in ``lang_list.txt`` of lingjzhu/CharsiuG2P. The model
id is the one in that repository's README.
"""

from __future__ import annotations

from pathlib import Path

from m2s.ipa import reject_reason
from m2s.rules import sing_phones

LANG_PREFIX = "<ger>: "
MODEL_ID = "charsiu/g2p_multilingual_byT5_tiny_16_layers_100"
TOKENIZER_ID = "google/byt5-small"
LANG_LIST_URL = "https://github.com/lingjzhu/CharsiuG2P/blob/main/lang_list.txt"


class CharsiuFallback:
    """Lazy loader. Tests pass ``predict`` so the model is not required."""

    def __init__(self, predict=None):
        self._predict = predict
        self._model = None
        self._tokenizer = None

    def predict_ipa(self, word: str) -> str:
        if self._predict is not None:
            return self._predict(word)
        if self._model is None:
            from transformers import AutoTokenizer, T5ForConditionalGeneration

            self._tokenizer = AutoTokenizer.from_pretrained(TOKENIZER_ID)
            self._model = T5ForConditionalGeneration.from_pretrained(MODEL_ID)
        prefixed = LANG_PREFIX + word
        encoded = self._tokenizer(
            [prefixed],
            padding=True,
            add_special_tokens=False,
            return_tensors="pt",
        )
        predicted = self._model.generate(**encoded, num_beams=1, max_length=50)
        decoded = self._tokenizer.batch_decode(predicted.tolist(), skip_special_tokens=True)
        return decoded[0]

    def phonemes(self, word: str, allowed: set[str]) -> tuple[str, list[str], list[str]]:
        raw = self.predict_ipa(word)
        reason = reject_reason(raw)
        if reason:
            return raw, [], [reason]
        try:
            phones = sing_phones(raw, lyric=word)
        except ValueError as error:
            return raw, [], [str(error)]
        unknown = [phone for phone in phones if phone not in allowed]
        return raw, phones, unknown


def write_archive(path: Path, rows: list[tuple[str, str, str, str]]) -> None:
    """word, raw IPA, phonemes or empty, accepted or rejected."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write("word\traw_ipa\tphonemes\tstatus\n")
        for word, raw, phones, status in rows:
            handle.write(f"{word}\t{raw}\t{phones}\t{status}\n")


def archive_missing(
    words: list[str],
    known: set[str],
    allowed: set[str],
    fallback: CharsiuFallback,
    path: Path,
) -> list[tuple[str, str, str, str]]:
    rows: list[tuple[str, str, str, str]] = []
    for word in words:
        if word in known or word.casefold() in {item.casefold() for item in known}:
            raise ValueError(f"{word} is in the lexicon; the fallback sample must be a miss")
        raw, phones, unknown = fallback.phonemes(word, allowed)
        if unknown or not phones:
            status = "rejected:" + ",".join(unknown or ["empty"])
            rendered = ""
        else:
            status = "accepted"
            rendered = " ".join(phones)
        rows.append((word, raw, rendered, status))
    if len(rows) < 3:
        raise ValueError("the fallback archive needs a name, a coinage, and a ch-word")
    write_archive(path, rows)
    return rows
