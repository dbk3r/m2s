"""SQLite record of training, export, and test runs on the Windows machine."""

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from m2s.progress import log_tail, parse_progress


@dataclass
class RunRecord:
    id: str
    kind: str
    stage: str
    status: str
    step: int | None
    step_total: int | None
    returncode: int | None
    started_at: str
    finished_at: str | None
    log_path: Path
    commands: list[tuple[list[str], Path]]
    command_index: int
    pid: int | None = None


class TrainStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                stage TEXT NOT NULL,
                status TEXT NOT NULL,
                step INTEGER,
                step_total INTEGER,
                returncode INTEGER,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                log_path TEXT NOT NULL,
                commands TEXT NOT NULL,
                command_index INTEGER NOT NULL,
                pid INTEGER
            )
            """
        )
        for run_id, pid in self._db.execute(
            "SELECT id, pid FROM runs WHERE status = 'running'"
        ).fetchall():
            if _alive(pid):
                continue
            self._db.execute(
                """
                UPDATE runs
                SET status = 'interrupted', finished_at = ?, pid = NULL
                WHERE id = ?
                """,
                (_now(), run_id),
            )
        self._db.commit()

    def add(self, record: RunRecord) -> None:
        self._db.execute(
            """
            INSERT INTO runs (
                id, kind, stage, status, step, step_total, returncode,
                started_at, finished_at, log_path, commands, command_index, pid
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            _row(record),
        )
        self._db.commit()

    def save(self, record: RunRecord) -> None:
        self._db.execute(
            """
            UPDATE runs SET
                status = ?, step = ?, step_total = ?, returncode = ?,
                finished_at = ?, command_index = ?, pid = ?
            WHERE id = ?
            """,
            (
                record.status,
                record.step,
                record.step_total,
                record.returncode,
                record.finished_at,
                record.command_index,
                record.pid,
                record.id,
            ),
        )
        self._db.commit()

    def get(self, run_id: str) -> RunRecord | None:
        row = self._db.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return None if row is None else _record(row)

    def list_runs(self) -> list[RunRecord]:
        rows = self._db.execute("SELECT * FROM runs ORDER BY started_at DESC").fetchall()
        return [_record(row) for row in rows]

    def finished_stages(self) -> set[str]:
        rows = self._db.execute(
            "SELECT stage FROM runs WHERE kind = 'train' AND status = 'succeeded'"
        ).fetchall()
        return {row[0] for row in rows}

    def refresh(self, record: RunRecord) -> RunRecord:
        step, total = parse_progress(log_tail(record.log_path))
        if step is None and total is None:
            return record
        record.step = step if step is not None else record.step
        record.step_total = total if total is not None else record.step_total
        self._db.execute(
            "UPDATE runs SET step = ?, step_total = ? WHERE id = ?",
            (record.step, record.step_total, record.id),
        )
        self._db.commit()
        return record


def new_record(run_id: str, kind: str, stage: str, log_path: Path, commands) -> RunRecord:
    return RunRecord(
        id=run_id,
        kind=kind,
        stage=stage,
        status="running",
        step=None,
        step_total=None,
        returncode=None,
        started_at=_now(),
        finished_at=None,
        log_path=log_path,
        commands=[(list(command), Path(cwd)) for command, cwd in commands],
        command_index=0,
    )


def _alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _row(record: RunRecord) -> tuple:
    commands = [
        {"cmd": command, "cwd": str(cwd)} for command, cwd in record.commands
    ]
    return (
        record.id,
        record.kind,
        record.stage,
        record.status,
        record.step,
        record.step_total,
        record.returncode,
        record.started_at,
        record.finished_at,
        str(record.log_path),
        json.dumps(commands),
        record.command_index,
        record.pid,
    )


def _record(row: tuple) -> RunRecord:
    commands = [
        (item["cmd"], Path(item["cwd"])) for item in json.loads(row[10])
    ]
    return RunRecord(
        id=row[0],
        kind=row[1],
        stage=row[2],
        status=row[3],
        step=row[4],
        step_total=row[5],
        returncode=row[6],
        started_at=row[7],
        finished_at=row[8],
        log_path=Path(row[9]),
        commands=commands,
        command_index=row[11],
        pid=row[12],
    )
