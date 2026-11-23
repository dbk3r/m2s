"""Start the training service and call it from another machine."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

from m2s.train_api import Runner, create_app
from m2s.train_host import load_host


def train_serve(config: Path, host: str, port: int) -> None:
    loaded = load_host(config)
    if host not in {"127.0.0.1", "localhost"} and not loaded.token:
        raise SystemExit("Ein Dienst auf dem Netz braucht token in der Host-Datei")
    import uvicorn

    uvicorn.run(create_app(Runner(loaded)), host=host, port=port)


def train_health(url: str, token: str) -> None:
    print(json.dumps(_call(url, token, "GET", "/health"), ensure_ascii=False, indent=2))


def train_start(url: str, token: str, stage: str, reset: bool) -> None:
    body = _call(url, token, "POST", "/runs", {"stage": stage, "reset": reset})
    print(body["id"])
    print(body["status"])


def train_runs(url: str, token: str) -> None:
    for run in _call(url, token, "GET", "/runs"):
        print(f"{run['id']}\t{run['kind']}\t{run['stage']}\t{run['status']}\t{_step(run)}")


def train_status(url: str, token: str, run_id: str) -> None:
    body = _call(url, token, "GET", f"/runs/{run_id}")
    print(body["status"])
    print(_step(body))
    if body.get("log"):
        print(body["log"])


def train_resume(url: str, token: str, run_id: str) -> None:
    body = _call(url, token, "POST", f"/runs/{run_id}/resume")
    print(body["id"])
    print(body["status"])


def train_test(url: str, token: str, stage: str) -> None:
    body = _call(url, token, "POST", "/tests", {"stage": stage})
    print(body["id"])
    print(body["status"])


def train_export(url: str, token: str, run_id: str) -> None:
    body = _call(url, token, "POST", f"/runs/{run_id}/export")
    print(body["id"])
    print(body["status"])


def _step(body: dict) -> str:
    if body.get("step") is None:
        return "step —"
    if body.get("step_total") is None:
        return f"step {body['step']}"
    return f"step {body['step']}/{body['step_total']}"


def _call(url: str, token: str, method: str, path: str, payload: dict | None = None):
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(url.rstrip("/") + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode()
        raise SystemExit(f"{exc.code} {detail}") from exc
