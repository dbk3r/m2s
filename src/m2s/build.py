"""Build the Phase-1 artifacts from a wiktextract JSONL file."""

from __future__ import annotations

from pathlib import Path

from m2s.dsdict import write_dsdict, write_german_g2p_symbols
from m2s.lexicon import (
    DUMP_DATE,
    KAIKKI_PAGE,
    KAIKKI_URL,
    WIKITEXTPROCESSOR_COMMIT,
    WIKTEXTRACT_COMMIT,
    count_phonemes,
    load,
    phoneme_list,
    write_counts,
    write_dictionary,
    write_lexicon,
    write_phonemes,
    write_rejected,
)


def provenance(phone_count: int, word_count: int, rejected: int) -> str:
    return "\n".join(
        [
            "# Provenienz Wörterbuch",
            "",
            f"- Seite: {KAIKKI_PAGE}",
            f"- Datei: {KAIKKI_URL}",
            f"- Dump-Datum laut Seite: {DUMP_DATE}",
            f"- wiktextract: {WIKTEXTRACT_COMMIT}",
            f"- wikitextprocessor: {WIKITEXTPROCESSOR_COMMIT}",
            "- Lizenzsatz auf der gelesenen Seite: keiner. Es wird keiner ergänzt.",
            f"- Deutsche Einträge mit mindestens einer IPA: {word_count}",
            f"- Verworfene IPA-Felder: {rejected}",
            f"- Phoneme einschließlich SP und AP: {phone_count}",
            "",
            "Verworfen wird nur, was `reject_reason` in `m2s.ipa` nennt:",
            "leer, Platzhalter mit führendem `-`, `{`/`}`, Ellipse, `/`, nur Betonungszeichen.",
            "Seltene Laute bleiben in der Zählliste.",
            "",
        ]
    )


def build(jsonl: Path, out: Path) -> dict[str, int]:
    entries, rejected = load(jsonl)
    counts = count_phonemes(entries.values())
    phones = phoneme_list(counts)
    out.mkdir(parents=True, exist_ok=True)
    (out / "rules").mkdir(exist_ok=True)
    write_lexicon(out / "lexicon.jsonl", entries)
    write_dictionary(out / "dictionary.txt", entries)
    write_rejected(out / "dictionary.rejected.tsv", rejected)
    write_counts(out / "phonemes.counts.tsv", counts, phones)
    write_phonemes(out / "phonemes.txt", phones)
    write_dsdict(out / "dsdict-de.yaml", entries, phones)
    write_german_g2p_symbols(out / "german-g2p-symbols.txt")
    (out / "PROVENANCE.md").write_text(
        provenance(len(phones), len(entries), len(rejected)),
        encoding="utf-8",
    )
    return {
        "words": len(entries),
        "rejected": len(rejected),
        "phonemes": len(phones),
    }
