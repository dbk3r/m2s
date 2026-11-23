"""HTTP control for training and inference tests. Progress is stored in SQLite."""

import secrets
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path

from m2s.progress import log_tail
from m2s.train_host import (
    STAGES,
    Host,
    export_command,
    stage_commands,
    stage_problems,
    test_command,
)
from m2s.train_store import RunRecord, TrainStore, new_record


class Runner:
    def __init__(self, host: Host):
        self.host = host
        self.store = TrainStore(host.work_dir / "train.sqlite")
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    def busy(self) -> bool:
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    def start(self, stage: str, reset: bool) -> RunRecord:
        if stage not in STAGES:
            raise ValueError(f"unbekannte Stufe {stage}")
        problems = stage_problems(self.host, stage, self.store.finished_stages())
        if problems:
            raise RuntimeError("\n".join(problems))
        return self._launch("train", stage, stage_commands(self.host, stage, reset))

    def resume(self, run_id: str) -> RunRecord:
        record = self.store.get(run_id)
        if record is None:
            raise KeyError(run_id)
        if record.kind != "train":
            raise RuntimeError("nur ein Trainingslauf kann aufgenommen werden")
        if record.status == "running":
            raise RuntimeError("der Lauf läuft noch")
        if record.status not in {"failed", "interrupted"}:
            raise RuntimeError("der Lauf ist nicht abgebrochen")
        if self.busy():
            raise RuntimeError("ein Lauf ist schon aktiv")
        remaining = record.commands[record.command_index :]
        remaining = [(_without_reset(command), cwd) for command, cwd in remaining]
        record.status = "running"
        record.finished_at = None
        record.returncode = None
        record.pid = None
        self.store.save(record)
        self._thread = threading.Thread(
            target=self._execute, args=(record, remaining, "a"), daemon=True
        )
        self._thread.start()
        return record

    def export(self, run_id: str) -> RunRecord:
        source = self.store.get(run_id)
        if source is None:
            raise KeyError(run_id)
        if source.status != "succeeded":
            raise RuntimeError("der Lauf ist noch nicht fertig")
        checkpoint = self._newest_checkpoint() if source.stage == "vocoder" else None
        command, cwd = export_command(self.host, source.stage, checkpoint)
        return self._launch("export", source.stage, [(command, cwd)])

    def test(self, stage: str) -> RunRecord:
        if stage not in self.store.finished_stages():
            raise RuntimeError(f"zuerst {stage} trainieren")
        command, cwd = test_command(self.host, stage)
        if self.host.test_ds is None or not self.host.test_ds.is_file():
            raise RuntimeError("test_ds fehlt")
        return self._launch("test", stage, [(command, cwd)])

    def progress(self, run_id: str) -> RunRecord:
        record = self.store.get(run_id)
        if record is None:
            raise KeyError(run_id)
        return self.store.refresh(record)

    def _launch(self, kind: str, stage: str, commands) -> RunRecord:
        if self.busy():
            raise RuntimeError("ein Lauf ist schon aktiv")
        run_id = datetime.now(timezone.utc).strftime(f"{kind}-{stage}-%Y%m%dT%H%M%SZ")
        log_path = self.host.work_dir / "logs" / f"{run_id}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        record = new_record(run_id, kind, stage, log_path, commands)
        self.store.add(record)
        self._thread = threading.Thread(
            target=self._execute, args=(record, commands, "w"), daemon=True
        )
        self._thread.start()
        return record

    def _execute(self, record: RunRecord, commands, mode: str) -> None:
        code = 0
        with record.log_path.open(mode, encoding="utf-8") as log:
            if mode == "a":
                log.write("\n$ resume\n")
            for offset, (command, cwd) in enumerate(commands):
                record.command_index = record.command_index if mode == "a" else 0
                if mode == "w":
                    record.command_index = offset
                else:
                    record.command_index = len(record.commands) - len(commands) + offset
                self.store.save(record)
                log.write("$ " + " ".join(command) + "\n")
                log.flush()
                process = subprocess.Popen(
                    command,
                    cwd=cwd,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                )
                record.pid = process.pid
                self.store.save(record)
                code = process.wait()
                record.pid = None
                if code != 0:
                    break
        record.returncode = code
        record.status = "succeeded" if code == 0 else "failed"
        record.finished_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.store.save(record)
        self.store.refresh(record)

    def _newest_checkpoint(self) -> Path | None:
        if not self.host.work_dir.is_dir():
            return None
        found = sorted(self.host.work_dir.rglob("*.ckpt"), key=lambda path: path.stat().st_mtime)
        return found[-1] if found else None


def _without_reset(command: list[str]) -> list[str]:
    return [part for part in command if part != "--reset"]


def create_app(runner: Runner):
    from fastapi import FastAPI, Header, HTTPException
    from pydantic import BaseModel

    app = FastAPI()

    class Start(BaseModel):
        stage: str
        reset: bool = False

    class TestStart(BaseModel):
        stage: str

    def authorize(header: str | None) -> None:
        expected = runner.host.token
        if not expected:
            return
        supplied = (header or "").removeprefix("Bearer ").strip()
        if not secrets.compare_digest(supplied, expected):
            raise HTTPException(status_code=401, detail="token fehlt")

    @app.get("/health")
    def health(authorization: str | None = Header(default=None)):
        authorize(authorization)
        from m2s.train_host import readiness

        problems = readiness(runner.host)
        return {"ok": not problems, "problems": problems, "busy": runner.busy()}

    @app.post("/runs")
    def start(body: Start, authorization: str | None = Header(default=None)):
        authorize(authorization)
        try:
            record = runner.start(body.stage, body.reset)
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _view(record, with_log=False)

    @app.get("/runs")
    def runs(authorization: str | None = Header(default=None)):
        authorize(authorization)
        return [_view(runner.store.refresh(record), with_log=False) for record in runner.store.list_runs()]

    @app.get("/runs/{run_id}")
    def status(run_id: str, authorization: str | None = Header(default=None)):
        authorize(authorization)
        try:
            record = runner.progress(run_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="unbekannter Lauf") from exc
        return _view(record, with_log=True)

    @app.post("/runs/{run_id}/resume")
    def resume(run_id: str, authorization: str | None = Header(default=None)):
        authorize(authorization)
        try:
            record = runner.resume(run_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="unbekannter Lauf") from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _view(record, with_log=False)

    @app.post("/runs/{run_id}/export")
    def export(run_id: str, authorization: str | None = Header(default=None)):
        authorize(authorization)
        try:
            record = runner.export(run_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="unbekannter Lauf") from exc
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _view(record, with_log=False)

    @app.post("/tests")
    def tests(body: TestStart, authorization: str | None = Header(default=None)):
        authorize(authorization)
        try:
            record = runner.test(body.stage)
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _view(record, with_log=False)

    return app


def _view(record: RunRecord, with_log: bool) -> dict:
    body = {
        "id": record.id,
        "kind": record.kind,
        "stage": record.stage,
        "status": record.status,
        "returncode": record.returncode,
        "step": record.step,
        "step_total": record.step_total,
        "started_at": record.started_at,
        "finished_at": record.finished_at,
    }
    if with_log:
        tail = log_tail(record.log_path).splitlines()
        body["log"] = "\n".join(tail[-40:])
    return body
