from pathlib import Path

from m2s.build import build
from m2s.ipa import reject_reason
from m2s.lexicon import load

FIXTURE = Path(__file__).parent / "fixtures" / "de.jsonl"


def test_reject_reason_names_the_dump_patterns():
    assert reject_reason("-") == "empty"
    assert reject_reason("-foo") == "placeholder"
    assert reject_reason("a/b") == "slash"
    assert reject_reason("ˈ") == "stress-only"
    assert reject_reason("[haˈloː]") is None


def test_fixture_keeps_german_variants_and_rejects_junk():
    entries, rejected = load(FIXTURE)
    assert "Hallo" not in entries
    assert [item.phonemes for item in entries["erinnern"].pronunciations] == [
        ["ʔ", "ɛ", "ɐ", "ʔ", "ɪ", "n", "ɐ", "n"]
    ]
    assert entries["wir"].pronunciations[0].phonemes == ["v", "iː", "ɐ"]
    reasons = {item.reason for item in rejected}
    assert reasons == {"empty", "slash"}


def test_build_writes_phoneme_list_markers_and_dsdict(tmp_path: Path):
    summary = build(FIXTURE, tmp_path)
    phones = (tmp_path / "phonemes.txt").read_text(encoding="utf-8").split()
    assert phones[-2:] == ["SP", "AP"]
    assert "ʔ" in phones
    assert "ç" in phones
    assert "x" in phones
    assert summary["words"] == 6
    dsdict = (tmp_path / "dsdict-de.yaml").read_text(encoding="utf-8")
    assert "replacements:" not in dsdict
    assert 'grapheme: "erinnern"' in dsdict
    assert 'type: vowel' in dsdict
    assert "GermanG2p.cs" in (tmp_path / "german-g2p-symbols.txt").read_text(encoding="utf-8")
    provenance = (tmp_path / "PROVENANCE.md").read_text(encoding="utf-8")
    assert "2026-11-01" in provenance
    assert "keiner" in provenance
    dictionary = (tmp_path / "dictionary.txt").read_text(encoding="utf-8")
    assert "erinnern\tʔ ɛ ɐ ʔ ɪ n ɐ n\n" in dictionary
