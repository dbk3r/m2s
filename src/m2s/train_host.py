"""Build the documented DiffSinger and SingingVocoders commands.

The WAV files stay on the training machine. corpus_dir is one singer folder,
such as songs/aufnahme/denis, not the shared text above it. A name in
transcriptions.csv is the path inside that folder, for example
c3/leise/001_ich_liebe_dich. This module refuses a run whose audio parameters
differ from the lock.
"""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from pathlib import Path

from m2s.audio_lock import audio_problems, load_yaml, resolve_config

STAGES = ("vocoder", "variance", "acoustic")
STAGE_BEFORE = {"vocoder": None, "variance": "vocoder", "acoustic": "variance"}


@dataclass(frozen=True)
class Host:
    token: str
    train_python: Path
    corpus_dir: Path
    diffsinger_dir: Path
    singingvocoders_dir: Path
    vocoder_checkpoint: Path
    vocoder_config: Path
    variance_config: Path
    acoustic_config: Path
    work_dir: Path
    preprocess_workers: int
    exp_vocoder: str
    exp_variance: str
    exp_acoustic: str
    mel_base: str
    lock: Path
    test_ds: Path | None = None


def load_host(path: Path) -> Host:
    data = load_yaml(path)

    def as_path(key: str) -> Path:
        value = data.get(key)
        if not isinstance(value, str) or not value:
            raise ValueError(f"{key} fehlt in {path}")
        candidate = Path(value)
        if not candidate.is_absolute():
            candidate = Path.cwd() / candidate
        return candidate

    workers = data.get("preprocess_workers")
    if not isinstance(workers, int) or isinstance(workers, bool):
        raise ValueError(f"preprocess_workers fehlt in {path}")
    return Host(
        token=str(data.get("token") or ""),
        train_python=as_path("train_python"),
        corpus_dir=as_path("corpus_dir"),
        diffsinger_dir=as_path("diffsinger_dir"),
        singingvocoders_dir=as_path("singingvocoders_dir"),
        vocoder_checkpoint=as_path("vocoder_checkpoint"),
        vocoder_config=as_path("vocoder_config"),
        variance_config=as_path("variance_config"),
        acoustic_config=as_path("acoustic_config"),
        work_dir=as_path("work_dir"),
        preprocess_workers=workers,
        exp_vocoder=str(data.get("exp_vocoder") or "vocoder"),
        exp_variance=str(data.get("exp_variance") or "variance"),
        exp_acoustic=str(data.get("exp_acoustic") or "acoustic"),
        mel_base=str(data.get("mel_base") or ""),
        lock=as_path("lock"),
        test_ds=_optional_path(data.get("test_ds")),
    )


def readiness(host: Host) -> list[str]:
    """Paths, locked audio parameters, and the corpus. Serving does not require this to be empty."""
    problems = _install_problems(host)
    if host.corpus_dir.is_dir():
        problems.extend(_corpus_problems(host.corpus_dir))
    elif host.corpus_dir:
        problems.append(f"corpus_dir fehlt: {host.corpus_dir}")
    return problems


def stage_problems(host: Host, stage: str, finished: set[str]) -> list[str]:
    if stage not in STAGES:
        return [f"unbekannte Stufe {stage}"]
    problems = _install_problems(host)
    earlier = STAGE_BEFORE[stage]
    if earlier and earlier not in finished:
        problems.append(f"zuerst {earlier}")
    if stage == "vocoder":
        problems.extend(_vocoder_paths(host))
    elif host.corpus_dir.is_dir():
        problems.extend(_corpus_problems(host.corpus_dir))
    else:
        problems.append(f"corpus_dir fehlt: {host.corpus_dir}")
    return problems


def stage_commands(host: Host, stage: str, reset: bool) -> list[tuple[list[str], Path]]:
    python = str(host.train_python)
    if stage == "vocoder":
        return [
            (
                [
                    python,
                    "process.py",
                    "--config",
                    str(host.vocoder_config),
                    "--num_cpu",
                    str(host.preprocess_workers),
                    "--strx",
                    "0",
                ],
                host.singingvocoders_dir,
            ),
            (
                [
                    python,
                    "train.py",
                    "--config",
                    str(host.vocoder_config),
                    "--exp_name",
                    host.exp_vocoder,
                    "--work_dir",
                    str(host.work_dir),
                ],
                host.singingvocoders_dir,
            ),
        ]
    config = host.variance_config if stage == "variance" else host.acoustic_config
    exp = host.exp_variance if stage == "variance" else host.exp_acoustic
    train = [python, "scripts/train.py", "--config", str(config), "--exp_name", exp]
    if reset:
        train.append("--reset")
    return [
        ([python, "scripts/binarize.py", "--config", str(config)], host.diffsinger_dir),
        (train, host.diffsinger_dir),
    ]


def _optional_path(value) -> Path | None:
    if not isinstance(value, str) or not value:
        return None
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    return candidate


def test_command(host: Host, stage: str) -> tuple[list[str], Path]:
    """Inference command from DiffSinger GettingStarted. There is no vocoder infer script there."""
    if stage not in {"variance", "acoustic"}:
        raise ValueError("ein Test läuft für variance oder acoustic")
    if host.test_ds is None:
        raise ValueError("test_ds fehlt in der Host-Datei")
    exp = host.exp_variance if stage == "variance" else host.exp_acoustic
    return (
        [str(host.train_python), "scripts/infer.py", stage, str(host.test_ds), "--exp", exp],
        host.diffsinger_dir,
    )


def export_command(host: Host, stage: str, checkpoint: Path | None) -> tuple[list[str], Path]:
    python = str(host.train_python)
    if stage == "vocoder":
        if checkpoint is None:
            raise ValueError("Vocoder-Export braucht den feinjustierten Checkpoint")
        return (
            [
                python,
                "scripts/export.py",
                "nsf-hifigan",
                "--config",
                str(host.acoustic_config),
                "--ckpt",
                str(checkpoint),
            ],
            host.diffsinger_dir,
        )
    kind = "variance" if stage == "variance" else "acoustic"
    exp = host.exp_variance if stage == "variance" else host.exp_acoustic
    return (
        [python, "scripts/export.py", kind, "--exp", exp],
        host.diffsinger_dir,
    )


def _install_problems(host: Host) -> list[str]:
    problems = []
    for label, path in (
        ("train_python", host.train_python),
        ("diffsinger_dir", host.diffsinger_dir),
        ("singingvocoders_dir", host.singingvocoders_dir),
        ("vocoder_checkpoint", host.vocoder_checkpoint),
        ("vocoder_config", host.vocoder_config),
        ("variance_config", host.variance_config),
        ("acoustic_config", host.acoustic_config),
        ("lock", host.lock),
    ):
        if not path.exists():
            problems.append(f"{label} fehlt: {path}")
    if host.lock.is_file():
        problems.extend(_lock_problems(host))
    return problems


def _lock_problems(host: Host) -> list[str]:
    problems = []
    for label, config, root in (
        ("vocoder_config", host.vocoder_config, host.singingvocoders_dir),
        ("variance_config", host.variance_config, host.diffsinger_dir),
        ("acoustic_config", host.acoustic_config, host.diffsinger_dir),
    ):
        if not config.is_file():
            continue
        try:
            resolved = resolve_config(config, root)
        except ValueError as exc:
            problems.append(f"{label}: {exc}")
            continue
        for problem in audio_problems(resolved, host.mel_base):
            problems.append(f"{label}: {problem}")
        for problem in windows_backend_problems(resolved, os.name):
            problems.append(f"{label}: {problem}")
    return problems


def windows_backend_problems(resolved: dict, platform: str) -> list[str]:
    """NCCL exists on Linux. A native Windows run cannot use that backend."""
    if platform != "nt":
        return []
    strategy = resolved.get("pl_trainer_strategy")
    backend = strategy.get("process_group_backend") if isinstance(strategy, dict) else None
    if backend == "nccl":
        return ["process_group_backend ist nccl. Unter Windows gibt es NCCL nicht, auf gloo stellen"]
    return []


def _vocoder_paths(host: Host) -> list[str]:
    if not host.vocoder_config.is_file():
        return []
    data = resolve_config(host.vocoder_config, host.singingvocoders_dir)
    paths = data.get("data_input_path") or []
    if not paths:
        return ["vocoder_config: data_input_path ist leer"]
    problems = []
    for entry in paths:
        candidate = Path(str(entry))
        if not candidate.is_absolute():
            candidate = host.singingvocoders_dir / candidate
        if not candidate.exists():
            problems.append(f"vocoder_config: data_input_path fehlt: {candidate}")
    ckpt = data.get("finetune_ckpt_path")
    if ckpt:
        candidate = Path(str(ckpt))
        if not candidate.is_absolute():
            candidate = host.singingvocoders_dir / candidate
        if candidate != host.vocoder_checkpoint and not candidate.exists():
            problems.append(f"vocoder_config: finetune_ckpt_path fehlt: {candidate}")
    return problems


def _corpus_problems(corpus: Path) -> list[str]:
    table = corpus / "transcriptions.csv"
    if not table.is_file():
        return ["transcriptions.csv fehlt im Korpus"]
    problems = []
    with table.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        for required in ("name", "ph_seq", "ph_dur"):
            if required not in fields:
                problems.append(f"transcriptions.csv ohne Spalte {required}")
        if problems:
            return problems
        rows = 0
        for row in reader:
            rows += 1
            name = (row.get("name") or "").strip()
            phones = (row.get("ph_seq") or "").split()
            durations = (row.get("ph_dur") or "").split()
            if not name or not phones:
                problems.append("transcriptions.csv hat eine leere Zeile")
                continue
            if len(durations) != len(phones):
                problems.append(f"{name}: ph_dur passt nicht zu ph_seq")
            for suffix in (".wav", ".flac"):
                if (corpus / f"{name}{suffix}").is_file():
                    break
            else:
                problems.append(f"{name}: WAV oder FLAC fehlt")
        if rows == 0:
            problems.append("transcriptions.csv hat keine Zeilen")
    return problems
