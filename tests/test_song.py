from pathlib import Path

import pytest

from m2s.song import export_song, note_name, parse_score, split_phones

SCORE = Path("songs/haenschen-klein-c.ly")
DICTIONARY = Path("data/phase1/dictionary.txt")


def test_score_aligns_every_sung_note_with_one_syllable():
    notes = parse_score(SCORE.read_text(encoding="utf-8"))
    sung = [note for note in notes if note.midi is not None]
    rests = [note for note in notes if note.midi is None]
    assert len(sung) == 49
    assert len(rests) == 2
    assert sung[0].syllable == "Häns"
    assert sung[0].word == "Hänschen"
    assert note_name(sung[0].midi) == "G4"
    assert sung[1].syllable == "chen"
    assert sung[1].first_of_word is False
    assert sung[5].word == "allein"
    assert note_name(sung[-1].midi) == "C4"
    assert sung[-1].word == "geschwind"


@pytest.mark.skipif(not DICTIONARY.exists(), reason="dictionary is built locally")
def test_song_uses_the_dictionary_without_splitting_words(tmp_path: Path):
    notes = export_song(SCORE, DICTIONARY, tmp_path / "haenschen-klein")
    report = (tmp_path / "haenschen-klein.tsv").read_text(encoding="utf-8")
    assert (tmp_path / "haenschen-klein.mid").stat().st_size > 0
    assert "Häns\tHänschen\t1\t67\tG4\t240\th ɛ n s" in report
    assert "chen\tHänschen\t0\t64\tE4\t240\tç ə n" in report
    assert "al\tallein\t1\t62\tD4\t240\tʔ a" in report
    assert "lein\tallein\t0" in report
    assert "l a ɪ n" in report
    assert "ge\tgeschwind" in report
    assert "ɡ ə" in report
    assert "ʃ v ɪ n t" in report
    assert "nach\t1" in report
    assert "n aː x" in report
    assert "wei\tweite\t1" in report
    assert "v a ɪ" in report
    assert "te\tweite\t0" in report
    assert "t ə" in report
    assert (tmp_path / "haenschen-klein.ustx").read_text(encoding="utf-8").count("lyric:") == 49
    assert "DIFFSINGER" in (tmp_path / "haenschen-klein.ustx").read_text(encoding="utf-8")
    assert notes[0].word == "Hänschen"


def test_split_uses_the_syllable_spelling_and_an_attested_onset():
    onsets = {(), ("ç",), ("s", "ç"), ("l",), ("t",), ("ʃ", "v"), ("d",), ("z",)}
    assert split_phones("h ɛ n s ç ə n".split(), ["Häns", "chen"], onsets) == [
        ["h", "ɛ", "n", "s"],
        ["ç", "ə", "n"],
    ]
    assert split_phones("ʔ a l a ɪ n".split(), ["al", "lein"], onsets) == [
        ["ʔ", "a"],
        ["l", "a", "ɪ", "n"],
    ]
    assert split_phones("ɡ ə ʃ v ɪ n t".split(), ["ge", "schwind"], onsets) == [
        ["ɡ", "ə"],
        ["ʃ", "v", "ɪ", "n", "t"],
    ]
    assert split_phones("h ɪ n a ɪ n".split(), ["hin", "ein"], onsets) == [
        ["h", "ɪ", "n"],
        ["a", "ɪ", "n"],
    ]
    assert split_phones("k l a ɪ n".split(), ["klein"], onsets) == [["k", "l", "a", "ɪ", "n"]]
    assert split_phones("b a b a b a".split(), ["ba", "ba"], onsets) is None
