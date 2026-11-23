from pathlib import Path

from m2s.analyze import (
    apply_finding,
    check_examples,
    check_vectors,
    load_vectors,
    phase1_report,
    suggest,
)
from m2s.fallback import LANG_PREFIX, CharsiuFallback, archive_missing

VECTORS = Path("data/phase1/rules/vectors.tsv")


def test_committed_vectors_match_the_rules():
    checks = check_vectors(load_vectors(VECTORS), Path("data/phase1/rules/schwa-median.txt"))
    failed = [check for check in checks if not check.ok]
    assert failed == []
    assert any(check.detail.startswith("offen") for check in checks)


def test_missing_example_is_recorded_and_not_invented(tmp_path: Path):
    phonemes = tmp_path / "phonemes.txt"
    phonemes.write_text("aː\nSP\nAP\n", encoding="utf-8")
    checks = {check.name: check for check in check_examples(phonemes)}
    assert checks["example:a:"].ok
    assert checks["example:ʃ"].ok is False
    assert checks["example:ʃ"].action == "keine"


def test_actions_match_the_study_and_rules_need_a_textgrid(tmp_path: Path):
    assert suggest("ch_unclear") == "Nachaufnahme"
    assert suggest("plosive_smear") == "keine"
    assert suggest("loss_still_falling") == "weiteres Training"
    assert suggest("glottal_absent_in_textgrid") == "Regeländerung"
    try:
        apply_finding(
            "glottal_absent_in_textgrid",
            rules_dir=tmp_path,
            textgrid=None,
            note="zweiter Knacklaut fehlt",
        )
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("rule change without TextGrid")
    grid = tmp_path / "take.TextGrid"
    grid.write_text("item\n", encoding="utf-8")
    action = apply_finding(
        "schwa_no_difference",
        rules_dir=tmp_path,
        textgrid=grid,
        note="tief und hoch gleich",
    )
    assert action == "Regeländerung"
    assert (tmp_path / "schwa-median.off").exists()
    assert (
        apply_finding(
            "ch_unclear",
            rules_dir=tmp_path,
            textgrid=None,
            note="ç und x",
        )
        == "Nachaufnahme"
    )
    assert (tmp_path / "nachaufnahme.txt").read_text(encoding="utf-8").startswith("ch_unclear")


def test_phase1_report_does_not_claim_a_listening_result(tmp_path: Path):
    phase = tmp_path / "phase"
    (phase / "rules").mkdir(parents=True)
    (phase / "rules" / "vectors.tsv").write_text(
        (VECTORS).read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (phase / "phonemes.txt").write_text(
        "\n".join(
            ["aː", "a", "eː", "ɛ", "ə", "p", "t", "k", "ʃ", "ç", "x", "ʔ", "SP", "AP"]
        )
        + "\n",
        encoding="utf-8",
    )
    _checks, row = phase1_report(phase, tmp_path)
    assert row["action"] == "keine"
    assert row["wir"] == "nicht im Take"
    assert row["glottal"] == "nicht im Take"


def test_german_prefix_is_the_charsiu_code():
    assert LANG_PREFIX == "<ger>: "


def test_fallback_archive_rejects_unknown_symbols_and_known_words(tmp_path: Path):
    def predict(word: str) -> str:
        return {"Nixdaheim": "nɪks", "Chryntz": "krʏnts", "Zephyrina": "t͡sɛ"}[word]

    rows = archive_missing(
        ["Zephyrina", "Nixdaheim", "Chryntz"],
        {"wir"},
        {"n", "ɪ", "k", "s", "ʏ", "t", "ɛ"},
        CharsiuFallback(predict),
        tmp_path / "fallback.tsv",
    )
    assert [row[3] for row in rows] == ["rejected:t͡s", "accepted", "rejected:ʁ"]
    text = (tmp_path / "fallback.tsv").read_text(encoding="utf-8")
    assert text.count("\n") == 4
    try:
        archive_missing(
            ["wir", "Nixdaheim", "Chryntz"],
            {"wir"},
            {"n"},
            CharsiuFallback(predict),
            tmp_path / "nope.tsv",
        )
    except ValueError:
        return
    raise AssertionError("known word must not be a fallback sample")
