"""Recording jobs from one singer folder under songs/aufnahme.

The note folders directly in songs/aufnahme are the shared text. Each singer
gets a copy, and that singer folder is the corpus for training.
"""

from __future__ import annotations

import math
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

NOTES = (
    "c2",
    "d#2",
    "f#2",
    "a2",
    "c3",
    "d#3",
    "f#3",
    "a3",
    "c4",
    "d#4",
    "f#4",
    "a4",
    "c5",
)
DYNAMICS = ("leise", "laut")
SAMPLE_RATE = 44100

_PITCH_CLASS = {
    "c": 0,
    "d": 2,
    "e": 4,
    "f": 5,
    "g": 7,
    "a": 9,
    "b": 11,
}
_NAMES = ("c", "c#", "d", "d#", "e", "f", "f#", "g", "g#", "a", "a#", "b")


@dataclass(frozen=True)
class Job:
    note: str
    dynamic: str
    number: int
    text: str
    txt_path: Path
    wav_path: Path

    @property
    def key(self) -> str:
        return f"{self.note}/{self.dynamic}/{self.wav_path.name}"


def note_midi(name: str) -> int:
    note = name.strip().lower()
    accidental = 0
    if note[1:2] == "#":
        accidental = 1
        octave = int(note[2:])
        letter = note[0]
    else:
        octave = int(note[1:])
        letter = note[0]
    return (octave + 1) * 12 + _PITCH_CLASS[letter] + accidental


def note_hz(name: str, a4: float = 440.0) -> float:
    return a4 * 2 ** ((note_midi(name) - 69) / 12)


def nearest_note(hz: float, a4: float = 440.0) -> str:
    midi = int(round(69 + 12 * math.log2(hz / a4)))
    octave = midi // 12 - 1
    return f"{_NAMES[midi % 12]}{octave}"


def list_singers(root: Path) -> list[str]:
    if not root.is_dir():
        return []
    names = []
    for path in sorted(root.iterdir()):
        if path.is_dir() and path.name not in NOTES and not path.name.startswith("."):
            names.append(path.name)
    return names


def singer_name_problem(name: str) -> str | None:
    cleaned = name.strip()
    if not cleaned:
        return "Der Name ist leer."
    if cleaned in NOTES:
        return "Dieser Name ist eine Note, kein Sänger."
    if cleaned != Path(cleaned).name or "/" in cleaned or "\\" in cleaned:
        return "Der Name darf kein Ordnertrenner sein."
    if cleaned.startswith("."):
        return "Der Name darf nicht mit einem Punkt beginnen."
    return None


def add_singer(root: Path, name: str) -> Path:
    problem = singer_name_problem(name)
    if problem:
        raise ValueError(problem)
    folder = root / name.strip()
    if folder.exists():
        raise FileExistsError(name.strip())
    copied = 0
    for note in NOTES:
        for dynamic in DYNAMICS:
            source = root / note / dynamic
            if not source.is_dir():
                continue
            dest = folder / note / dynamic
            dest.mkdir(parents=True)
            for txt in sorted(source.glob("*.txt")):
                shutil.copy2(txt, dest / txt.name)
                copied += 1
    if copied == 0:
        shutil.rmtree(folder, ignore_errors=True)
        raise ValueError("Die Vorlage hat keine Zeilen.")
    return folder


def remove_singer(root: Path, name: str) -> None:
    folder = root / name
    if name in NOTES or not folder.is_dir():
        raise FileNotFoundError(name)
    shutil.rmtree(folder)


def current_singer(root: Path) -> str | None:
    path = root / "current-singer.txt"
    if not path.is_file():
        return None
    name = path.read_text(encoding="utf-8").strip()
    if name in list_singers(root):
        return name
    return None


def remember_singer(root: Path, name: str | None) -> None:
    path = root / "current-singer.txt"
    if not name:
        path.unlink(missing_ok=True)
        return
    path.write_text(f"{name}\n", encoding="utf-8")


def discover(root: Path) -> list[Job]:
    jobs: list[Job] = []
    for note in NOTES:
        for dynamic in DYNAMICS:
            folder = root / note / dynamic
            if not folder.is_dir():
                continue
            for txt in sorted(folder.glob("*.txt")):
                number = int(txt.name.split("_", 1)[0])
                jobs.append(
                    Job(
                        note=note,
                        dynamic=dynamic,
                        number=number,
                        text=txt.read_text(encoding="utf-8").strip(),
                        txt_path=txt,
                        wav_path=txt.with_suffix(".wav"),
                    )
                )
    return jobs


class JobStatus:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path)
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS job (
                key TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                updated TEXT NOT NULL
            )
            """
        )
        self._db.commit()

    def close(self) -> None:
        self._db.close()

    def status(self, job: Job) -> str:
        if job.wav_path.is_file():
            return "done"
        row = self._db.execute("SELECT status FROM job WHERE key = ?", (job.key,)).fetchone()
        if row and row[0] == "skipped":
            return "skipped"
        return "open"

    def mark(self, job: Job, status: str) -> None:
        self._db.execute(
            """
            INSERT INTO job (key, status, updated) VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET status = excluded.status, updated = excluded.updated
            """,
            (job.key, status, datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")),
        )
        self._db.commit()

    def skip_note(self, jobs: list[Job], note: str) -> None:
        for job in jobs:
            if job.note == note and self.status(job) == "open":
                self.mark(job, "skipped")
