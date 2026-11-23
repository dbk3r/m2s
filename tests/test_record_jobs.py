import wave
from pathlib import Path

import numpy as np

from m2s.record_audio import cents, check_take, detect_hz, display_band, level_hint, write_wav24
from m2s.record_jobs import (
    SAMPLE_RATE,
    JobStatus,
    add_singer,
    current_singer,
    discover,
    list_singers,
    nearest_note,
    note_hz,
    note_midi,
    remember_singer,
    remove_singer,
)


def test_note_names_use_a4_at_440():
    assert note_midi("c2") == 36
    assert note_midi("d#2") == 39
    assert note_hz("a4") == 440
    assert abs(note_hz("c3") - 130.81) < 0.02
    assert nearest_note(note_hz("c3")) == "c3"
    assert nearest_note(note_hz("d#2")) == "d#2"
    assert nearest_note(note_hz("a4") * 2 ** (30 / 1200)) == "a4"


def test_discovered_plan_follows_the_folders():
    root = Path("songs/aufnahme")
    jobs = discover(root)
    assert len(jobs) == 13 * 2 * 165
    assert jobs[0].note == "c2"
    assert jobs[0].dynamic == "leise"
    assert jobs[0].number == 1
    assert jobs[0].text == "ich liebe dich"
    assert jobs[0].wav_path.name == "001_ich_liebe_dich.wav"
    assert jobs[0].key == "c2/leise/001_ich_liebe_dich.wav"


def test_a_singer_folder_copies_the_text_and_can_be_removed(tmp_path: Path):
    template = tmp_path / "c3" / "leise"
    template.mkdir(parents=True)
    (template / "001_probe.txt").write_text("probe\n", encoding="utf-8")
    assert list_singers(tmp_path) == []
    folder = add_singer(tmp_path, "denis")
    assert folder == tmp_path / "denis"
    assert (folder / "c3" / "leise" / "001_probe.txt").read_text(encoding="utf-8") == "probe\n"
    assert list_singers(tmp_path) == ["denis"]
    jobs = discover(folder)
    assert len(jobs) == 1
    assert jobs[0].wav_path == folder / "c3" / "leise" / "001_probe.wav"
    remember_singer(tmp_path, "denis")
    assert current_singer(tmp_path) == "denis"
    try:
        add_singer(tmp_path, "c3")
    except ValueError as exc:
        assert "Note" in str(exc)
    else:
        raise AssertionError("note name was accepted")
    remove_singer(tmp_path, "denis")
    assert list_singers(tmp_path) == []
    assert (template / "001_probe.txt").is_file()


def test_a_sine_at_c3_lands_near_the_target():
    target = note_hz("c3")
    times = np.arange(8192) / SAMPLE_RATE
    samples = 0.4 * np.sin(2 * np.pi * target * times)
    found = detect_hz(samples.astype(np.float32), SAMPLE_RATE)
    assert found is not None
    assert abs(cents(found, target)) < 15
    assert display_band(cents(found, target)) == "mittig"


def test_wav_is_44100_mono_24bit_and_skip_leaves_open_jobs(tmp_path: Path):
    folder = tmp_path / "c3" / "leise"
    folder.mkdir(parents=True)
    txt = folder / "001_probe.txt"
    txt.write_text("probe\n", encoding="utf-8")
    jobs = discover(tmp_path)
    assert len(jobs) == 1
    samples = np.linspace(-0.5, 0.5, 100, dtype=np.float32)
    write_wav24(jobs[0].wav_path, samples, SAMPLE_RATE)
    with wave.open(str(jobs[0].wav_path), "rb") as handle:
        assert handle.getframerate() == 44100
        assert handle.getnchannels() == 1
        assert handle.getsampwidth() == 3
    status = JobStatus(tmp_path / "record.sqlite")
    assert status.status(jobs[0]) == "done"
    jobs[0].wav_path.unlink()
    assert status.status(jobs[0]) == "open"
    status.skip_note(jobs, "c3")
    assert status.status(jobs[0]) == "skipped"


def test_level_hint_follows_the_dynamic():
    assert level_hint(-40, "leise") == "lauter"
    assert level_hint(-30, "leise") == "passt"
    assert level_hint(-20, "leise") == "leiser"
    assert level_hint(-24, "laut") == "lauter"
    assert level_hint(-12, "laut") == "passt"
    assert level_hint(-6, "laut") == "leiser"


def _tone(note: str, seconds: float, level_db: float) -> np.ndarray:
    target = note_hz(note)
    times = np.arange(int(seconds * SAMPLE_RATE)) / SAMPLE_RATE
    amplitude = 10 ** (level_db / 20) * np.sqrt(2)
    return (amplitude * np.sin(2 * np.pi * target * times)).astype(np.float32)


def test_a_take_inside_the_spans_is_usable():
    check = check_take(_tone("c3", 4.0, -30), SAMPLE_RATE, "c3", "leise")
    assert check.usable
    assert check.line().endswith("brauchbar")


def test_a_take_outside_the_spans_asks_for_another():
    short = check_take(_tone("c3", 1.0, -30), SAMPLE_RATE, "c3", "leise")
    assert short.reasons == ("außerhalb 3–6 s",)
    quiet = check_take(_tone("c3", 4.0, -38), SAMPLE_RATE, "c3", "leise")
    assert "zu leise" in quiet.reasons
    off = check_take(_tone("e3", 4.0, -30), SAMPLE_RATE, "c3", "leise")
    assert "Tonhöhe weit daneben" in off.reasons
    silence = check_take(np.zeros(4 * SAMPLE_RATE, dtype=np.float32), SAMPLE_RATE, "c3", "leise")
    assert "kein Ton" in silence.reasons
    clipped = np.clip(_tone("c3", 4.0, -6), -1.0, 1.0)
    clipped[0] = 1.0
    assert "übersteuert" in check_take(clipped, SAMPLE_RATE, "c3", "laut").reasons


def test_display_bands_are_not_used_as_names_only():
    assert display_band(0) == "mittig"
    assert display_band(20) == "mittig"
    assert display_band(50) == "daneben"
    assert display_band(81) == "weit"
