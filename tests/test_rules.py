from m2s.rules import median_from_notes, sing_display, sing_phones


def test_erinnern_has_both_glottal_stops():
    assert sing_display("ɛɐ̯ˈɪnɐn") == "ʔ ɛ ɐ ˈʔ ɪ n ɐ n"


def test_glottal_is_not_doubled_when_the_lexicon_already_has_it():
    assert sing_display("ʔɛɐ̯ˈʔɪnɐn") == "ʔ ɛ ɐ ˈʔ ɪ n ɐ n"


def test_unstressed_internal_vowel_gets_no_glottal_stop():
    assert sing_phones("a.a") == ["ʔ", "a", "a"]
    assert sing_phones("aˈa") == ["ʔ", "a", "ʔ", "a"]


def test_wir_coda_rhotic_becomes_a():
    assert sing_display("viːr") == "v iː ɐ"
    assert sing_display("viːʁ") == "v iː ɐ"
    assert sing_display("viːʀ") == "v iː ɐ"
    assert sing_display("viːɐ") == "v iː ɐ"
    assert "".join(sing_phones("viːr")) == "viːɐ"


def test_onset_rhotics_become_uvular_fricative():
    assert sing_phones("raːt")[0] == "ʁ"
    assert sing_phones("ʀaːt")[0] == "ʁ"
    assert sing_phones("tʁaː")[1] == "ʁ"
    assert sing_phones("traː")[1] == "ʁ"


def test_schwa_stays_without_a_median_and_opens_above_it():
    assert sing_display("bɪtə", "bitte") == "b ɪ t ə"
    assert sing_display("bɪtə", "bitte", 60, 60) == "b ɪ t ə"
    assert sing_display("bɪtə", "bitte", 72, 60) == "b ɪ t ɛ"


def test_rounded_schwa_syllable_opens_to_oe():
    assert sing_display("bøə", "böe", 72, 60) == "b ø œ"


def test_only_the_final_e_opens():
    assert sing_display("ɡəˈʁaːdə", "gerade", 80, 60) == "ɡ ə ˈʁ aː d ɛ"


def test_median_uses_only_notes_that_end_in_e_and_contain_schwa():
    median = median_from_notes(
        [
            ("bitte", ["b", "ɪ", "t", "ə"], 60),
            ("Bitte", ["b", "ɪ", "t", "ə"], 72),
            ("wir", ["v", "iː", "ɐ"], 64),
            ("Namen", ["n", "aː", "m", "ə"], 67),
        ]
    )
    assert median is not None
    assert median.count == 2
    assert median.midi == 66
