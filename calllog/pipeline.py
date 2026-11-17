"""파일 한 개/폴더 전체를 통화록으로 만드는 파이프라인."""
from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable, Sequence

from . import analyze, render
from .config import Config
from .filenames import parse_filename, safe_filename
from .models import CallDocument
from .parsers import ParsedText, Segment, format_timestamp, parse_text_file
from .transcribe import (
    Transcriber,
    TranscriptionError,
    TranscriptionResult,
    WhisperTranscriber,
    build_transcriber,
)

AUDIO_EXTENSIONS = {".m4a", ".mp3", ".wav", ".ogg", ".flac", ".aac", ".wma", ".opus", ".webm", ".m4b", ".amr"}
TEXT_EXTENSIONS = {".txt"}
SUPPORTED_EXTENSIONS = AUDIO_EXTENSIONS | TEXT_EXTENSIONS

_SKIP_NAMES = {"desktop.ini", "thumbs.db", ".ds_store", ".gitkeep"}


@dataclass
class ProcessResult:
    source: Path
    ok: bool = False
    skipped: bool = False
    reason: str = ""
    outputs: list[Path] = field(default_factory=list)
    error: str = ""
    doc: CallDocument | None = None
    seconds: float = 0.0


class ProcessedRegistry:
    """이미 처리한 파일을 해시로 기억해 중복 변환을 막는다."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.entries: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                self.entries = {str(k): v for k, v in data.items() if isinstance(v, dict)}
        except (OSError, json.JSONDecodeError, ValueError):
            self.entries = {}

    def digest(self, path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    def contains(self, digest: str) -> bool:
        return digest in self.entries

    def add(self, digest: str, source: Path, outputs: Sequence[Path]) -> None:
        self.entries[digest] = {
            "source": source.name,
            "processed_at": datetime.now().isoformat(timespec="seconds"),
            "outputs": [str(p) for p in outputs],
        }
        self.save()

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            tmp.write_text(json.dumps(self.entries, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self.path)
        except OSError:
            pass


class Processor:
    """설정 + 전사 엔진을 들고 파일을 변환한다."""

    def __init__(
        self,
        config: Config,
        transcriber: Transcriber | None = None,
        log: Callable[[str], None] | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.config = config
        self._transcriber = transcriber
        self.log = log or (lambda _m: None)
        self.now = now or datetime.now
        self.registry = ProcessedRegistry(config.input_dir / ".processed.json")

    # ---------------------------------------------------------------- 엔진
    @property
    def transcriber(self) -> Transcriber:
        if self._transcriber is None:
            self._transcriber = build_transcriber(self.config, progress=self.log)
        return self._transcriber

    # ---------------------------------------------------------------- 스캔
    def collect(self, folder: Path | None = None, recursive: bool = True) -> list[Path]:
        folder = Path(folder or self.config.input_dir)
        if not folder.exists():
            return []
        iterator = folder.rglob("*") if recursive else folder.glob("*")
        files: list[Path] = []
        for path in iterator:
            if not path.is_file():
                continue
            if self._skip(path):
                continue
            files.append(path)
        files.sort(key=lambda p: (p.stat().st_mtime if p.exists() else 0, p.name))
        return files

    def _skip(self, path: Path) -> bool:
        name = path.name
        if name.startswith(".") or name.startswith("~$"):
            return True
        if name.lower() in _SKIP_NAMES:
            return True
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return True
        try:
            if path.stat().st_size == 0:
                return True  # 아직 복사 중일 수 있음
        except OSError:
            return True
        return False

    # ---------------------------------------------------------------- 변환
    def process_folder(self, folder: Path | None = None) -> list[ProcessResult]:
        self.config.ensure_dirs()
        results = [self.process_file(p) for p in self.collect(folder)]
        return results

    def process_file(self, path: str | Path) -> ProcessResult:
        path = Path(path)
        started = datetime.now()
        result = ProcessResult(source=path)

        if not path.exists():
            result.reason = "파일이 없습니다."
            return result
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            result.reason = f"지원하지 않는 형식입니다: {path.suffix or '확장자 없음'}"
            return result
        if self._skip(path):
            result.skipped = True
            result.reason = "건너뛴 파일(빈 파일·숨김·임시 파일)"
            return result

        try:
            digest = self.registry.digest(path)
        except OSError as exc:
            result.reason = f"파일을 읽지 못했습니다: {exc}"
            return result
        if self.registry.contains(digest):
            result.skipped = True
            result.reason = "이미 변환한 파일(중복)"
            self.log(f"  ↷ 이미 처리한 파일이라 건너뜁니다: {path.name}")
            return result

        try:
            doc = self._build_document(path)
            outputs = self._write_outputs(doc)
            doc.source_path = path
            result.doc = doc
            result.outputs = outputs
            result.ok = True
            self.registry.add(digest, path, outputs)
            if self.config.archive_processed:
                self._archive(path)
            self.log(f"  ✓ {path.name} → {', '.join(p.name for p in outputs)}")
        except TranscriptionError as exc:
            result.error = str(exc)
            self.log(f"  ✗ {path.name}: {exc}")
        except Exception as exc:  # 예상 못 한 오류도 나머지 파일 처리를 막지 않는다
            result.error = f"{type(exc).__name__}: {exc}"
            self.log(f"  ✗ {path.name}: {result.error}")
        result.seconds = (datetime.now() - started).total_seconds()
        return result

    # ---------------------------------------------------------------- 문서
    def _build_document(self, path: Path) -> CallDocument:
        info = parse_filename(path, max_len=self.config.title_max_len)
        warnings: list[str] = []
        duration: float | None = None

        if path.suffix.lower() in TEXT_EXTENSIONS:
            parsed: ParsedText = parse_text_file(path)
            segments = parsed.segments
            warnings.extend(parsed.warnings)
            mode = "텍스트 변환본"
            engine = ""
            if parsed.when:
                info.when = parsed.when
                if parsed.time_known:
                    info.time_known = True
            if parsed.title:
                info.title = parsed.title
            duration = parsed.duration_sec
        else:
            transcription: TranscriptionResult = self.transcriber.transcribe(path)
            segments = transcription.segments
            duration = transcription.duration_sec
            engine = transcription.engine
            mode = "음성→텍스트"
            warnings.extend(transcription.warnings)

        if duration is None:
            stamps = [s.start for s in segments if s.start]
            duration = max(stamps) if stamps else None

        text = "\n".join(s.text for s in segments)
        kws = analyze.keywords(text, self.config.max_keywords)
        summary = analyze.summarize(segments, self.config.max_summary_sentences, kws)
        speakers = _speakers(segments)
        actions = analyze.extract_actions(segments, self.config.max_action_items, speakers)
        doc = CallDocument(
            title=info.title or "통화 녹음",
            when=info.when,
            source_name=path.name,
            mode=mode,
            engine=engine,
            duration_sec=duration,
            segments=segments,
            keywords=kws,
            summary=summary,
            actions=actions,
            amounts=analyze.amounts_in(text),
            dates=analyze.dates_in(text),
            speakers=speakers,
            warnings=warnings,
            created_at=self.now(),
        )
        if not segments:
            doc.warnings.append("대화 내용을 정리하지 못했습니다. 원본 파일을 확인해 주세요.")
        return doc

    def _write_outputs(self, doc: CallDocument) -> list[Path]:
        base = f"{doc.stamp()}_{safe_filename(doc.title, self.config.title_max_len)}_통화록"
        targets: list[tuple[str, Path]] = []
        for fmt in self.config.document_formats:
            path = self.config.output_dir / f"{base}.{fmt}"
            if path.exists():
                for i in range(2, 100):
                    candidate = self.config.output_dir / f"{base}_{i}.{fmt}"
                    if not candidate.exists():
                        path = candidate
                        break
            targets.append((fmt, path))
        outputs: list[Path] = []
        for fmt, path in targets:
            if fmt == "md":
                outputs.append(render.write_markdown(doc, path))
            else:
                outputs.append(render.write_docx(doc, path))
        if self.config.keep_raw_transcript and doc.segments:
            raw_path = self.config.output_dir / f"{base}_전사원문.txt"
            raw_path.write_text(
                "\n".join(
                    f"[{format_timestamp(s.start)}] {s.speaker or ''} {s.text}".strip()
                    for s in doc.segments
                ),
                encoding="utf-8",
            )
            outputs.append(raw_path)
        return outputs

    def _archive(self, path: Path) -> None:
        target_dir = self.config.processed_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / path.name
        if target.exists():
            stamp = datetime.now().strftime("%H%M%S")
            target = target_dir / f"{path.stem}_{stamp}{path.suffix}"
        try:
            shutil.move(str(path), str(target))
        except OSError as exc:
            self.log(f"  ! 원본을 옮기지 못했습니다({path.name}): {exc}")


def _speakers(segments: Iterable[Segment]) -> list[str]:
    seen: list[str] = []
    for seg in segments:
        if seg.speaker and seg.speaker not in seen:
            seen.append(seg.speaker)
    return seen


def summarize_results(results: Sequence[ProcessResult]) -> str:
    ok = [r for r in results if r.ok]
    skipped = [r for r in results if r.skipped]
    failed = [r for r in results if not r.ok and not r.skipped]
    lines = [f"변환 완료 {len(ok)}개 · 건너뜀 {len(skipped)}개 · 실패 {len(failed)}개"]
    return "\n".join(lines)
