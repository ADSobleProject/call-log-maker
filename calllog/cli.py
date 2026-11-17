"""명령줄 진입점.

    python -m calllog batch            # input/ 폴더 일괄 변환
    python -m calllog files a.m4a b.txt  # 지정한 파일만 변환 (드래그 앤 드롭)
    python -m calllog watch            # 폴더 감시 자동 변환
    python -m calllog doctor           # 설치·설정 점검
    python -m calllog demo             # 샘플 txt 로 미리보기 결과 만들기
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import compat
from .config import PROJECT_ROOT, Config
from .pipeline import ProcessedRegistry, Processor, summarize_results
from .transcribe import audio_engine_available
from .watcher import FolderWatcher


def _fix_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass


def _print_header(cfg: Config) -> None:
    print("=" * 58)
    print("  🎙️  통화록 변환기 (call-log-maker)")
    print("=" * 58)
    print(cfg.describe())
    for warning in cfg.warnings:
        print(f"  ! {warning}")
    if not audio_engine_available():
        print("  · 음성 파일 변환: 설치 안 됨 → 지금은 .txt 만 변환됩니다 ('설치_점검.bat' 참고)")
    print("-" * 58)


def _load(args: argparse.Namespace) -> Config:
    root = Path(args.root).resolve() if getattr(args, "root", None) else PROJECT_ROOT
    return Config.load(getattr(args, "config", None), root=root)


def cmd_batch(args: argparse.Namespace) -> int:
    cfg = _load(args)
    cfg.ensure_dirs()
    _print_header(cfg)
    processor = Processor(cfg, log=print)
    files = processor.collect(cfg.input_dir)
    if not files:
        print(f"\n📂 {cfg.input_dir} 에 변환할 파일이 없습니다.")
        print("   · 녹음 파일(.m4a/.mp3/.wav...)이나 텍스트(.txt)를 이 폴더에 넣고 다시 실행해 주세요.")
        return 0
    print(f"\n📥 {len(files)}개 파일을 찾았습니다.\n")
    results = [processor.process_file(p) for p in files]
    print()
    print(summarize_results(results))
    if any(r.ok for r in results):
        print(f"📁 결과 폴더: {cfg.output_dir}")
    return 0 if all(r.ok or r.skipped for r in results) else 1


def cmd_files(args: argparse.Namespace) -> int:
    cfg = _load(args)
    cfg.ensure_dirs()
    _print_header(cfg)
    targets: list[Path] = []
    for raw in args.paths:
        path = Path(raw).expanduser()
        if path.is_dir():
            targets.extend(Processor(cfg).collect(path))
        elif path.exists():
            targets.append(path)
        else:
            print(f"  ! 찾을 수 없습니다: {raw}")
    if not targets:
        print("\n변환할 파일을 찾지 못했습니다.")
        print("   · 파일을 이 .bat 위로 끌어다 놓으면 바로 변환됩니다.")
        return 1
    # 드래그한 원본은 사용자 폴더에 그대로 두고, 해시 기록으로만 중복을 막는다
    cfg.archive_processed = False
    processor = Processor(cfg, log=print)
    print(f"\n📥 {len(targets)}개 파일을 변환합니다.\n")
    results = [processor.process_file(p) for p in targets]
    print()
    print(summarize_results(results))
    if any(r.ok for r in results):
        print(f"📁 결과 폴더: {cfg.output_dir}")
    return 0 if all(r.ok or r.skipped for r in results) else 1


def cmd_watch(args: argparse.Namespace) -> int:
    cfg = _load(args)
    cfg.ensure_dirs()
    _print_header(cfg)
    interval = args.interval or cfg.watch_interval_sec
    watcher = FolderWatcher(Processor(cfg, log=print), interval=interval, log=print)
    watcher.run()
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    cfg = _load(args)
    _print_header(cfg)
    ok = True
    here = compat.current_interpreter()

    print("\n[점검]")
    print(f"  · 이 프로그램을 돌리는 Python: {here.version_text} ({here.bits_text})")
    if tuple(here.version) < compat.MIN_PYTHON:
        print(f"    ✗ Python {compat.MIN_PYTHON[0]}.{compat.MIN_PYTHON[1]} 이상이 필요합니다.")
        ok = False

    try:
        import docx  # noqa: F401

        print("  · python-docx: 설치됨 (.md/.docx 결과물 만들기 가능)")
    except Exception as exc:  # 설치 안 됨 또는 깨짐
        print(f"    ✗ python-docx 를 불러오지 못했습니다({type(exc).__name__}) → '설치_점검.bat' 을 실행하세요.")
        ok = False

    if audio_engine_available():
        model = cfg.transcribe.get("model", "small")
        print(f"  · faster-whisper: 설치됨 (음성 파일 변환 가능, 모델 {model})")
        print("    모델 파일은 첫 변환 때 한 번만 받고, 그 뒤로는 오프라인으로 씁니다.")
    else:
        print("    ! faster-whisper 가 없습니다 → .txt 변환은 되지만 음성 파일은 변환되지 않습니다.")
        if not compat.is_audio_ready(here.version, here.bits):
            print(f"      이유: {compat.describe_audio_problem(here)}")
        print("")
        for line in compat.audio_help_lines(here):
            print("    " + line)
        print("")

    for label, path in (("입력", cfg.input_dir), ("결과", cfg.output_dir), ("완료", cfg.processed_dir)):
        state = "있음" if path.exists() else "없음(자동 생성)"
        print(f"  · {label} 폴더: {path} [{state}]")

    samples = list(cfg.input_dir.glob("*")) if cfg.input_dir.exists() else []
    print(f"  · 대기 중인 파일: {len([p for p in samples if p.is_file() and not p.name.startswith('.')])}개")
    print("  · 더 자세한 환경 점검: python setup_env.py --check")
    print("\n결과: " + ("사용 가능 ✅" if ok else "설치를 확인해 주세요 ⚠️"))
    return 0 if ok else 1


def cmd_demo(args: argparse.Namespace) -> int:
    cfg = _load(args)
    cfg.ensure_dirs()
    _print_header(cfg)
    sample = cfg.root / "samples" / "통화 녹음 김지훈_261117_210000.txt"
    if not sample.exists():
        print(f"샘플 파일이 없습니다: {sample}")
        return 1
    # 샘플 원본은 그대로 두고(이동·중복기록 없이) 미리보기만 만든다
    cfg.archive_processed = False
    processor = Processor(cfg, log=print)
    processor = Processor(cfg, log=print)
    processor.registry = ProcessedRegistry(cfg.root / ".demo" / ".processed.json")
    print(f"\n🧪 샘플로 미리보기를 만듭니다: {sample.name}\n")
    result = processor.process_file(sample)
    if result.ok:
        print("\n✅ 미리보기 완성:")
        for path in result.outputs:
            print(f"   · {path}")
        return 0
    print(f"\n✗ 실패: {result.error or result.reason}")
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="calllog",
        description="음성 녹음/텍스트 기록을 깔끔한 통화록(.md/.docx)으로 바꿉니다.",
    )
    parser.add_argument("--config", help="설정 파일 경로 (기본: 프로젝트 폴더의 config.json)")
    parser.add_argument("--root", help="프로젝트 폴더 (기본: 이 패키지의 상위 폴더)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("batch", help="input 폴더의 모든 파일을 한 번에 변환")
    p.set_defaults(func=cmd_batch)

    p = sub.add_parser("files", help="지정한 파일만 변환 (드래그 앤 드롭용)")
    p.add_argument("paths", nargs="+", help="변환할 파일 또는 폴더")
    p.set_defaults(func=cmd_files)

    p = sub.add_parser("watch", help="폴더를 계속 지켜보다 새 파일을 자동 변환")
    p.add_argument("--interval", type=float, default=None, help="확인 주기(초), 기본 3")
    p.set_defaults(func=cmd_watch)

    p = sub.add_parser("doctor", help="설치 상태와 설정을 점검")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("demo", help="샘플 텍스트로 결과 미리보기")
    p.set_defaults(func=cmd_demo)
    return parser


def main(argv: list[str] | None = None) -> int:
    _fix_console()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args) or 0)
    except KeyboardInterrupt:
        print("\n중단했습니다.")
        return 130


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
