"""CLI for the Phase-1 dictionary and the analysis loop."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from m2s.analyze import append_run, apply_finding, phase1_report
from m2s.build import build
from m2s.fallback import MODEL_ID, CharsiuFallback, archive_missing
from m2s.lexicon import load
from m2s.rules import read_median, sing_display, sing_phones
from m2s.song import export_song
from m2s.train_cli import (
    train_export,
    train_health,
    train_resume,
    train_runs,
    train_serve,
    train_start,
    train_status,
    train_test,
)


def main() -> None:
    parser = argparse.ArgumentParser(prog="m2s")
    sub = parser.add_subparsers(dest="command", required=True)

    build_parser = sub.add_parser("build")
    build_parser.add_argument("--jsonl", type=Path, required=True)
    build_parser.add_argument("--out", type=Path, required=True)

    g2p_parser = sub.add_parser("g2p")
    g2p_parser.add_argument("ipa")
    g2p_parser.add_argument("--lyric", default="")
    g2p_parser.add_argument("--midi", type=int)
    g2p_parser.add_argument("--median", type=float)

    analyze_parser = sub.add_parser("analyze")
    analyze_parser.add_argument("--phase", type=Path, required=True)
    analyze_parser.add_argument("--runs", type=Path, required=True)
    analyze_parser.add_argument("--repo", type=Path, default=Path("."))

    finding_parser = sub.add_parser("finding")
    finding_parser.add_argument("code")
    finding_parser.add_argument("--rules", type=Path, required=True)
    finding_parser.add_argument("--textgrid", type=Path)
    finding_parser.add_argument("--note", default="")

    fallback_parser = sub.add_parser("fallback")
    fallback_parser.add_argument("--lexicon-jsonl", type=Path, required=True)
    fallback_parser.add_argument("--phonemes", type=Path, required=True)
    fallback_parser.add_argument("--out", type=Path, required=True)
    fallback_parser.add_argument("--words", nargs=3, required=True)
    fallback_parser.add_argument(
        "--model",
        action="store_true",
        help=f"Load {MODEL_ID}. Without this flag the command refuses to guess IPA.",
    )

    median_parser = sub.add_parser("median")
    median_parser.add_argument("--path", type=Path, required=True)

    record_parser = sub.add_parser("record")
    record_parser.add_argument("--root", type=Path, default=Path("songs/aufnahme"))

    song_parser = sub.add_parser("song")
    song_parser.add_argument("--ly", type=Path, required=True)
    song_parser.add_argument("--dictionary", type=Path, required=True)
    song_parser.add_argument("--out", type=Path, required=True)

    train = sub.add_parser("train")
    train_sub = train.add_subparsers(dest="train_command", required=True)
    serve = train_sub.add_parser("serve")
    serve.add_argument("--config", type=Path, required=True)
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    for name in ("health", "start", "status", "export", "runs", "resume", "test"):
        command = train_sub.add_parser(name)
        command.add_argument("--url", required=True)
        command.add_argument("--token", default="")
        if name == "start":
            command.add_argument("--stage", required=True, choices=["vocoder", "variance", "acoustic"])
            command.add_argument("--reset", action="store_true")
        if name == "test":
            command.add_argument("--stage", required=True, choices=["variance", "acoustic"])
        if name in ("status", "export", "resume"):
            command.add_argument("--run", required=True)

    args = parser.parse_args()
    if args.command == "build":
        summary = build(args.jsonl, args.out)
        print(json.dumps(summary))
        return
    if args.command == "g2p":
        print(
            sing_display(args.ipa, args.lyric, args.midi, args.median)
        )
        print(" ".join(sing_phones(args.ipa, args.lyric, args.midi, args.median)))
        return
    if args.command == "analyze":
        checks, row = phase1_report(args.phase, args.repo)
        append_run(args.runs, row)
        for check in checks:
            mark = "ok" if check.ok else "fail"
            print(f"{mark}\t{check.action}\t{check.name}\t{check.detail}")
        print(row["run_id"])
        return
    if args.command == "finding":
        action = apply_finding(
            args.code,
            rules_dir=args.rules,
            textgrid=args.textgrid,
            note=args.note,
        )
        print(action)
        return
    if args.command == "song":
        notes = export_song(args.ly, args.dictionary, args.out)
        sung = [note for note in notes if note.midi is not None]
        print(f"{len(sung)} notes, last word {sung[-1].word}")
        print(args.out.with_suffix(".mid"))
        print(args.out.with_suffix(".tsv"))
        return
    if args.command == "median":
        median = read_median(args.path)
        if median is None:
            raise SystemExit("kein Median")
        print(f"{median.midi}\t{median.count}\t{median.transcriptions_sha256}")
        return
    if args.command == "fallback":
        if not args.model:
            raise SystemExit(
                "Ohne --model wird keine IPA erfunden. Der Lauf lädt " + MODEL_ID
            )
        entries, _rejected = load(args.lexicon_jsonl)
        allowed = {
            line.strip()
            for line in args.phonemes.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }
        archive_missing(
            args.words,
            set(entries),
            allowed,
            CharsiuFallback(),
            args.out,
        )
        print(args.out)
        return
    if args.command == "record":
        try:
            from m2s.record_window import run_record_app
        except ImportError as exc:
            raise SystemExit(
                "Die Aufnahme-App braucht die Gruppe record: uv sync --group record"
            ) from exc
        run_record_app(args.root)
        return
    if args.command == "train":
        if args.train_command == "serve":
            train_serve(args.config, args.host, args.port)
        elif args.train_command == "health":
            train_health(args.url, args.token)
        elif args.train_command == "start":
            train_start(args.url, args.token, args.stage, args.reset)
        elif args.train_command == "status":
            train_status(args.url, args.token, args.run)
        elif args.train_command == "runs":
            train_runs(args.url, args.token)
        elif args.train_command == "resume":
            train_resume(args.url, args.token, args.run)
        elif args.train_command == "test":
            train_test(args.url, args.token, args.stage)
        elif args.train_command == "export":
            train_export(args.url, args.token, args.run)
        return
    raise SystemExit(f"unknown command {args.command}")


if __name__ == "__main__":
    main()
