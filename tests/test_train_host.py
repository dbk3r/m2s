import sys
import time
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from m2s.audio_lock import audio_problems
from m2s.train_api import Runner, create_app
from m2s.train_host import load_host, stage_commands, stage_problems, windows_backend_problems

LOCKED = {
    "audio_sample_rate": 44100,
    "hop_size": 512,
    "win_size": 2048,
    "fft_size": 2048,
    "audio_num_mel_bins": 128,
    "fmin": 40,
    "fmax": 16000,
    "mel_base": "e",
}


def _write_host(tmp_path: Path, hop: int = 512) -> Path:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "a.wav").write_bytes(b"wav")
    (corpus / "transcriptions.csv").write_text(
        "name,ph_seq,ph_dur\na,aː t,0.1 0.2\n",
        encoding="utf-8",
    )
    diffsinger = tmp_path / "DiffSinger"
    vocoders = tmp_path / "SingingVocoders"
    (diffsinger / "scripts").mkdir(parents=True)
    vocoders.mkdir()
    checkpoint = tmp_path / "vocoder.ckpt"
    checkpoint.write_bytes(b"ckpt")
    audio = dict(LOCKED)
    audio["hop_size"] = hop
    for folder, name in ((diffsinger, "variance.yaml"), (diffsinger, "acoustic.yaml"), (vocoders, "ft.yaml")):
        payload = dict(audio)
        payload["data_input_path"] = [str(corpus)]
        payload["finetune_ckpt_path"] = str(checkpoint)
        (folder / name).write_text(yaml.safe_dump(payload), encoding="utf-8")
    (diffsinger / "scripts" / "binarize.py").write_text("print('binarize')\n", encoding="utf-8")
    (diffsinger / "scripts" / "train.py").write_text("print('step=12')\n", encoding="utf-8")
    (vocoders / "process.py").write_text("print('process')\n", encoding="utf-8")
    (vocoders / "train.py").write_text("print('step=4')\n", encoding="utf-8")
    lock = tmp_path / "audio.lock.yaml"
    lock.write_text(
        "sample_rate: 44100\nhop_size: 512\nwin_size: 2048\nfft_size: 2048\n"
        "num_mel_bins: 128\nfmin: 40\nfmax: 16000\n",
        encoding="utf-8",
    )
    host = tmp_path / "host.yaml"
    host.write_text(
        "\n".join(
            [
                "token: geheim",
                f"train_python: {sys.executable}",
                f"corpus_dir: {corpus}",
                f"diffsinger_dir: {diffsinger}",
                f"singingvocoders_dir: {vocoders}",
                f"vocoder_checkpoint: {checkpoint}",
                f"vocoder_config: {vocoders / 'ft.yaml'}",
                f"variance_config: {diffsinger / 'variance.yaml'}",
                f"acoustic_config: {diffsinger / 'acoustic.yaml'}",
                f"work_dir: {tmp_path / 'work'}",
                "preprocess_workers: 2",
                "mel_base: e",
                f"lock: {lock}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return host


def test_windows_refuses_the_nccl_backend():
    problems = windows_backend_problems(
        {"pl_trainer_strategy": {"process_group_backend": "nccl"}},
        "nt",
    )
    assert problems == ["process_group_backend ist nccl. Unter Windows gibt es NCCL nicht, auf gloo stellen"]
    assert windows_backend_problems(
        {"pl_trainer_strategy": {"process_group_backend": "nccl"}},
        "posix",
    ) == []


def test_progress_reads_the_printed_step_and_total():
    from m2s.progress import parse_progress

    step, total = parse_progress("Epoch 0: 12/100000\nstep=12\n")
    assert (step, total) == (12, 100000)


def test_an_aborted_run_resumes_without_reset(tmp_path: Path):
    host_path = _write_host(tmp_path)
    flag = tmp_path / "SingingVocoders" / "fail.once"
    flag.write_text("1", encoding="utf-8")
    script = tmp_path / "SingingVocoders" / "train.py"
    script.write_text(
        "from pathlib import Path\n"
        f"flag = Path(r'{flag}')\n"
        "if flag.exists():\n"
        "    flag.unlink()\n"
        "    raise SystemExit(1)\n"
        "print('step=9')\n"
        "print('20/100')\n",
        encoding="utf-8",
    )
    host = load_host(host_path)
    client = TestClient(create_app(Runner(host)))
    headers = {"Authorization": "Bearer geheim"}
    started = client.post("/runs", json={"stage": "vocoder"}, headers=headers)
    assert started.status_code == 200
    run_id = started.json()["id"]
    status = _wait(client, run_id, headers)
    assert status["status"] == "failed"
    resumed = client.post(f"/runs/{run_id}/resume", headers=headers)
    assert resumed.status_code == 200
    status = _wait(client, run_id, headers)
    assert status["status"] == "succeeded"
    assert status["step"] == 20
    assert status["step_total"] == 100
    assert "--reset" not in status["log"]


def _wait(client: TestClient, run_id: str, headers: dict) -> dict:
    status = {}
    for _ in range(50):
        status = client.get(f"/runs/{run_id}", headers=headers).json()
        if status["status"] != "running":
            return status
        time.sleep(0.05)
    return status


def test_locked_hop_rejects_a_different_config():
    problems = audio_problems({"hop_size": 256, "audio_sample_rate": 44100}, "e")
    assert any("hop_size ist 256" in problem for problem in problems)
    assert any("mel_base" in problem or "sample_rate" in problem for problem in problems)


def test_commands_follow_the_published_scripts(tmp_path: Path):
    host = load_host(_write_host(tmp_path))
    vocoder = stage_commands(host, "vocoder", reset=False)
    assert vocoder[0][0][1:] == [
        "process.py",
        "--config",
        str(host.vocoder_config),
        "--num_cpu",
        "2",
        "--strx",
        "0",
    ]
    train = stage_commands(host, "acoustic", reset=True)[1][0]
    assert train[1:] == [
        "scripts/train.py",
        "--config",
        str(host.acoustic_config),
        "--exp_name",
        "acoustic",
        "--reset",
    ]


def test_a_run_waits_for_the_previous_stage_and_then_finishes(tmp_path: Path):
    host = load_host(_write_host(tmp_path))
    assert any(problem.startswith("zuerst") for problem in stage_problems(host, "acoustic", set()))
    runner = Runner(host)
    client = TestClient(create_app(runner))
    denied = client.post("/runs", json={"stage": "acoustic"}, headers={"Authorization": "Bearer geheim"})
    assert denied.status_code == 409
    started = client.post("/runs", json={"stage": "vocoder"}, headers={"Authorization": "Bearer geheim"})
    assert started.status_code == 200
    run_id = started.json()["id"]
    status = _wait(client, run_id, {"Authorization": "Bearer geheim"})
    assert status["status"] == "succeeded"
    assert status["step"] == 4
    assert client.get("/health").status_code == 401
