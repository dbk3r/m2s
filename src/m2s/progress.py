"""Read the latest trainer step from a log tail. Nothing is inferred beyond the printed numbers."""

import re

_STEP = re.compile(r"step=(\d+)")
_FRACTION = re.compile(r"(\d+)/(\d+)")


def parse_progress(text: str) -> tuple[int | None, int | None]:
    step = None
    total = None
    for line in text.splitlines():
        fraction = _FRACTION.search(line)
        if fraction:
            step = int(fraction.group(1))
            total = int(fraction.group(2))
        marked = _STEP.search(line)
        if marked:
            step = int(marked.group(1))
    return step, total


def log_tail(path, limit: int = 65536) -> str:
    if not path.is_file():
        return ""
    with path.open("rb") as handle:
        handle.seek(0, 2)
        size = handle.tell()
        handle.seek(max(0, size - limit))
        return handle.read().decode("utf-8", errors="replace")
