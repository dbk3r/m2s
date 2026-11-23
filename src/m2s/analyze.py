"""Test and analysis loop for Phase 1.

A run records the vector checks. A finding may name one action from the
study: Nachaufnahme, Regeländerung, weiteres Training, or keine. A rule
change is written only when a TextGrid path is present. Hop size is not
changed from this loop.
"""

from __future__ import annotations

import csv
import hashlib
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from m2s.dsdict import GERMAN_G2P_CONSONANTS, GERMAN_G2P_VOWELS
from m2s.rules import read_median, sing_display

ACTIONS = ("Nachaufnahme", "Regeländerung", "weiteres Training", "keine")

# Study examples use ASCII length; the tokenizer stores IPA length.
EXAMPLE_PHONES = {
    "a:": "aː",
    "a": "a",
    "e:": "eː",
    "ɛ": "ɛ",
    "ə": "ə",
    "p": "p",
    "t": "t",
    "k": "k",
    "ʃ": "ʃ",
    "ç": "ç",
    "x": "x",
    "ʔ": "ʔ",
    "SP": "SP",
    "AP": "AP",
}

RULE_FINDINGS = {
    "glottal_absent_in_textgrid": "Regeländerung",
    "rhotic_sung_as_trill": "Regeländerung",
    "schwa_prefers_oe": "Regeländerung",
    "schwa_no_difference": "Regeländerung",
}
LISTEN_FINDINGS = {
    "ch_unclear": "Nachaufnahme",
    "glottal_unclear": "Nachaufnahme",
    "long_vowel_unclear": "Nachaufnahme",
}


@dataclass(frozen=True)
class Vector:
    orthography: str
    ipa: str
    phonemes: str
    midi: int | None
    status: str


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str
    action: str


def file_sha256(path: Path) -> str:
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_commit(cwd: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return "nogit"
    if result.returncode != 0:
        return "nogit"
    return result.stdout.strip() or "nogit"


def load_vectors(path: Path) -> list[Vector]:
    rows: list[Vector] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for record in csv.DictReader(handle, delimiter="\t"):
            midi = record.get("midi") or ""
            rows.append(
                Vector(
                    record["orthography"],
                    record["ipa"],
                    record["phonemes"],
                    int(midi) if midi else None,
                    record["status"],
                )
            )
    return rows


def check_vectors(vectors: list[Vector], median_path: Path) -> list[Check]:
    median = read_median(median_path)
    checks: list[Check] = []
    for vector in vectors:
        if vector.status == "offen":
            if median is None or vector.midi is None:
                checks.append(
                    Check(
                        f"vector:{vector.orthography}:{vector.midi or '-'}",
                        True,
                        "offen bis ein Schwa-Median aus dem Alignment vorliegt",
                        "keine",
                    )
                )
                continue
            expected = sing_display(
                vector.ipa, vector.orthography, vector.midi, median.midi
            )
            ok = expected == vector.phonemes
        elif vector.status == "belegt":
            expected = sing_display(
                vector.ipa,
                vector.orthography,
                vector.midi,
                None if vector.midi is None else (median.midi if median else None),
            )
            # Belegte Zeilen ohne Note dürfen den Median nicht brauchen.
            if vector.midi is None:
                expected = sing_display(vector.ipa, vector.orthography)
            ok = expected == vector.phonemes
        else:
            checks.append(
                Check(
                    f"vector:{vector.orthography}",
                    False,
                    f"unbekannter status {vector.status}",
                    "Regeländerung",
                )
            )
            continue
        checks.append(
            Check(
                f"vector:{vector.orthography}:{vector.midi or '-'}",
                ok,
                f"erwartet {vector.phonemes}, regel {expected}",
                "keine" if ok else "Regeländerung",
            )
        )
    return checks


def check_examples(phoneme_file: Path) -> list[Check]:
    if not phoneme_file.exists():
        return [
            Check(
                "phonemes",
                False,
                "phonemes.txt fehlt",
                "keine",
            )
        ]
    present = {
        line.strip()
        for line in phoneme_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    checks: list[Check] = []
    for label, phone in EXAMPLE_PHONES.items():
        ok = phone in present
        if phone in {"SP", "AP"}:
            detail = (
                "reservierter Marker, nicht aus dem Lexikon gezählt"
                if ok
                else "Marker fehlt"
            )
        elif ok:
            detail = "im Lexikon"
        else:
            detail = "kommt im Lexikon nicht vor; nicht erfunden"
        checks.append(Check(f"example:{label}", ok, detail, "keine"))
    return checks


def check_german_g2p_gap() -> Check:
    names = ", ".join(GERMAN_G2P_VOWELS + GERMAN_G2P_CONSONANTS)
    return Check(
        "german_g2p_replacements",
        True,
        "GermanG2p.cs nennt Symbole ohne IPA-Paare, daher kein replacements-Block: "
        + names,
        "keine",
    )


def suggest(finding: str) -> str:
    if finding in RULE_FINDINGS:
        return RULE_FINDINGS[finding]
    if finding in LISTEN_FINDINGS:
        return LISTEN_FINDINGS[finding]
    if finding == "plosive_smear":
        return "keine"
    if finding == "loss_still_falling":
        return "weiteres Training"
    if finding == "vectors_ok":
        return "keine"
    raise KeyError(finding)


def apply_finding(
    finding: str,
    *,
    rules_dir: Path,
    textgrid: Path | None,
    note: str,
) -> str:
    """Record one allowed follow-up. Rule files change only with a TextGrid."""
    action = suggest(finding)
    rules_dir.mkdir(parents=True, exist_ok=True)
    log = rules_dir / "findings.tsv"
    if not log.exists():
        log.write_text("finding\taction\tnote\ttextgrid\n", encoding="utf-8")
    grid = "" if textgrid is None else str(textgrid)
    with log.open("a", encoding="utf-8") as handle:
        handle.write(f"{finding}\t{action}\t{note}\t{grid}\n")
    if action == "Nachaufnahme":
        task = rules_dir / "nachaufnahme.txt"
        previous = task.read_text(encoding="utf-8") if task.exists() else ""
        task.write_text(previous + f"{finding}\t{note}\n", encoding="utf-8")
        return action
    if action == "weiteres Training":
        return action
    if action != "Regeländerung":
        return action
    if textgrid is None or not textgrid.exists():
        raise FileNotFoundError(
            "eine Regeländerung braucht eine vorhandene TextGrid-Datei"
        )
    marker = rules_dir / "rule-overrides.tsv"
    if not marker.exists():
        marker.write_text("finding\tnote\ttextgrid\n", encoding="utf-8")
    with marker.open("a", encoding="utf-8") as handle:
        handle.write(f"{finding}\t{note}\t{textgrid}\n")
    if finding == "schwa_no_difference":
        disabled = rules_dir / "schwa-median.off"
        disabled.write_text(f"{note}\t{textgrid}\n", encoding="utf-8")
    return action


def append_run(path: Path, row: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "run_id",
        "git",
        "phonemes_sha256",
        "audio_lock_sha256",
        "hours",
        "clips",
        "sample_rate",
        "sofa",
        "correction_pilot",
        "correction_rest",
        "ap_share",
        "vocoder",
        "acoustic",
        "step",
        "render",
        "ch",
        "glottal",
        "long_vowel",
        "wir",
        "e_low",
        "e_high",
        "action",
        "detail",
    ]
    new_file = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", extrasaction="ignore")
        if new_file:
            writer.writeheader()
        writer.writerow({key: row.get(key, "") for key in columns})


def phase1_report(phase_dir: Path, repo: Path) -> tuple[list[Check], dict[str, str]]:
    checks = check_vectors(
        load_vectors(phase_dir / "rules" / "vectors.tsv"),
        phase_dir / "rules" / "schwa-median.txt",
    )
    checks.extend(check_examples(phase_dir / "phonemes.txt"))
    checks.append(check_german_g2p_gap())
    failed = [check for check in checks if not check.ok]
    if failed:
        action = "Regeländerung"
        detail = "; ".join(check.name for check in failed)
    else:
        action = "keine"
        detail = f"{len(checks)} checks"
    run_id = datetime.now(timezone.utc).strftime("phase1-%Y%m%dT%H%M%SZ")
    row = {
        "run_id": run_id,
        "git": git_commit(repo),
        "phonemes_sha256": file_sha256(phase_dir / "phonemes.txt"),
        "audio_lock_sha256": "",
        "ch": "nicht im Take",
        "glottal": "nicht im Take",
        "long_vowel": "nicht im Take",
        "wir": "nicht im Take",
        "e_low": "nicht im Take",
        "e_high": "nicht im Take",
        "action": action,
        "detail": detail,
    }
    return checks, row
