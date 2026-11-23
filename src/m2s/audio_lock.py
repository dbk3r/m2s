"""Compare a training config with the locked audio parameters of study 1."""

from __future__ import annotations

from pathlib import Path

import yaml

LOCKED = {
    "sample_rate": 44100,
    "hop_size": 512,
    "win_size": 2048,
    "fft_size": 2048,
    "num_mel_bins": 128,
    "fmin": 40,
    "fmax": 16000,
}

ALIASES = {
    "sample_rate": ("audio_sample_rate", "sample_rate"),
    "hop_size": ("hop_size",),
    "win_size": ("win_size",),
    "fft_size": ("fft_size",),
    "num_mel_bins": ("audio_num_mel_bins", "num_mel_bins"),
    "fmin": ("fmin",),
    "fmax": ("fmax",),
}


def load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} enthält kein YAML-Objekt")
    return data


def resolve_config(path: Path, root: Path) -> dict:
    """Merge base_config files. The child overrides the base."""
    return _resolve(path, root, depth=0)


def _resolve(path: Path, root: Path, depth: int) -> dict:
    if depth > 6:
        raise ValueError(f"base_config in {path} ist zu tief verschachtelt")
    data = load_yaml(path)
    merged: dict = {}
    bases = data.get("base_config") or []
    if isinstance(bases, str):
        bases = [bases]
    for base in bases:
        base_path = _find_base(path, root, str(base))
        merged = _overlay(merged, _resolve(base_path, root, depth + 1))
    return _overlay(merged, {key: value for key, value in data.items() if key != "base_config"})


def _find_base(config: Path, root: Path, relative: str) -> Path:
    for candidate in (root / relative, config.parent / relative):
        if candidate.is_file():
            return candidate
    raise ValueError(f"base_config {relative} von {config} fehlt")


def _overlay(base: dict, child: dict) -> dict:
    merged = dict(base)
    for key, value in child.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _overlay(merged[key], value)
        else:
            merged[key] = value
    return merged


def audio_problems(resolved: dict, mel_base: str) -> list[str]:
    problems = []
    for name, expected in LOCKED.items():
        found = _lookup(resolved, ALIASES[name])
        if found is None:
            problems.append(f"{name} fehlt in der Trainingskonfiguration")
            continue
        if _number(found) != expected:
            problems.append(f"{name} ist {found}, gesperrt ist {expected}")
    if not mel_base:
        problems.append("mel_base ist leer. Sie wird am gepinnten ONNX abgelesen")
    else:
        found = resolved.get("mel_base")
        if found is None:
            problems.append("mel_base fehlt in der Trainingskonfiguration")
        elif str(found) != mel_base:
            problems.append(f"mel_base ist {found}, die Host-Datei sagt {mel_base}")
    return problems


def _lookup(data: dict, names: tuple[str, ...]):
    for name in names:
        if name in data:
            return data[name]
    return None


def _number(value) -> float:
    return float(value)
